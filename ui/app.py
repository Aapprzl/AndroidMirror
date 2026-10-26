import os
import sys
import customtkinter as ctk
from tkinter import font, messagebox

from core.adb_manager import ADBManager
from core.scrcpy_runner import ScrcpyRunner
from core import config_manager

class AndroidMirrorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("AndroidMirror")
        self.geometry("480x640")
        self.resizable(False, False)

        # Persistence
        self.config = config_manager.load_config()

        # State tracking
        self._is_streaming = False

        # Clean exit
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Set appearance mode and color theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")  # We'll customize the accent color below

        # Custom accent color
        self.accent_color = "#1f6feb"

        # Configure grid layout (3x3)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=0)  # Status panel
        self.grid_rowconfigure(2, weight=1)  # Center area
        self.grid_rowconfigure(3, weight=0)  # Recording toggle
        self.grid_rowconfigure(4, weight=0)  # Start button
        self.grid_rowconfigure(5, weight=0)  # Bottom buttons
        self.grid_rowconfigure(6, weight=0)  # Status bar

        # Create widgets
        self.create_header()
        self.create_status_panel()
        self.create_center_area()
        self.create_start_button()
        self.create_bottom_buttons()
        self.create_status_bar()

        # Current connected device serial (used to launch scrcpy)
        self._current_serial: str | None = None

        # Scrcpy runner (created once, reused)
        self._scrcpy = ScrcpyRunner(on_status=self._update_status_bar)

        # Start ADB background manager
        self._adb_manager = ADBManager(
            on_device_connected=self.set_device_connected,
            on_device_disconnected=self.set_device_disconnected,
            on_status=self._update_status_bar,
        )

        # Set Window Icon
        self._set_app_icon()

    def _set_app_icon(self):
        """Set the window icon for the application."""
        icon_name = "icon.ico"
        
        # Check if running as .exe (PyInstaller bundle)
        if getattr(sys, 'frozen', False):
            # Bundled data is in sys._MEIPASS
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            # Development mode
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_path = os.path.join(base_dir, icon_name)
        
        if os.path.exists(icon_path):
            try:
                # On Windows, iconbitmap works best
                self.iconbitmap(icon_path)
            except Exception as e:
                print(f"Error loading icon: {e}")

    def create_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        # Main title
        title_label = ctk.CTkLabel(
            header_frame,
            text="AndroidMirror",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.accent_color
        )
        title_label.grid(row=0, column=0, pady=(0, 5))

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="USB Screen Mirror",
            font=ctk.CTkFont(size=14),
            text_color="gray70"
        )
        subtitle_label.grid(row=1, column=0)

    def create_status_panel(self):
        # Status panel (rounded card)
        status_frame = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=("gray90", "gray20")  # light, dark
        )
        status_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        # Status content
        status_content = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_content.grid(row=0, column=0, padx=15, pady=15)
        status_content.grid_columnconfigure(0, weight=1)

        # Indicator circle (red for disconnected)
        self.indicator_canvas = ctk.CTkCanvas(
            status_content,
            width=16,
            height=16,
            highlightthickness=0,
            bg=status_frame._fg_color[1] if ctk.get_appearance_mode() == "Dark" else status_frame._fg_color[0]
        )
        self.indicator_canvas.grid(row=0, column=0, padx=(0, 12), pady=(4, 0), sticky="n")
        self.indicator_canvas.create_oval(2, 2, 14, 14, fill="#ff4444", outline="")

        # Status text (Device Model)
        self.status_text = ctk.CTkLabel(
            status_content,
            text="Tidak ada perangkat terdeteksi",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="gray70"
        )
        self.status_text.grid(row=0, column=1, sticky="w")

        # Device Info (Android, Battery, Temp)
        self.device_info_label = ctk.CTkLabel(
            status_content,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray50"
        )
        self.device_info_label.grid(row=1, column=1, sticky="w")

    def create_center_area(self):
        # Center area (rounded card)
        center_frame = ctk.CTkFrame(
            self,
            corner_radius=15,
            fg_color=("gray90", "gray20"),
            height=300
        )
        center_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        center_frame.grid_columnconfigure(0, weight=1)
        center_frame.grid_rowconfigure(0, weight=1)

        # Center content
        center_content = ctk.CTkFrame(center_frame, fg_color="transparent")
        center_content.grid(row=0, column=0, padx=20, pady=20)
        center_content.grid_columnconfigure(0, weight=1)

        # Phone icon
        phone_label = ctk.CTkLabel(
            center_content,
            text="📱",
            font=ctk.CTkFont(size=60),
            text_color="gray50"
        )
        phone_label.grid(row=0, column=0, pady=(0, 20))

        # Instruction text (dynamic)
        self.instruction_label = ctk.CTkLabel(
            center_content,
            text="Hubungkan HP via kabel USB\nlalu aktifkan USB Debugging",
            font=ctk.CTkFont(size=16),
            justify="center",
            text_color="gray60"
        )
        self.instruction_label.grid(row=1, column=0)

    def create_start_button(self):
        # Recording Switch Container
        record_frame = ctk.CTkFrame(self, fg_color="transparent")
        record_frame.grid(row=3, column=0, padx=40, pady=(10, 0), sticky="ew")
        record_frame.grid_columnconfigure(0, weight=1)

        self.record_switch = ctk.CTkSwitch(
            record_frame,
            text="Simpan Rekaman (.mkv)",
            font=ctk.CTkFont(size=14),
            progress_color=self.accent_color
        )
        self.record_switch.grid(row=0, column=0)
        self._add_tooltip(self.record_switch, "Gunakan .mkv agar rekaman tetap aman (tidak rusak) meski laptop/HP terputus mendadak")

        # Start button
        self.start_button = ctk.CTkButton(
            self,
            text="▶ Mulai Mirror",
            font=ctk.CTkFont(size=18, weight="bold"),
            corner_radius=10,
            height=50,
            fg_color=self.accent_color,
            hover_color="#165ac7",
            text_color="white",
            state="disabled",  # Initially disabled
            command=self._on_mirror_button_click,
        )
        self.start_button.grid(row=4, column=0, padx=40, pady=(10, 20), sticky="ew")
        
        # Tooltip
        self._add_tooltip(self.start_button, "Mulai menampilkan layar HP di laptop")

    def create_bottom_buttons(self):
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)

        # Settings button
        self.settings_button = ctk.CTkButton(
            bottom_frame,
            text="⚙ Pengaturan",
            font=ctk.CTkFont(size=14),
            corner_radius=8,
            height=35,
            fg_color="transparent",
            border_width=1,
            border_color="gray50",
            text_color="gray70",
            hover_color=("gray80", "gray20"),
            command=self._open_settings,
        )
        self.settings_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self._add_tooltip(self.settings_button, "Atur kualitas video dan preferensi")

        # Help button
        self.help_button = ctk.CTkButton(
            bottom_frame,
            text="? Bantuan",
            font=ctk.CTkFont(size=14),
            corner_radius=8,
            height=35,
            fg_color="transparent",
            border_width=1,
            border_color="gray50",
            text_color="gray70",
            hover_color=("gray80", "gray20"),
            command=self._open_help,
        )
        self.help_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        self._add_tooltip(self.help_button, "Panduan cara menggunakan aplikasi")

    def create_status_bar(self):
        self.status_label = ctk.CTkLabel(
            self,
            text="Siap",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray50"
        )
        self.status_label.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="w")

    # ------------------------------------------------------------------
    # Mirror button toggle
    # ------------------------------------------------------------------

    def _on_mirror_button_click(self):
        """Toggle mirror on/off when the main button is clicked."""
        if self._scrcpy.is_running():
            # --- Stop ---
            self._scrcpy.stop()
            self._set_idle_ui()
            self._update_status_bar("Mirror dihentikan.")
        else:
            # Prepare options (including recording)
            launch_options = self.config.copy()
            launch_options["record"] = self.record_switch.get()

            # --- Start ---
            serial = self._current_serial
            if not serial:
                self._update_status_bar("Tidak ada perangkat. Sambungkan HP terlebih dahulu.")
                return
            
            # Use real config
            self._set_streaming_ui()
            started = self._scrcpy.start(
                device_serial=serial,
                options=launch_options,
                on_stop_callback=self._on_scrcpy_stopped,
            )
            if not started:
                # start() already pushed an error to status bar
                self._set_idle_ui()
            else:
                self._is_streaming = True
                self._update_center_text()

    def _on_scrcpy_stopped(self):
        """Called by ScrcpyRunner watcher thread when scrcpy exits externally."""
        self._is_streaming = False
        # Schedule UI reset on main thread
        self.after(0, self._set_idle_ui)
        self.after(0, self._update_center_text)

    def _set_streaming_ui(self):
        """Switch button to Stop mode (called on main thread)."""
        text = "⏹ Stop Mirror"
        if self.record_switch.get():
            text = "⏹ Stop & Save Record"

        self.start_button.configure(
            text=text,
            fg_color="#cc2222",
            hover_color="#991111",
        )
        self.record_switch.configure(state="disabled")

    def _set_idle_ui(self):
        """Switch button back to Start mode (called on main thread)."""
        self._is_streaming = False
        # Only re-enable if a device is still connected
        state = "normal" if self._current_serial else "disabled"
        self.start_button.configure(
            text="▶ Mulai Mirror",
            fg_color=self.accent_color,
            hover_color="#165ac7",
            state=state,
        )
        self.record_switch.configure(state="normal")

    def _update_center_text(self):
        """Update instruction text based on the current state."""
        if self._is_streaming:
            status = "Sedang streaming..."
            if self.record_switch.get():
                status = "🔴 Sedang Rekam & Mirror..."
            
            self.instruction_label.configure(
                text=status,
                text_color="#44ff88"
            )
        elif self._current_serial:
            self.instruction_label.configure(
                text="Perangkat siap!\nKlik Mulai Mirror untuk memulai",
                text_color="#44ff88"
            )
        else:
            self.instruction_label.configure(
                text="Hubungkan HP via kabel USB\nlalu aktifkan USB Debugging",
                text_color="gray60"
            )

    # ------------------------------------------------------------------
    # Settings / Help / Lifecyle
    # ------------------------------------------------------------------

    def _open_settings(self):
        SettingsWindow(self)

    def _open_help(self):
        HelpWindow(self)

    def _on_closing(self):
        """Handle window close: stop background threads and subprocesses."""
        if hasattr(self, "_scrcpy"):
            self._scrcpy.stop()
        if hasattr(self, "_adb_manager"):
            self._adb_manager.stop()
        self.destroy()

    def _add_tooltip(self, widget, text):
        """Simple tooltip helper."""
        def enter(event):
            self._update_status_bar(text)
        def leave(event):
            self._update_status_bar("Siap" if not self._is_streaming else "Sedang streaming...")
        
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    # ------------------------------------------------------------------
    # ADB callbacks — called from background thread, must use self.after()
    # ------------------------------------------------------------------

    def set_device_connected(self, device_name: str):
        """Update UI to reflect a connected USB device."""
        from core.adb_manager import get_usb_serials, get_android_version
        try:
            serials = get_usb_serials()
            self._current_serial = serials[0] if serials else None
            android_ver = get_android_version(self._current_serial) if self._current_serial else "?"
        except Exception:
            self._current_serial = None
            android_ver = "?"

        def _update():
            self.indicator_canvas.delete("all")
            self.indicator_canvas.create_oval(2, 2, 14, 14, fill="#44ff88", outline="")
            self.status_text.configure(text=device_name, text_color="#44ff88")
            self.start_button.configure(state="normal")
            self._update_status_bar(f"Perangkat terhubung: {device_name}")
            self._update_center_text()
            
            # Show Android version immediately
            self.device_info_label.configure(text=f"Android {android_ver} | Menunggu data...")
            
            # Start periodic stats update
            self._update_device_stats()

        self.after(0, _update)

    def _update_device_stats(self):
        """Periodically refresh battery and temperature info."""
        if not self._current_serial:
            return

        from core.adb_manager import get_battery_info
        info = get_battery_info(self._current_serial)
        
        if info:
            level = info.get("level", "?")
            temp = info.get("temp", "?")
            
            # Get current text to keep Android version
            current_text = self.device_info_label.cget("text")
            android_part = current_text.split("|")[0].strip() if "|" in current_text else "Android"
            
            new_text = f"{android_part} | 🔋 {level}% | 🌡️ {temp}°C"
            self.device_info_label.configure(text=new_text)

        # Schedule next update in 10 seconds if still connected
        if self._current_serial:
            self.after(10000, self._update_device_stats)

    def set_device_disconnected(self):
        """Update UI to reflect that no USB device is connected."""
        self._current_serial = None
        # Stop scrcpy if it is running (cable pulled mid-session)
        if self._scrcpy.is_running():
            self._scrcpy.stop()

        def _update():
            self.indicator_canvas.delete("all")
            self.indicator_canvas.create_oval(2, 2, 18, 18, fill="#ff4444", outline="")
            self.status_text.configure(
                text="Tidak ada perangkat terdeteksi",
                text_color="gray70",
            )
            self.device_info_label.configure(text="")
            self.start_button.configure(
                text="▶ Mulai Mirror",
                fg_color=self.accent_color,
                hover_color="#165ac7",
                state="disabled",
            )
            self._update_status_bar("Siap — menunggu perangkat...")
            self._update_center_text()
        self.after(0, _update)

    def _update_status_bar(self, msg: str):
        """Thread-safe status bar update."""
        def _update():
            self.status_label.configure(text=msg)
        self.after(0, _update)

# ---------------------------------------------------------------------------
# Popup Windows
# ---------------------------------------------------------------------------

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Pengaturan Scrcpy")
        self.geometry("380x480")
        self.resizable(False, False)
        self.transient(parent)  # Stay on top of parent
        # Defer grab_set() until the window is actually visible to avoid
        # "grab failed: window not viewable" on some platforms.
        self.after(50, self.grab_set)
        
        # UI Setup
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        # 1. Bitrate Slider
        # Choices: 2M, 4M, 8M, 16M
        self.bitrate_map = ["2M", "4M", "8M", "16M"]
        current_bitrate = self.parent.config.get("bitrate", "8M")
        initial_bg_idx = self.bitrate_map.index(current_bitrate) if current_bitrate in self.bitrate_map else 2
        
        ctk.CTkLabel(main_frame, text="Bitrate Video:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.bitrate_label = ctk.CTkLabel(main_frame, text=current_bitrate)
        self.bitrate_label.grid(row=0, column=1, sticky="e")
        
        self.bitrate_slider = ctk.CTkSlider(
            main_frame, from_=0, to=3, number_of_steps=3,
            command=self._on_bitrate_change
        )
        self.bitrate_slider.set(initial_bg_idx)
        self.bitrate_slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 20))

        # 2. Max FPS Dropdown
        ctk.CTkLabel(main_frame, text="Max FPS:", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.fps_menu = ctk.CTkOptionMenu(main_frame, values=["30", "60"])
        self.fps_menu.set(str(self.parent.config.get("fps", 60)))
        self.fps_menu.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 20))

        # 3. Toggles
        self.always_on_top_var = ctk.BooleanVar(value=self.parent.config.get("always_on_top", False))
        ctk.CTkSwitch(main_frame, text="Selalu di Atas", variable=self.always_on_top_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)
        
        self.turn_screen_off_var = ctk.BooleanVar(value=self.parent.config.get("turn_screen_off", False))
        ctk.CTkSwitch(main_frame, text="Matikan Layar HP", variable=self.turn_screen_off_var).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        
        self.stay_awake_var = ctk.BooleanVar(value=self.parent.config.get("stay_awake", False))
        ctk.CTkSwitch(main_frame, text="Cegah HP Sleep", variable=self.stay_awake_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)

        self.fullscreen_var = ctk.BooleanVar(value=self.parent.config.get("fullscreen", False))
        ctk.CTkSwitch(main_frame, text="Layar Penuh (Fullscreen)", variable=self.fullscreen_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=(5, 30))

        # 4. Action Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=8, column=0, columnspan=2, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(button_frame, text="💾 Simpan", command=self._save, fg_color="#1f6feb").grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(button_frame, text="✖ Batal", command=self.destroy, fg_color="gray30").grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _on_bitrate_change(self, val):
        idx = int(val)
        self.bitrate_label.configure(text=self.bitrate_map[idx])

    def _save(self):
        new_config = {
            "bitrate": self.bitrate_map[int(self.bitrate_slider.get())],
            "fps": int(self.fps_menu.get()),
            "always_on_top": self.always_on_top_var.get(),
            "turn_screen_off": self.turn_screen_off_var.get(),
            "stay_awake": self.stay_awake_var.get(),
            "fullscreen": self.fullscreen_var.get()
        }
        self.parent.config.update(new_config)
        config_manager.save_config(self.parent.config)
        self.parent._update_status_bar("Konfigurasi disimpan.")
        self.destroy()

class HelpWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Bantuan AndroidMirror")
        self.geometry("400x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main_frame, text="Cara Menggunakan AndroidMirror", font=ctk.CTkFont(size=20, weight="bold"), text_color="#1f6feb").grid(row=0, column=0, pady=(0, 20))

        instructions = [
            "1. Aktifkan USB Debugging di HP",
            "2. Hubungkan HP via kabel USB",
            "3. Klik Mulai Mirror"
        ]
        
        for i, text in enumerate(instructions):
            ctk.CTkLabel(main_frame, text=text, font=ctk.CTkFont(size=15)).grid(row=i+1, column=0, sticky="w", pady=5)

        note_box = ctk.CTkFrame(main_frame, corner_radius=10, fg_color=("gray85", "gray15"))
        note_box.grid(row=4, column=0, pady=(20, 20), sticky="ew")
        
        ctk.CTkLabel(note_box, text="Catatan Samsung:", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(10, 0), anchor="w")
        ctk.CTkLabel(note_box, text="Settings → About Phone → Software Info\ntap Build Number 7x → Developer Options\n→ Aktifkan USB Debugging.", justify="left", font=ctk.CTkFont(size=12)).pack(padx=10, pady=(0, 10), anchor="w")

        ctk.CTkButton(main_frame, text="Tutup", command=self.destroy).grid(row=5, column=0, pady=(10, 0))

if __name__ == "__main__":
    app = AndroidMirrorApp()
    app.mainloop()