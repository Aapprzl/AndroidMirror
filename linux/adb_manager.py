import os
import re
import stat
import subprocess
import threading
import time
import zipfile

import urllib.request

import sys

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ADB_DIR     = os.path.join(_BASE_DIR, "bin", "adb")
_PT_DIR      = os.path.join(_ADB_DIR, "platform-tools")
_ADB_EXE     = os.path.join(_PT_DIR, "adb")
_ADB_ZIP_URL = (
    "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
)
_ADB_ZIP_TMP = os.path.join(_ADB_DIR, "platform-tools-latest-linux.zip")

ADB_TIMEOUT = 30


def _run_adb(*args, timeout: int = ADB_TIMEOUT) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [_ADB_EXE, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out"
    except FileNotFoundError:
        return False, "adb not found"
    except Exception as exc:
        return False, str(exc)


def _download_with_progress(url: str, dest: str, on_status=None) -> None:
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


def _make_executable(path: str):
    """Set execute permission for the owner on *path*."""
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def is_adb_available() -> bool:
    return os.path.isfile(_ADB_EXE)


def ensure_adb(on_status=None) -> bool:
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

        try:
            os.remove(_ADB_ZIP_TMP)
        except OSError:
            pass

        _make_executable(_ADB_EXE)

        if is_adb_available():
            if on_status:
                on_status("ADB siap digunakan.")
            return True

        if on_status:
            on_status("Gagal mengunduh ADB. Periksa koneksi internet Anda.")
        return False

    except Exception as exc:
        print(f"[ADBManager] Download error: {exc}")
        if on_status:
            on_status("Gagal mengunduh ADB. Periksa koneksi internet Anda.")
        try:
            os.remove(_ADB_ZIP_TMP)
        except OSError:
            pass
        return False


def get_usb_serials() -> list[str]:
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
    ok, output = _run_adb("devices", "-l")
    if not ok:
        return []

    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial, state = parts[0], parts[1]

        if ":" in serial:
            continue

        if state not in ("device",):
            continue

        ok_model, model = _run_adb("-s", serial, "shell", "getprop", "ro.product.model", timeout=10)
        if ok_model and model:
            ok_brand, brand = _run_adb("-s", serial, "shell", "getprop", "ro.product.brand", timeout=10)
            if ok_brand and brand:
                brand = brand.strip().title()
                model = model.strip()
                if not model.lower().startswith(brand.lower()):
                    model = f"{brand} {model}"
            devices.append(model.strip())
        else:
            devices.append(serial)

    return devices


def get_battery_info(serial: str) -> dict:
    ok, output = _run_adb("-s", serial, "shell", "dumpsys", "battery")
    if not ok:
        return {}

    info = {}
    level_match = re.search(r"level:\s+(\d+)", output)
    if level_match:
        info["level"] = int(level_match.group(1))

    temp_match = re.search(r"temperature:\s+(\d+)", output)
    if temp_match:
        info["temp"] = float(temp_match.group(1)) / 10.0

    return info


def get_android_version(serial: str) -> str:
    ok, version = _run_adb("-s", serial, "shell", "getprop", "ro.build.version.release")
    return version if ok else "Unknown"


class ADBManager:
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

        self._thread = threading.Thread(
            target=self._run, name="ADBPollingThread", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _status(self, msg: str):
        if self._on_status:
            try:
                self._on_status(msg)
            except Exception:
                pass

    def _run(self):
        self._adb_ready = ensure_adb(on_status=self._status)

        if not self._adb_ready:
            return

        self._status("Siap — menunggu perangkat...")

        _run_adb("start-server")

        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as exc:
                print(f"[ADBManager] Poll error: {exc}")
            self._stop_event.wait(self._interval)

    def _poll(self):
        devices = get_usb_devices()
        device_set = set(devices)

        new_devices = device_set - self._current_devices
        for name in new_devices:
            self._current_devices.add(name)
            try:
                self._on_connected(name)
            except Exception as exc:
                print(f"[ADBManager] on_connected error: {exc}")

        removed = self._current_devices - device_set
        if removed:
            self._current_devices -= removed
            if not self._current_devices:
                try:
                    self._on_disconnected()
                except Exception as exc:
                    print(f"[ADBManager] on_disconnected error: {exc}")
