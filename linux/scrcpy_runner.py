import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import threading
import urllib.request

import sys

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRCPY_DIR    = os.path.join(_BASE_DIR, "bin", "scrcpy")
_SCRCPY_EXE    = os.path.join(_SCRCPY_DIR, "scrcpy")
_GITHUB_API    = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"


def _resolve_download_url() -> tuple[str, str]:
    req = urllib.request.Request(
        _GITHUB_API,
        headers={"User-Agent": "AndroidMirror/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if re.match(r"scrcpy-linux-.*\.tar\.gz$", name):
            return asset["browser_download_url"], name

    raise RuntimeError("scrcpy-linux-*.tar.gz asset not found in latest release")


def _download_with_progress(url: str, dest: str, on_status=None) -> None:
    def _report(block_count, block_size, total_size):
        if total_size > 0 and on_status:
            downloaded = min(block_count * block_size, total_size)
            pct = int(downloaded * 100 / total_size)
            mb  = downloaded / (1024 * 1024)
            on_status(f"Mengunduh scrcpy... {pct}% ({mb:.1f} MB)")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest, reporthook=_report)


def _make_executable(path: str):
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def is_scrcpy_available() -> bool:
    return os.path.isfile(_SCRCPY_EXE)


def ensure_scrcpy(on_status=None) -> bool:
    if is_scrcpy_available():
        return True

    try:
        if on_status:
            on_status("Memeriksa versi scrcpy terbaru...")

        download_url, filename = _resolve_download_url()
        tarball_path = os.path.join(_SCRCPY_DIR, filename)

        _download_with_progress(download_url, tarball_path, on_status)

        if on_status:
            on_status("Mengekstrak scrcpy...")

        os.makedirs(_SCRCPY_DIR, exist_ok=True)
        with tarfile.open(tarball_path, "r:gz") as tf:
            tmp_dir = tempfile.mkdtemp()
            try:
                tf.extractall(tmp_dir)
                # If there's a single top-level directory, move its contents up
                extracted = os.listdir(tmp_dir)
                if len(extracted) == 1 and os.path.isdir(os.path.join(tmp_dir, extracted[0])):
                    src_dir = os.path.join(tmp_dir, extracted[0])
                    for item in os.listdir(src_dir):
                        shutil.move(os.path.join(src_dir, item), os.path.join(_SCRCPY_DIR, item))
                else:
                    for item in extracted:
                        shutil.move(os.path.join(tmp_dir, item), os.path.join(_SCRCPY_DIR, item))
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            os.remove(tarball_path)
        except OSError:
            pass

        _make_executable(_SCRCPY_EXE)

        if is_scrcpy_available():
            if on_status:
                on_status("scrcpy siap digunakan.")
            return True

        if on_status:
            on_status("Gagal mengunduh scrcpy. Periksa koneksi internet Anda.")
        return False

    except Exception as exc:
        print(f"[ScrcpyRunner] Download error: {exc}")
        if on_status:
            on_status("Gagal mengunduh scrcpy. Periksa koneksi internet Anda.")
        return False


class ScrcpyRunner:
    _DEFAULT_FLAGS = [
        "--window-title", "AndroidMirror",
    ]

    def __init__(self, on_status=None):
        self._on_status: callable = on_status
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._watch_thread: threading.Thread | None = None

    def start(self, device_serial: str, options: dict = None, on_stop_callback=None) -> bool:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return True

        if not ensure_scrcpy(on_status=self._on_status):
            return False

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

            if options.get("record"):
                import datetime
                record_dir = os.path.join(_BASE_DIR, "recordings")
                os.makedirs(record_dir, exist_ok=True)

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"AndroidMirror_{timestamp}.mkv"
                record_path = os.path.join(record_dir, filename)

                cmd += ["--record", record_path]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=_SCRCPY_DIR,
            )
        except Exception as exc:
            self._status(f"Gagal menjalankan scrcpy: {exc}")
            return False

        with self._lock:
            self._process = proc

        self._status("Sedang streaming...")

        self._watch_thread = threading.Thread(
            target=self._watch,
            args=(proc, on_stop_callback),
            name="ScrcpyWatcher",
            daemon=True,
        )
        self._watch_thread.start()
        return True

    def stop(self):
        with self._lock:
            proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
            except Exception:
                pass
        with self._lock:
            self._process = None

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def _status(self, msg: str):
        if self._on_status:
            try:
                self._on_status(msg)
            except Exception:
                pass

    def _watch(self, proc: subprocess.Popen, on_stop_callback):
        stderr_output = ""
        try:
            _, stderr_bytes = proc.communicate()
            if stderr_bytes:
                stderr_output = stderr_bytes.decode(errors="replace").strip()
        except Exception:
            proc.wait()

        with self._lock:
            self._process = None

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
            except Exception:
                pass
