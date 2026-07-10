"""
core/scrcpy_runner.py
Handles scrcpy download and process lifecycle for AndroidMirror.

Features:
- Auto-resolve latest scrcpy release from GitHub API
- Download scrcpy-win64-*.zip with progress callback
- Extract to bin/scrcpy/
- ScrcpyRunner class: start / stop / is_running
- on_stop_callback when scrcpy window closes externally
"""

import json
import os
import re
import subprocess
import threading
import urllib.request
import zipfile

import sys
# ---------------------------------------------------------------------------
# Paths (Refactored for PyInstaller portability)
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    # If running as .exe, use the .exe directory
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # If running as script, use the project root
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRCPY_DIR    = os.path.join(_BASE_DIR, "bin", "scrcpy")
_SCRCPY_EXE    = os.path.join(_SCRCPY_DIR, "scrcpy.exe")
_GITHUB_API    = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_download_url() -> tuple[str, str]:
    """
    Query GitHub API and return (download_url, filename) for the
    scrcpy-win64-*.zip asset in the latest release.
    Raises RuntimeError if not found.
    """
    req = urllib.request.Request(
        _GITHUB_API,
        headers={"User-Agent": "AndroidMirror/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if re.match(r"scrcpy-win64-.*\.zip$", name):
            return asset["browser_download_url"], name

    raise RuntimeError("scrcpy-win64-*.zip asset not found in latest release")


def _download_with_progress(url: str, dest: str, on_status=None) -> None:
    """
    Download *url* to *dest*.  Calls on_status(msg) with progress updates.
    """
    def _report(block_count, block_size, total_size):
        if total_size > 0 and on_status:
            downloaded = min(block_count * block_size, total_size)
            pct = int(downloaded * 100 / total_size)
            mb  = downloaded / (1024 * 1024)
            on_status(f"Mengunduh scrcpy... {pct}% ({mb:.1f} MB)")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest, reporthook=_report)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_scrcpy_available() -> bool:
    """Return True if scrcpy.exe exists at the expected location."""
    return os.path.isfile(_SCRCPY_EXE)


def ensure_scrcpy(on_status=None) -> bool:
    """
    Make sure scrcpy is available.
    Downloads and extracts the latest Windows release from GitHub if missing.

    Parameters
    ----------
    on_status : callable(str) | None
        Called with human-readable status messages for the UI status bar.

    Returns
    -------
    bool
        True  – scrcpy is ready.
        False – Download failed; caller should display an error.
    """
    if is_scrcpy_available():
        return True

    try:
        if on_status:
            on_status("Memeriksa versi scrcpy terbaru...")

        download_url, filename = _resolve_download_url()
        zip_path = os.path.join(_SCRCPY_DIR, filename)

        _download_with_progress(download_url, zip_path, on_status)

        if on_status:
            on_status("Mengekstrak scrcpy...")

        os.makedirs(_SCRCPY_DIR, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            # Detect the top-level folder prefix (e.g. "scrcpy-win64-v3.1/")
            prefix = ""
            if members and "/" in members[0]:
                prefix = members[0].split("/")[0] + "/"
            for member in members:
                rel = member[len(prefix):] if prefix and member.startswith(prefix) else member
                if not rel:
                    continue  # skip root dir entry
                dest = os.path.join(_SCRCPY_DIR, rel)
                if member.endswith("/"):
                    os.makedirs(dest, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as out:
                        out.write(src.read())

        # Clean up zip
        try:
            os.remove(zip_path)
        except OSError:
            pass

        if is_scrcpy_available():
            if on_status:
                on_status("scrcpy siap digunakan.")
            return True

        if on_status:
            on_status("Gagal mengunduh scrcpy. Periksa koneksi internet Anda.")
        return False

    except Exception as exc:  # noqa: BLE001
        print(f"[ScrcpyRunner] Download error: {exc}")
        if on_status:
            on_status("Gagal mengunduh scrcpy. Periksa koneksi internet Anda.")
        return False


# ---------------------------------------------------------------------------
# ScrcpyRunner class
# ---------------------------------------------------------------------------

class ScrcpyRunner:
    """
    Manages a single scrcpy process.

    Parameters
    ----------
    on_status : callable(str) | None
        Called with status/error messages for the UI status bar.
    """

    # Default scrcpy flags (now partially dynamic)
    _DEFAULT_FLAGS = [
        "--window-title",   "AndroidMirror",
    ]

    def __init__(self, on_status=None):
        self._on_status: callable = on_status
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._watch_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self, device_serial: str, options: dict = None, on_stop_callback=None) -> bool:
        """
        Launch scrcpy for *device_serial*.

        Downloads scrcpy first if it is not available.

        Parameters
        ----------
        device_serial : str
            ADB serial of the target device.
        options : dict | None
            Dictionary of scrcpy options (bitrate, fps, etc.)
        on_stop_callback : callable() | None
            Called from a background thread when scrcpy exits (for any reason).

        Returns
        -------
        bool
            True if the process was launched successfully.
        """
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return True  # Already running

        # Ensure scrcpy binary present (may download)
        if not ensure_scrcpy(on_status=self._on_status):
            return False

        # Build dynamic command
        cmd = [_SCRCPY_EXE, "--serial", device_serial] + self._DEFAULT_FLAGS
        
        if options:
            if "bitrate" in options:
                cmd += ["--video-bit-rate", str(options["bitrate"])]
            if "fps" in options:
                cmd += ["--max-fps", str(options["fps"])]
            if options.get("always_on_top"):
                cmd += ["--always-on-top"]
            if options.get("turn_screen_off"):
                cmd += ["--turn-screen-off"]
            if options.get("stay_awake"):
                cmd += ["--stay-awake"]
            if options.get("fullscreen"):
                cmd += ["--fullscreen"]
            
            # --- Screen Recording ---
            if options.get("record"):
                import datetime
                record_dir = os.path.join(_BASE_DIR, "recordings")
                os.makedirs(record_dir, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                # Using .mkv instead of .mp4 for better resilience against 
                # abrupt process termination (which causes corruption in MP4).
                filename = f"AndroidMirror_{timestamp}.mkv"
                record_path = os.path.join(record_dir, filename)
                
                cmd += ["--record", record_path]
        

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=_SCRCPY_DIR,  # Set Working Directory so it finds DLLs
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as exc:  # noqa: BLE001
            self._status(f"Gagal menjalankan scrcpy: {exc}")
            return False

        with self._lock:
            self._process = proc

        self._status("Sedang streaming...")

        # Watcher thread: fires on_stop_callback when scrcpy exits
        self._watch_thread = threading.Thread(
            target=self._watch,
            args=(proc, on_stop_callback),
            name="ScrcpyWatcher",
            daemon=True,
        )
        self._watch_thread.start()
        return True

    def stop(self):
        """Terminate the running scrcpy process (if any)."""
        with self._lock:
            proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                # Try to terminate gracefully
                proc.terminate()
                # Give it some time to flush the video recording
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if still running
                try:
                    proc.kill()
                except Exception:
                    pass
            except Exception:
                pass
        with self._lock:
            self._process = None

    def is_running(self) -> bool:
        """Return True if the scrcpy process is currently alive."""
        with self._lock:
            return self._process is not None and self._process.poll() is None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _status(self, msg: str):
        if self._on_status:
            try:
                self._on_status(msg)
            except Exception:  # noqa: BLE001
                pass

    def _watch(self, proc: subprocess.Popen, on_stop_callback):
        """
        Block until *proc* exits, read stderr, then invoke on_stop_callback.
        """
        stderr_output = ""
        try:
            _, stderr_bytes = proc.communicate()
            if stderr_bytes:
                stderr_output = stderr_bytes.decode(errors="replace").strip()
        except Exception:  # noqa: BLE001
            proc.wait()

        with self._lock:
            self._process = None

        # Surface meaningful errors; skip benign INFO lines
        if stderr_output:
            lines = [
                ln for ln in stderr_output.splitlines()
                if ln.strip()
                and not ln.lstrip().startswith("INFO")
                and "disconnected" not in ln.lower()
            ]
            if lines:
                self._status(f"scrcpy: {lines[-1]}")
            else:
                self._status("Mirror dihentikan.")
        else:
            self._status("Mirror dihentikan.")

        if on_stop_callback:
            try:
                on_stop_callback()
            except Exception:  # noqa: BLE001
                pass
