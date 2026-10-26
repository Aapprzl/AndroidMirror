"""
core/adb_manager.py
Handles ADB (Android Debug Bridge) for USB device detection.

Features:
- Auto-download platform-tools for Windows if not present
- USB-only device scanning (no Wi-Fi adb)
- Background thread polling every 2 seconds
- Callback-based UI updates (thread-safe)
- 30-second timeout on all ADB commands
"""

import os
import re
import subprocess
import threading
import time
import zipfile

import urllib.request

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

_ADB_DIR     = os.path.join(_BASE_DIR, "bin", "adb")
_PT_DIR      = os.path.join(_ADB_DIR, "platform-tools")
_ADB_EXE     = os.path.join(_PT_DIR, "adb.exe")
_ADB_ZIP_URL = (
    "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)
_ADB_ZIP_TMP = os.path.join(_ADB_DIR, "platform-tools-latest-windows.zip")

# ---------------------------------------------------------------------------
# ADB timeout (seconds) for every subprocess call
# ---------------------------------------------------------------------------
ADB_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_adb(*args, timeout: int = ADB_TIMEOUT) -> tuple[bool, str]:
    """
    Run an ADB command and return (success, output).
    Returns (False, error_message) on failure or timeout.
    """
    try:
        result = subprocess.run(
            [_ADB_EXE, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,  # hide console window on Windows
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out"
    except FileNotFoundError:
        return False, "adb.exe not found"
    except Exception as exc:
        return False, str(exc)


def _download_with_progress(url: str, dest: str, on_status=None) -> None:
    """
    Download *url* to *dest*, calling on_status(msg) with progress updates.
    Raises an exception on failure.
    """
    def _report(block_count, block_size, total_size):
        if total_size > 0 and on_status:
            downloaded = min(block_count * block_size, total_size)
            pct = int(downloaded * 100 / total_size)
            mb = downloaded / (1024 * 1024)
            on_status(f"Mengunduh ADB tools... {pct}% ({mb:.1f} MB)")

    if on_status:
        on_status("Mengunduh ADB tools... harap tunggu")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest, reporthook=_report)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_adb_available() -> bool:
    """Return True if adb.exe exists at the expected location."""
    return os.path.isfile(_ADB_EXE)


def ensure_adb(on_status=None) -> bool:
    """
    Make sure ADB is available.
    Downloads and extracts platform-tools if missing.

    Parameters
    ----------
    on_status : callable(str) | None
        Called with a human-readable status message (for the UI status bar).

    Returns
    -------
    bool
        True  – ADB is ready.
        False – Download failed; caller should show an error to the user.
    """
    if is_adb_available():
        return True

    try:
        if on_status:
            on_status("Mengunduh ADB tools... harap tunggu")

        _download_with_progress(_ADB_ZIP_URL, _ADB_ZIP_TMP, on_status)

        if on_status:
            on_status("Mengekstrak ADB tools...")

        os.makedirs(_ADB_DIR, exist_ok=True)
        with zipfile.ZipFile(_ADB_ZIP_TMP, "r") as zf:
            zf.extractall(_ADB_DIR)

        # Clean up zip
        try:
            os.remove(_ADB_ZIP_TMP)
        except OSError:
            pass

        if is_adb_available():
            if on_status:
                on_status("ADB siap digunakan.")
            return True

        if on_status:
            on_status("Gagal mengunduh ADB. Periksa koneksi internet Anda.")
        return False

    except Exception as exc:  # noqa: BLE001
        print(f"[ADBManager] Download error: {exc}")
        if on_status:
            on_status("Gagal mengunduh ADB. Periksa koneksi internet Anda.")
        # Remove partial zip if any
        try:
            os.remove(_ADB_ZIP_TMP)
        except OSError:
            pass
        return False


def get_usb_serials() -> list[str]:
    """
    Return the ADB serial numbers of all USB-connected authorised devices.
    Wi-Fi ADB entries (containing ':') are excluded.
    """
    ok, output = _run_adb("devices")
    if not ok:
        return []
    serials = []
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device" and ":" not in parts[0]:
            serials.append(parts[0])
    return serials


def get_usb_devices() -> list[str]:
    """
    Return a list of model names for USB-connected Android devices.

    Wi-Fi ADB connections (host:port format, e.g. 192.168.x.x:5555) are
    intentionally excluded.

    Example return value: ["Samsung Galaxy A56", "Xiaomi Redmi Note 12"]
    """
    ok, output = _run_adb("devices", "-l")
    if not ok:
        return []

    devices = []
    for line in output.splitlines():
        line = line.strip()
        # Skip header and empty lines
        if not line or line.startswith("List of devices"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial, state = parts[0], parts[1]

        # Skip Wi-Fi ADB entries (contain ':' in serial, typically port 5555)
        if ":" in serial:
            continue

        # Only handle fully authorised/online devices
        if state not in ("device",):
            continue

        # Fetch human-readable model name
        ok_model, model = _run_adb("-s", serial, "shell", "getprop", "ro.product.model", timeout=10)
        if ok_model and model:
            # Also try brand for a nicer name, e.g. "Samsung Galaxy A56"
            ok_brand, brand = _run_adb("-s", serial, "shell", "getprop", "ro.product.brand", timeout=10)
            if ok_brand and brand:
                brand = brand.strip().title()
                model = model.strip()
                # Avoid duplicating brand in model name
                if not model.lower().startswith(brand.lower()):
                    model = f"{brand} {model}"
            devices.append(model.strip())
        else:
            # Fallback to serial number if model unavailable
            devices.append(serial)

    return devices


def get_battery_info(serial: str) -> dict:
    """
    Return a dictionary with 'level' (%) and 'temp' (°C) for the given serial.
    Returns empty dict on failure.
    """
    ok, output = _run_adb("-s", serial, "shell", "dumpsys", "battery")
    if not ok:
        return {}

    info = {}
    # level: 100
    level_match = re.search(r"level:\s+(\d+)", output)
    if level_match:
        info["level"] = int(level_match.group(1))

    # temperature: 305 (means 30.5°C)
    temp_match = re.search(r"temperature:\s+(\d+)", output)
    if temp_match:
        info["temp"] = float(temp_match.group(1)) / 10.0

    return info


def get_android_version(serial: str) -> str:
    """Return the Android version string (e.g. '13', '14') for the given serial."""
    ok, version = _run_adb("-s", serial, "shell", "getprop", "ro.build.version.release")
    return version if ok else "Unknown"


# ---------------------------------------------------------------------------
# Background manager class
# ---------------------------------------------------------------------------

class ADBManager:
    """
    Polls for USB Android devices every *interval* seconds in a daemon thread.

    Parameters
    ----------
    on_device_connected    : callable(device_name: str)
        Called when a new device appears.  Receives the model name string.
    on_device_disconnected : callable()
        Called when all devices are removed.
    on_status              : callable(msg: str)
        Called with status messages (e.g. ADB download progress).
    interval               : float
        Poll interval in seconds (default 2).
    """

    def __init__(
        self,
        on_device_connected,
        on_device_disconnected,
        on_status=None,
        interval: float = 2.0,
    ):
        self._on_connected    = on_device_connected
        self._on_disconnected = on_device_disconnected
        self._on_status       = on_status
        self._interval        = interval

        self._current_devices: set[str] = set()
        self._adb_ready        = False
        self._stop_event       = threading.Event()

        # Daemon thread – dies automatically when main thread exits
        self._thread = threading.Thread(
            target=self._run, name="ADBPollingThread", daemon=True
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def stop(self):
        """Signal the polling thread to stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _status(self, msg: str):
        if self._on_status:
            try:
                self._on_status(msg)
            except Exception:  # noqa: BLE001
                pass

    def _run(self):
        """Main loop running inside the daemon thread."""
        # Step 1 – ensure ADB is present (may download)
        self._adb_ready = ensure_adb(on_status=self._status)

        if not self._adb_ready:
            # on_status already called with error message by ensure_adb()
            return

        self._status("Siap — menunggu perangkat...")

        # Step 2 – start ADB server quietly
        _run_adb("start-server")

        # Step 3 – poll
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as exc:  # noqa: BLE001
                print(f"[ADBManager] Poll error: {exc}")
            self._stop_event.wait(self._interval)

    def _poll(self):
        devices = get_usb_devices()
        device_set = set(devices)

        # New devices connected
        new_devices = device_set - self._current_devices
        for name in new_devices:
            self._current_devices.add(name)
            try:
                self._on_connected(name)
            except Exception as exc:  # noqa: BLE001
                print(f"[ADBManager] on_connected error: {exc}")

        # Devices removed
        removed = self._current_devices - device_set
        if removed:
            self._current_devices -= removed
            if not self._current_devices:
                # All devices gone
                try:
                    self._on_disconnected()
                except Exception as exc:  # noqa: BLE001
                    print(f"[ADBManager] on_disconnected error: {exc}")
