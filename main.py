import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting AndroidMirror...")

if sys.platform == "linux":
    # -------------------------------------------------------------------
    # Linux path — override core modules with Linux-specific versions
    # so that ui/app.py's imports (from core.adb_manager, etc.) resolve
    # to the Linux implementations.
    # -------------------------------------------------------------------
    import linux.adb_manager
    import linux.scrcpy_runner
    import core.config_manager  # OS-independent, shared

    sys.modules["core.adb_manager"]    = linux.adb_manager
    sys.modules["core.scrcpy_runner"]  = linux.scrcpy_runner
    sys.modules["core.config_manager"] = core.config_manager

    from linux.app_linux import LinuxAndroidMirrorApp as AppClass
else:
    # -------------------------------------------------------------------
    # Windows path — use the existing core/ modules as-is.
    # -------------------------------------------------------------------
    from ui.app import AndroidMirrorApp as AppClass

if __name__ == "__main__":
    app = AppClass()
    app.mainloop()