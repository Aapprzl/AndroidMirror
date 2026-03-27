import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting AndroidMirror...")
from ui.app import AndroidMirrorApp

if __name__ == "__main__":
    app = AndroidMirrorApp()
    app.mainloop()