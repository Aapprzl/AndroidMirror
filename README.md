# AndroidMirror

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-0078d7.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**AndroidMirror** is a professional desktop application designed to mirror your Android screen to your PC via USB. Built with a focus on ease of use and performance, it is an ideal tool for mobile gamers, educators, and live streamers (e.g., using OBS).

---

## [Screenshot / Preview Placeholder]
*Visual preview of the dark mode UI with device connected and streaming.*

---

## 🚀 Key Features

- 🔌 **Instant Detection**: Automatically detects Android devices as soon as they are plugged in via USB.
- 📺 **High Performance**: Powered by `scrcpy` for low-latency, high-resolution mirroring (up to 16M bitrate and 60 FPS).
- 🔊 **Audio Support**: Stream device audio directly to your PC (Android 11+).
- ⚙️ **Customizable settings**: Easily adjust bitrate, max FPS, and scrcpy flags through a dedicated settings popup.
- 🌙 **Modern Dark Mode**: Sleek and professional UI built with CustomTkinter.
- 💾 **Persistent Config**: Remembers your preferred video settings between sessions.
- ✅ **One-Click Experience**: No manual ADB command entry required; the app handles everything.

---

## 🛠 Installation & Usage

### For End Users
Currently supported on **Windows 10/11**.
1. Go to the [Releases](https://github.com/ZENBOOK/AndroidMirror/releases) page.
2. Download the latest `AndroidMirror.zip`.
3. Extract and run `AndroidMirror.exe`.

### For Developers
1. **Clone the repository**:
   ```bash
   git clone https://github.com/ZENBOOK/AndroidMirror.git
   cd AndroidMirror
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**:
   ```bash
   python main.py
   ```

---

## 📋 Prerequisites

To use AndroidMirror, ensure your environment meets these requirements:
- **Operating System**: Windows 10 or 11.
- **Android Device**: USB Debugging must be enabled (see instructions below).
- **Cables**: Use a high-quality USB Data Cable (avoid "charge-only" cables).

---

## 📱 Enabling USB Debugging (Samsung / Standard)

1. Open **Settings** on your phone.
2. Go to **About Phone** → **Software Information**.
3. Tap **Build Number** 7 times until "Developer mode has been turned on" appears.
4. Go back to **Settings** → **Developer Options**.
5. Find and enable **USB Debugging**.
6. When prompted on the device after connecting to PC, allow the connection.

---

## 💻 Powered By

- [scrcpy](https://github.com/Genymobile/scrcpy) - High-performance screen mirroring.
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI library for Python.
- [ADB (Android Debug Bridge)](https://developer.android.com/studio/command-line/adb) - Device communication.
- [PyInstaller](https://pyinstaller.org/) - For building the standalone executable.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---
*Tested on Samsung Galaxy A56 (SM-A566B) | Windows 11*
