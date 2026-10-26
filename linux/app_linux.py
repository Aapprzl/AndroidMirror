from ui.app import AndroidMirrorApp
import os
import sys
from tkinter import PhotoImage


class LinuxAndroidMirrorApp(AndroidMirrorApp):
    """Linux-adapted version of AndroidMirrorApp.

    Overrides icon handling for Linux (uses .png + iconphoto instead of
    .ico + iconbitmap).  All other UI behaviour is inherited from the
    shared base class.
    """

    def _set_app_icon(self):
        icon_name = "icon.png"

        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_path = os.path.join(base_dir, icon_name)

        if os.path.exists(icon_path):
            try:
                self.iconphoto(True, PhotoImage(file=icon_path))
            except Exception as e:
                print(f"Error loading icon: {e}")
