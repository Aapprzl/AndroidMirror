"""
core/config_manager.py
Handles loading and saving of configuration settings for AndroidMirror.
"""

import json
import os

import sys
if getattr(sys, 'frozen', False):
    # If running as .exe, use the .exe directory
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # If running as script, use the project root
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "bitrate": "8M",
    "fps": 60,
    "always_on_top": False,
    "turn_screen_off": False,
    "stay_awake": False,
    "fullscreen": False
}

def load_config():
    """Load configuration from config.json, returning defaults if not found or invalid."""
    if not os.path.exists(_CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(_CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Merge with defaults to ensure all keys exist
            full_config = DEFAULT_CONFIG.copy()
            full_config.update(config)
            return full_config
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ConfigManager] Error loading config: {exc}")
        return DEFAULT_CONFIG.copy()

def save_config(config_data):
    """Save configuration data to config.json."""
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
        return True
    except OSError as exc:
        print(f"[ConfigManager] Error saving config: {exc}")
        return False
