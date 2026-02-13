"""
Personal Voice Assistant

FRIDAY/JARVIS-inspired CustomTkinter UI + local voice control + a couple of
practical automations:
- Download a YouTube video/audio (via yt-dlp)
- Move folders between locations
"""

from __future__ import annotations

import ctypes
import datetime
import json
import secrets
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from tkinter import filedialog, messagebox
from io import BytesIO

# Optional window-management imports for a Jarvis-style dashboard
try:
    import pygetwindow as gw
except Exception:
    gw = None

# Suppress ALSA/JACK library warnings in the console (Linux)
def py_error_handler(filename, line, function, err, fmt):
    pass


ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(
    None,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
)
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

try:
    asound = ctypes.cdll.LoadLibrary("libasound.so.2")
    asound.snd_lib_error_set_handler(c_error_handler)
except Exception:
    pass

try:
    import customtkinter as ctk
except Exception:
    ctk = None

try:
    from lib.voice_engine import VoiceEngine
except Exception as e:
    VoiceEngine = None  # type: ignore[assignment]
    _voice_engine_import_error = e

try:
    from lib.command_processor import CommandProcessor
except Exception as e:
    CommandProcessor = None  # type: ignore[assignment]
    _command_processor_import_error = e

try:
    from lib.gesture_controller import GestureController
except Exception:
    GestureController = None  # type: ignore[assignment]

# If you want to run without audio (CI/headless) set:
#   FRIDAY_HEADLESS=1  or FRIDAY_DISABLE_AUDIO_WARNINGS=1
_FRIDAY_HEADLESS = (
    os.environ.get("FRIDAY_HEADLESS") == "1"
    or os.environ.get("FRIDAY_DISABLE_AUDIO_WARNINGS") == "1"
)
if _FRIDAY_HEADLESS:
    os.environ["SDL_AUDIODRIVER"] = "dummy"

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
_stderr_null = None
if _FRIDAY_HEADLESS:
    _stderr_null = open(os.devnull, "w")
    sys.stderr = _stderr_null

import pygame

try:
    import psutil  # type: ignore
except Exception:
    psutil = None

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore[assignment]

try:
    from flask import Flask, Response, request  # type: ignore
except Exception:
    Flask = None  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]


@dataclass(frozen=True)
class FridayColors:
    bg: str = "#050816"
    panel: str = "#081229"
    panel_2: str = "#0b1633"
    accent: str = "#00e5ff"
    accent_2: str = "#00ffae"
    text: str = "#e0f7fa"
    muted: str = "#93a4b8"
    danger: str = "#ff1744"
    ok: str = "#00c853"
    warn: str = "#f39c12"


class _FallbackCommandProcessor:
    def __init__(self, voice_engine: object, import_error: Exception):
        self.voice_engine = voice_engine
        self.import_error = import_error

    def process(self, command: str) -> bool:
        return False


def _get_local_ip() -> str:
    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class FridayGUI:
    """FRIDAY-like desktop console using CustomTkinter."""

    def __init__(self):
        if ctk is None:
            raise RuntimeError(
                "customtkinter is not installed. Install it with: pip install customtkinter"
            )
        if VoiceEngine is None:
            raise RuntimeError(
                f"VoiceEngine failed to import: {_voice_engine_import_error}. "
                "Install dependencies from requirements.txt."
            )

        self.colors = FridayColors()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("FRIDAY")
        self.root.geometry("1200x720")
        self.root.minsize(1100, 650)
        self.root.configure(fg_color=self.colors.bg)
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)

        self.is_listening = False
        self.is_hidden = False
        self.wake_word_enabled = True

        self._window_handles: list[object] = []
        self._download_thread: threading.Thread | None = None
        self._move_thread: threading.Thread | None = None
        self._voice_form: dict | None = None
        self._yt_queue: list[dict] = []
        self._yt_queue_lock = threading.Lock()
        self._last_download_path: str | None = None
        self.limited_mode = False
        self.command_processor_error: str | None = None
        self._config_base_path = os.path.join(os.path.dirname(__file__), "config.json")
        self._config_user_path = os.path.join(os.path.dirname(__file__), "config.user.json")
        self._config = self._load_config()
        self._pending_config_write = False
        self._cmd_history: list[str] = []
        self._cmd_history_idx: int | None = None
        self._camera_preview_stop = threading.Event()
        self._camera_preview_thread: threading.Thread | None = None
        self._camera_preview_cap = None
        self._camera_preview_lock = threading.Lock()
        self._camera_preview_pil = None
        self._camera_preview_photo = None
        self._camera_preview_ctk_img = None
        self._gesture_model_path = os.path.join(
            os.path.dirname(__file__), "models", "hand_landmarker.task"
        )
        self._mouse_control_enabled = ctk.BooleanVar(value=False)
        self._window_move_enabled = ctk.BooleanVar(value=False)
        self._close_window_enabled = ctk.BooleanVar(value=False)
        self._screenshot_enabled = ctk.BooleanVar(value=False)
        self._fist_action = ctk.StringVar(value="Stop listening")
        self._mouse_smooth = {"x": None, "y": None}
        self._window_drag = {"active": False, "win": None, "dx": 0, "dy": 0}

        self.voice_engine = VoiceEngine()
        try:
            from lib.memory_store import FridayMemory

            memory_store = FridayMemory()
        except Exception:
            memory_store = None

        if CommandProcessor is None:
            self.limited_mode = True
            self.command_processor_error = str(_command_processor_import_error)
            self.command_processor = _FallbackCommandProcessor(
                self.voice_engine, _command_processor_import_error
            )  # type: ignore[arg-type]
        else:
            self.command_processor = CommandProcessor(self.voice_engine, memory_store)

        self.gesture_controller = None
        self._gesture_status = ctk.StringVar(value="Gestures: not started")
        self._last_gesture = ctk.StringVar(value="Last gesture: —")

        self._build_ui()
        self.update_voice_settings()

        try:
            pygame.mixer.music.set_volume(1.0)
        except Exception:
            pass

        threading.Thread(target=self.background_listener, daemon=True).start()
        self.root.after(400, self._startup_greeting)

    def on_app_close(self):
        try:
            self.stop_share_server()
        except Exception:
            pass
        try:
            self.stop_camera_preview()
        except Exception:
            pass
        try:
            self.stop_gestures()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _load_config(self) -> dict:
        def deep_merge(a: dict, b: dict) -> dict:
            out = dict(a)
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(out.get(k), dict):
                    out[k] = deep_merge(out[k], v)
                else:
                    out[k] = v
            return out

        base = {}
        user = {}
        try:
            with open(self._config_base_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    base = data
        except Exception:
            base = {}

        try:
            if os.path.exists(self._config_user_path):
                with open(self._config_user_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        user = data
        except Exception:
            user = {}

        return deep_merge(base, user)

    def _get_config(self, *path, default=None):
        node = self._config
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def _set_config(self, *path, value):
        if not path:
            return
        node = self._config
        for key in path[:-1]:
            if key not in node or not isinstance(node.get(key), dict):
                node[key] = {}
            node = node[key]
        node[path[-1]] = value

    def _schedule_config_write(self):
        if self._pending_config_write:
            return
        self._pending_config_write = True
        self.root.after(900, self._write_config_now)

    def _write_config_now(self):
        self._pending_config_write = False
        try:
            tmp = f"{self._config_user_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, self._config_user_path)
            self.log("Config saved.")
        except Exception as e:
            self.log(f"Config save failed: {e}")

    def _startup_greeting(self):
        try:
            import random

            greetings = [
                "FRIDAY online and standing by.",
                "All systems are up. How can I help?",
                "Systems online. I'm ready.",
            ]
            self.voice_engine.speak(random.choice(greetings))
        except Exception:
            pass

    # ---------------------------
    # UI
    # ---------------------------
    def _build_ui(self):
        header = ctk.CTkFrame(self.root, fg_color=self.colors.bg, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        header_inner = ctk.CTkFrame(header, fg_color=self.colors.bg, corner_radius=0)
        header_inner.pack(fill="x", padx=18, pady=(12, 6))

        # CustomTkinter doesn't ship a canvas; use a Tk canvas inside a CTkFrame.
        self.orb_canvas = self._tk_canvas(
            header_inner, width=64, height=64, bg=self.colors.bg
        )
        self.orb_canvas.pack(side="left", padx=(0, 14), pady=0)
        self._init_orb_visual()

        title = ctk.CTkLabel(
            header_inner,
            text="FRIDAY // INTERACTIVE CONSOLE",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=22, weight="bold"),
        )
        title.pack(side="left", pady=0)

        status_right = ctk.CTkFrame(header_inner, fg_color="transparent")
        status_right.pack(side="right", fill="x", expand=False)

        self.ind_move = ctk.CTkLabel(
            status_right,
            text="● MOVE",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.ind_move.pack(side="right", padx=(12, 0))

        self.ind_dl = ctk.CTkLabel(
            status_right,
            text="● DL",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.ind_dl.pack(side="right", padx=(12, 0))

        self.ind_listen = ctk.CTkLabel(
            status_right,
            text="● LISTEN",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.ind_listen.pack(side="right", padx=(12, 0))

        mode_text = "LIMITED MODE" if self.limited_mode else "FULL MODE"
        mode_color = self.colors.warn if self.limited_mode else self.colors.ok
        self.mode_label = ctk.CTkLabel(
            status_right,
            text=mode_text,
            text_color=mode_color,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.mode_label.pack(side="right", padx=(12, 0))

        if self.limited_mode:
            fix_btn = ctk.CTkButton(
                status_right,
                text="FIX DEPS",
                command=self.show_dependency_help,
                fg_color="#1b2735",
                hover_color="#24384e",
                text_color=self.colors.text,
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                width=110,
                height=30,
            )
            fix_btn.pack(side="right", padx=(0, 10))

        self._refresh_indicators()

        controls = ctk.CTkFrame(self.root, fg_color=self.colors.bg, corner_radius=0)
        controls.pack(fill="x", padx=18, pady=(6, 10))

        self.listen_button = ctk.CTkButton(
            controls,
            text="▶ LISTEN",
            command=self.start_listening,
            fg_color=self.colors.ok,
            text_color=self.colors.bg,
            hover_color="#1fe27a",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            width=140,
            height=36,
        )
        self.listen_button.pack(side="left", padx=(0, 10))

        self.stop_button = ctk.CTkButton(
            controls,
            text="■ STOP",
            command=self.stop_listening,
            fg_color=self.colors.danger,
            text_color=self.colors.bg,
            hover_color="#ff4a68",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            width=140,
            height=36,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(0, 10))

        clear_button = ctk.CTkButton(
            controls,
            text="CLR LOG",
            command=self.clear_log,
            fg_color="#263238",
            text_color=self.colors.text,
            hover_color="#33424a",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=36,
        )
        clear_button.pack(side="left", padx=(0, 10))

        export_button = ctk.CTkButton(
            controls,
            text="EXPORT LOG",
            command=self.export_log,
            fg_color="#263238",
            text_color=self.colors.text,
            hover_color="#33424a",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=140,
            height=36,
        )
        export_button.pack(side="left", padx=(0, 10))

        help_button = ctk.CTkButton(
            controls,
            text="HELP",
            command=self.show_help,
            fg_color="#2962ff",
            text_color="#e3f2fd",
            hover_color="#4478ff",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=100,
            height=36,
        )
        help_button.pack(side="left", padx=(0, 10))

        hide_button = ctk.CTkButton(
            controls,
            text="HIDE",
            command=self.hide_interface,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=90,
            height=36,
        )
        hide_button.pack(side="left", padx=(0, 10))

        self._wake_var = ctk.BooleanVar(value=True)
        wake_switch = ctk.CTkSwitch(
            controls,
            text="WAKE WORD",
            variable=self._wake_var,
            command=self.toggle_wake_word,
            fg_color="#1b2735",
            progress_color=self.colors.accent,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        wake_switch.pack(side="left", padx=(0, 10))

        self._chatbot_var = ctk.BooleanVar(value=False)
        self.chatbot_switch = ctk.CTkSwitch(
            controls,
            text="CHATBOT",
            variable=self._chatbot_var,
            command=self.toggle_chatbot,
            fg_color="#1b2735",
            progress_color=self.colors.accent,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.chatbot_switch.pack(side="left", padx=(8, 10))

        voice_panel = ctk.CTkFrame(self.root, fg_color=self.colors.panel, corner_radius=12)
        voice_panel.pack(fill="x", padx=18, pady=(0, 10))

        voice_title = ctk.CTkLabel(
            voice_panel,
            text="AUDIO / VOICE CONTROL",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        voice_title.pack(anchor="w", padx=12, pady=(10, 2))

        sliders = ctk.CTkFrame(voice_panel, fg_color="transparent")
        sliders.pack(fill="x", padx=12, pady=(4, 10))

        cfg_speed = self._get_config("assistant", "voice_speed", default=150)
        try:
            cfg_speed = int(cfg_speed)
        except Exception:
            cfg_speed = 150
        self.speed_var = ctk.IntVar(value=cfg_speed)
        ctk.CTkLabel(
            sliders,
            text="Voice Speed",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=10),
        ).pack(side="left", padx=(0, 8))
        self.speed_scale = ctk.CTkSlider(
            sliders,
            from_=50,
            to=300,
            number_of_steps=250,
            variable=self.speed_var,
            command=lambda _: self.update_voice_settings(),
        )
        self.speed_scale.pack(side="left", fill="x", expand=True, padx=(0, 18))

        cfg_vol = self._get_config("assistant", "voice_volume", default=0.9)
        try:
            cfg_vol = float(cfg_vol)
        except Exception:
            cfg_vol = 0.9
        self.volume_var = ctk.DoubleVar(value=cfg_vol)
        ctk.CTkLabel(
            sliders,
            text="Volume",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=10),
        ).pack(side="left", padx=(0, 8))
        self.volume_scale = ctk.CTkSlider(
            sliders,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            variable=self.volume_var,
            command=lambda _: self.update_voice_settings(),
        )
        self.volume_scale.pack(side="left", fill="x", expand=True)

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right = ctk.CTkFrame(body, fg_color=self.colors.panel, corner_radius=12, width=280)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self.tabs = ctk.CTkTabview(
            left,
            fg_color=self.colors.panel,
            segmented_button_fg_color=self.colors.panel_2,
            segmented_button_selected_color=self.colors.accent,
            segmented_button_selected_hover_color=self.colors.accent,
            segmented_button_unselected_color=self.colors.panel_2,
        )
        self.tabs.pack(fill="both", expand=True)

        self.tab_console = self.tabs.add("Console")
        self.tab_commands = self.tabs.add("Commands")
        self.tab_system = self.tabs.add("System")
        self.tab_camera = self.tabs.add("Camera")
        self.tab_maps = self.tabs.add("Maps")
        self.tab_share = self.tabs.add("Share")
        self.tab_youtube = self.tabs.add("YouTube")
        self.tab_files = self.tabs.add("Files")

        self._build_console_tab(self.tab_console)
        self._build_commands_tab(self.tab_commands)
        self._build_system_tab(self.tab_system)
        self._build_camera_tab(self.tab_camera)
        self._build_maps_tab(self.tab_maps)
        self._build_share_tab(self.tab_share)
        self._build_youtube_tab(self.tab_youtube)
        self._build_files_tab(self.tab_files)
        self._build_windows_panel(right)

        status = ctk.CTkFrame(self.root, fg_color=self.colors.bg, corner_radius=0)
        status.pack(fill="x", side="bottom")
        self.status_label = ctk.CTkLabel(
            status,
            text="Ready",
            text_color=self.colors.ok,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.status_label.pack(anchor="w", padx=18, pady=(6, 10))

        self.root.bind("<space>", lambda e: self.start_listening())
        self.root.bind("<Escape>", lambda e: self.stop_listening())

        self.refresh_window_list()
        self._toast_widget = None

    def toast(self, message: str, level: str = "info", ms: int = 3200):
        try:
            if self._toast_widget and self._toast_widget.winfo_exists():
                self._toast_widget.destroy()
        except Exception:
            pass

        bg = self.colors.panel_2
        border = self.colors.accent
        text_color = self.colors.text
        if level == "ok":
            border = self.colors.ok
        elif level == "warn":
            border = self.colors.warn
        elif level == "error":
            border = self.colors.danger

        frame = ctk.CTkFrame(self.root, fg_color=bg, corner_radius=12, border_width=2, border_color=border)
        label = ctk.CTkLabel(
            frame,
            text=message,
            text_color=text_color,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            justify="left",
            wraplength=520,
        )
        label.pack(padx=14, pady=10)
        frame.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-18)
        self._toast_widget = frame

        def _hide():
            try:
                if frame.winfo_exists():
                    frame.destroy()
            except Exception:
                pass

        self.root.after(ms, _hide)

    def _build_console_tab(self, parent):
        ctk.CTkLabel(
            parent,
            text="SYSTEM BUS / EVENT STREAM",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.log_text = ctk.CTkTextbox(
            parent,
            fg_color=self.colors.bg,
            text_color=self.colors.accent_2,
            font=("Consolas", 11),
            corner_radius=10,
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.log_text.configure(state="disabled")

        cmd_row = ctk.CTkFrame(parent, fg_color="transparent")
        cmd_row.pack(fill="x", padx=12, pady=(0, 12))

        self.command_entry = ctk.CTkEntry(
            cmd_row,
            placeholder_text='Type a command… (try: download <url> or move "src" "dst")',
            fg_color="#000814",
            text_color=self.colors.text,
            placeholder_text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=36,
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.command_entry.bind("<Return>", lambda e: self.handle_text_command())
        self.command_entry.bind("<Up>", lambda e: self._history_prev())
        self.command_entry.bind("<Down>", lambda e: self._history_next())

        self.send_button = ctk.CTkButton(
            cmd_row,
            text="EXECUTE",
            command=self.handle_text_command,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=36,
        )
        self.send_button.pack(side="right")

    def _build_commands_tab(self, parent):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            head,
            text="Command Center",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        quick = ctk.CTkFrame(parent, fg_color="transparent")
        quick.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkButton(
            quick,
            text="VOICE: CREATE FOLDER",
            command=self._voice_form_start_create_folder,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            height=38,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            quick,
            text="VOICE: MOVE FOLDER",
            command=self._voice_form_start_move_folder,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            height=38,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            quick,
            text="OPEN DOWNLOADS",
            command=self._open_youtube_out_dir,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            height=38,
            width=160,
        ).pack(side="left")

        card = ctk.CTkFrame(parent, fg_color=self.colors.bg, corner_radius=10)
        card.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cheat = (
            "VOICE TRIGGERS:\n"
            "  - \"create a new folder\" → voice popup\n"
            "  - \"move folder\" → voice popup\n"
            "  - say \"confirm\" / \"cancel\"\n\n"
            "TYPED COMMANDS (Console tab):\n"
            "  - download <url> [out_dir]\n"
            "  - move \"<src_folder>\" \"<dst_folder>\"\n\n"
            "HOTKEYS:\n"
            "  - Space: start listening\n"
            "  - Esc: stop listening\n"
        )
        box = ctk.CTkTextbox(
            card,
            fg_color=self.colors.bg,
            text_color=self.colors.text,
            font=("Consolas", 12),
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("end", cheat)
        box.configure(state="disabled")

    def _build_system_tab(self, parent):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            head,
            text="System Telemetry",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        note = (
            "Tip: Install psutil for richer stats.\n"
            "  pip install psutil"
            if psutil is None
            else "Live system stats (via psutil)."
        )
        ctk.CTkLabel(
            head,
            text=note,
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        card = ctk.CTkFrame(parent, fg_color=self.colors.bg, corner_radius=10)
        card.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.system_text = ctk.CTkTextbox(
            card, fg_color=self.colors.bg, text_color=self.colors.text, font=("Consolas", 12)
        )
        self.system_text.pack(fill="both", expand=True, padx=12, pady=12)
        self.system_text.configure(state="disabled")

        self._refresh_system_tab()

    def _build_camera_tab(self, parent):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            head,
            text="Camera / Gesture Control",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        info = ctk.CTkLabel(
            head,
            text="If gestures don't work, your camera may be on index 1 or 2.\n"
            "Select an index, click TEST, then START.",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            justify="left",
        )
        info.pack(anchor="w", pady=(4, 0))

        card = ctk.CTkFrame(parent, fg_color=self.colors.panel, corner_radius=12)
        card.pack(fill="x", padx=12, pady=(8, 12))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(12, 10))

        cfg_cam = self._get_config("customization", "camera_index", default=0)
        try:
            cfg_cam = int(cfg_cam)
        except Exception:
            cfg_cam = 0
        self.camera_index_var = ctk.IntVar(value=cfg_cam)
        self.camera_index_str = ctk.StringVar(value=str(cfg_cam))

        ctk.CTkLabel(
            row,
            text="Camera index",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(side="left", padx=(0, 10))

        idx_menu = ctk.CTkOptionMenu(
            row,
            values=["0", "1", "2", "3"],
            variable=self.camera_index_str,
            command=lambda v: self._on_camera_index_changed(v),
            fg_color="#1b2735",
            button_color="#1b2735",
            button_hover_color="#24384e",
            dropdown_fg_color="#0b1633",
            dropdown_text_color=self.colors.text,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=34,
            width=90,
        )
        idx_menu.pack(side="left")

        test_btn = ctk.CTkButton(
            row,
            text="TEST",
            command=self.test_camera,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=110,
            height=34,
        )
        test_btn.pack(side="left", padx=(14, 0))

        self.preview_start_btn = ctk.CTkButton(
            row,
            text="PREVIEW",
            command=self.start_camera_preview,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=130,
            height=34,
        )
        self.preview_start_btn.pack(side="left", padx=(14, 0))

        self.preview_stop_btn = ctk.CTkButton(
            row,
            text="STOP PREVIEW",
            command=self.stop_camera_preview,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=150,
            height=34,
            state="disabled",
        )
        self.preview_stop_btn.pack(side="left", padx=(10, 0))

        toggles = ctk.CTkFrame(card, fg_color="transparent")
        toggles.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkSwitch(
            toggles,
            text="MOUSE (1 finger)",
            variable=self._mouse_control_enabled,
            command=self._on_mouse_control_toggle,
            fg_color="#1b2735",
            progress_color=self.colors.accent,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkSwitch(
            toggles,
            text="MOVE WINDOW (4)",
            variable=self._window_move_enabled,
            command=self._on_window_move_toggle,
            fg_color="#1b2735",
            progress_color=self.colors.accent,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkSwitch(
            toggles,
            text="CLOSE WINDOW (5)",
            variable=self._close_window_enabled,
            command=self._on_close_window_toggle,
            fg_color="#1b2735",
            progress_color=self.colors.accent,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(side="left")

        toggles2 = ctk.CTkFrame(card, fg_color="transparent")
        toggles2.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkSwitch(
            toggles2,
            text="SCREENSHOT (gesture)",
            variable=self._screenshot_enabled,
            command=self._on_screenshot_toggle,
            fg_color="#1b2735",
            progress_color=self.colors.accent,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            toggles2,
            text="Fist action",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkOptionMenu(
            toggles2,
            values=["Stop listening", "Screenshot", "Both"],
            variable=self._fist_action,
            fg_color="#1b2735",
            button_color="#1b2735",
            button_hover_color="#24384e",
            dropdown_fg_color="#0b1633",
            dropdown_text_color=self.colors.text,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=32,
        ).pack(side="left")

        self.gesture_start_btn = ctk.CTkButton(
            row,
            text="START",
            command=self.start_gestures,
            fg_color=self.colors.ok,
            hover_color="#1fe27a",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=34,
        )
        self.gesture_start_btn.pack(side="left", padx=(14, 0))

        self.gesture_stop_btn = ctk.CTkButton(
            row,
            text="STOP",
            command=self.stop_gestures,
            fg_color=self.colors.danger,
            hover_color="#ff4a68",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=34,
            state="disabled",
        )
        self.gesture_stop_btn.pack(side="left", padx=(10, 0))

        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=12, pady=(0, 12))

        self._gesture_model_status = ctk.StringVar(value="")
        model_row = ctk.CTkFrame(card, fg_color="transparent")
        model_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(
            model_row,
            textvariable=self._gesture_model_status,
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            model_row,
            text="MODEL HELP",
            command=self.show_gesture_model_help,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            width=130,
            height=30,
        ).pack(side="right")

        ctk.CTkLabel(
            status_row,
            textvariable=self._gesture_status,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11),
            justify="left",
        ).pack(anchor="w")

        ctk.CTkLabel(
            status_row,
            textvariable=self._last_gesture,
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        deps = []
        if GestureController is None:
            deps.append("GestureController import failed (check deps).")
        try:
            import cv2  # type: ignore
        except Exception:
            deps.append("OpenCV (cv2) missing.")
        try:
            import mediapipe  # type: ignore
        except Exception:
            deps.append("MediaPipe missing.")
        if deps:
            self._gesture_status.set("Gestures: unavailable — " + " ".join(deps))

        preview_card = ctk.CTkFrame(parent, fg_color=self.colors.bg, corner_radius=12)
        preview_card.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        ctk.CTkLabel(
            preview_card,
            text="Camera Preview",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.camera_preview_label = ctk.CTkLabel(
            preview_card,
            text="Preview is stopped.",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=11),
            width=900,
            height=420,
        )
        self.camera_preview_label.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._camera_preview_ui_tick()

        try:
            import mediapipe as mp  # type: ignore

            if hasattr(mp, "solutions"):
                self._gesture_model_status.set("Model: not needed (mp.solutions available).")
            else:
                ok = os.path.exists(self._gesture_model_path)
                self._gesture_model_status.set(
                    f"Model: {'OK' if ok else 'MISSING'} — {self._gesture_model_path}"
                )
        except Exception:
            self._gesture_model_status.set(f"Model: {self._gesture_model_path}")

    def _refresh_system_tab(self):
        lines = []
        now = datetime.datetime.now()
        lines.append(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Platform: {sys.platform}")
        lines.append(f"Python: {sys.version.split()[0]}")
        lines.append("")

        if psutil is not None:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage(os.path.expanduser("~"))
                lines.append(f"CPU: {cpu:5.1f}%")
                lines.append(
                    f"RAM: {mem.percent:5.1f}%  ({self._human_bytes(mem.used)} / {self._human_bytes(mem.total)})"
                )
                lines.append(
                    f"Disk(~): {disk.percent:5.1f}% ({self._human_bytes(disk.used)} / {self._human_bytes(disk.total)})"
                )
            except Exception as e:
                lines.append(f"psutil error: {e}")
        else:
            try:
                st = os.statvfs(os.path.expanduser("~"))
                total = st.f_frsize * st.f_blocks
                free = st.f_frsize * st.f_bavail
                used = total - free
                pct = (used / total * 100.0) if total else 0.0
                lines.append(f"Disk(~): {pct:5.1f}% ({self._human_bytes(used)} / {self._human_bytes(total)})")
            except Exception:
                lines.append("Disk(~): unavailable")

        text = "\n".join(lines) + "\n"
        try:
            self.system_text.configure(state="normal")
            self.system_text.delete("1.0", "end")
            self.system_text.insert("end", text)
            self.system_text.configure(state="disabled")
        except Exception:
            pass

        self.root.after(1000, self._refresh_system_tab)

    def _refresh_indicators(self):
        try:
            listening = bool(self.is_listening)
            downloading = bool(self._download_thread and self._download_thread.is_alive())
            moving = bool(self._move_thread and self._move_thread.is_alive())

            self.ind_listen.configure(
                text_color=(self.colors.warn if listening else self.colors.muted)
            )
            self.ind_dl.configure(
                text_color=(self.colors.warn if downloading else self.colors.muted)
            )
            self.ind_move.configure(
                text_color=(self.colors.warn if moving else self.colors.muted)
            )
        except Exception:
            pass
        self.root.after(400, self._refresh_indicators)

    # ---------------------------
    # Camera / gestures
    # ---------------------------
    def _on_camera_index_changed(self, value: str):
        try:
            idx = int(str(value).strip())
        except Exception:
            idx = 0
        self.camera_index_var.set(idx)
        try:
            self.camera_index_str.set(str(idx))
        except Exception:
            pass
        self._set_config("customization", "camera_index", value=idx)
        self._schedule_config_write()
        self._gesture_status.set(f"Gestures: camera set to {idx}")

    def _gesture_set_status(self, msg: str):
        self._gesture_status.set(f"Gestures: {msg}")

    def _set_last_gesture(self, label: str):
        txt = f"Last gesture: {label}"
        try:
            self._last_gesture.set(txt)
        except Exception:
            pass
        self.log(f"Gesture detected: {label}")

    def _open_camera_tab(self):
        try:
            self.tabs.set("Camera")
        except Exception:
            pass

    def _on_mouse_control_toggle(self):
        if bool(self._mouse_control_enabled.get()):
            if pyautogui is None:
                self._mouse_control_enabled.set(False)
                self.toast("pyautogui missing; mouse control unavailable.", level="error", ms=4500)
                return
            self.toast("Mouse control enabled (1 finger).", level="ok")
        else:
            self._mouse_smooth = {"x": None, "y": None}
            self.toast("Mouse control disabled.", level="ok")

    def _on_window_move_toggle(self):
        if bool(self._window_move_enabled.get()):
            if gw is None and not self._has_xdotool():
                self._window_move_enabled.set(False)
                self.toast(
                    "Window move unavailable (need xdotool on Linux).",
                    level="error",
                    ms=4500,
                )
                return
            self.toast("Window move enabled (4 fingers).", level="ok")
        else:
            self._window_drag = {"active": False, "win": None, "dx": 0, "dy": 0}
            self.toast("Window move disabled.", level="ok")

    def _on_close_window_toggle(self):
        if bool(self._close_window_enabled.get()):
            self.toast("Close window enabled (5 fingers).", level="ok")
        else:
            self.toast("Close window disabled.", level="ok")

    def _on_screenshot_toggle(self):
        if bool(self._screenshot_enabled.get()):
            if pyautogui is None and Image is None:
                self._screenshot_enabled.set(False)
                self.toast("Screenshot unavailable (missing Pillow/pyautogui).", level="error", ms=4500)
                return
            self.toast("Screenshot enabled.", level="ok")
        else:
            self.toast("Screenshot disabled.", level="ok")

    def take_screenshot(self) -> str | None:
        screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(screenshots_dir, f"friday-{ts}.png")

        try:
            if pyautogui is not None:
                img = pyautogui.screenshot()
                img.save(path)
                self.toast("Screenshot saved.", level="ok")
                self.log(f"Screenshot: {path}")
                return path
        except Exception as e:
            self.log(f"Screenshot failed (pyautogui): {e}")

        # Fallback: try PIL ImageGrab (may not work on Linux without X/Wayland setup)
        try:
            from PIL import ImageGrab  # type: ignore

            img = ImageGrab.grab()
            img.save(path)
            self.toast("Screenshot saved.", level="ok")
            self.log(f"Screenshot: {path}")
            return path
        except Exception as e:
            self.toast("Screenshot failed.", level="error")
            self.log(f"Screenshot failed: {e}")
            return None

    def _on_fist_gesture(self):
        action = str(self._fist_action.get() or "Stop listening")
        if action in {"Stop listening", "Both"}:
            self.stop_listening()
        if action in {"Screenshot", "Both"} and bool(self._screenshot_enabled.get()):
            self.take_screenshot()

    def _mouse_move_from_norm(self, x: float, y: float):
        if pyautogui is None:
            return
        try:
            w, h = pyautogui.size()
            tx = max(0, min(int(x * w), w - 1))
            ty = max(0, min(int(y * h), h - 1))
            # basic smoothing
            lx = self._mouse_smooth["x"]
            ly = self._mouse_smooth["y"]
            if lx is None or ly is None:
                sx, sy = tx, ty
            else:
                alpha = 0.35
                sx = int(lx + (tx - lx) * alpha)
                sy = int(ly + (ty - ly) * alpha)
            self._mouse_smooth["x"] = sx
            self._mouse_smooth["y"] = sy
            pyautogui.moveTo(sx, sy, duration=0)
        except Exception:
            pass

    def _window_drag_start(self, x: float, y: float):
        win = None
        xwid = None
        if gw is not None:
            try:
                win = gw.getActiveWindow()
            except Exception:
                win = None
        if win is None:
            xwid = self._xdotool_active_window_id()
            if not xwid:
                return
        try:
            if pyautogui is None:
                return
            sw, sh = pyautogui.size()
            px = int(x * sw)
            py = int(y * sh)
            # Offset cursor->window top-left so it "sticks"
            if win is not None:
                self._window_drag = {
                    "active": True,
                    "win": win,
                    "backend": "pygetwindow",
                    "dx": px - win.left,
                    "dy": py - win.top,
                }
            else:
                geom = self._xdotool_window_geometry(xwid)
                if not geom:
                    return
                left = int(geom.get("X", "0"))
                top = int(geom.get("Y", "0"))
                self._window_drag = {
                    "active": True,
                    "win": xwid,
                    "backend": "xdotool",
                    "dx": px - left,
                    "dy": py - top,
                }
            self._set_last_gesture("window drag start")
        except Exception:
            self._window_drag = {"active": False, "win": None, "dx": 0, "dy": 0}

    def _window_drag_update(self, x: float, y: float):
        if not self._window_drag.get("active"):
            return
        win = self._window_drag.get("win")
        backend = self._window_drag.get("backend")
        if not win or pyautogui is None:
            return
        try:
            sw, sh = pyautogui.size()
            px = int(x * sw)
            py = int(y * sh)
            nx = px - int(self._window_drag.get("dx", 0))
            ny = py - int(self._window_drag.get("dy", 0))
            if backend == "xdotool":
                self._xdotool_window_move(str(win), nx, ny)
            else:
                win.moveTo(nx, ny)
        except Exception:
            pass

    def _window_drag_stop(self):
        if self._window_drag.get("active"):
            self._window_drag = {"active": False, "win": None, "dx": 0, "dy": 0}
            self._set_last_gesture("window drag stop")

    def _close_active_window(self):
        if not bool(self._close_window_enabled.get()):
            return
        try:
            if gw is not None:
                try:
                    win = gw.getActiveWindow()
                except Exception:
                    win = None
                if win:
                    try:
                        win.close()
                        return
                    except Exception:
                        pass
            wid = self._xdotool_active_window_id()
            if wid:
                self._xdotool_window_close(wid)
                return
            if pyautogui is not None:
                pyautogui.hotkey("alt", "f4")
        except Exception:
            pass

    def _gesture_click(self):
        if pyautogui is None:
            self.toast("pyautogui missing; click unavailable.", level="error")
            return
        try:
            pyautogui.click()
            self.toast("Click.", level="ok", ms=900)
        except Exception:
            pass

    def _gesture_open_palm_action(self):
        # Open palm maps to either 4 (move window via pointer updates) or 5 (close window),
        # but the controller only guarantees >=4 here. Use close if enabled and drag is not active.
        if bool(self._close_window_enabled.get()):
            self._close_active_window()

    def _build_maps_tab(self, parent):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            head,
            text="Maps (OpenStreetMap)",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        note = ctk.CTkLabel(
            head,
            text="This opens maps in your browser (no API key).",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            justify="left",
        )
        note.pack(anchor="w", pady=(4, 0))

        card = ctk.CTkFrame(parent, fg_color=self.colors.panel, corner_radius=12)
        card.pack(fill="x", padx=12, pady=(8, 12))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(12, 12))

        self.maps_query = ctk.StringVar(value="")
        entry = ctk.CTkEntry(
            row,
            textvariable=self.maps_query,
            placeholder_text="Search location… (e.g., 'New York' or '1600 Pennsylvania Ave')",
            fg_color="#000814",
            text_color=self.colors.text,
            placeholder_text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=36,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry.bind("<Return>", lambda e: self.open_map_search())

        ctk.CTkButton(
            row,
            text="OPEN",
            command=self.open_map_search,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=36,
        ).pack(side="left")

        ctk.CTkButton(
            row,
            text="OPEN LOCAL IP",
            command=self.open_local_ip_in_browser,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=160,
            height=36,
        ).pack(side="left", padx=(10, 0))

    def open_map_search(self):
        q = (self.maps_query.get() or "").strip()
        if not q:
            self.toast("Type a location first.", level="warn")
            return
        url = "https://www.openstreetmap.org/search?query=" + q.replace(" ", "+")
        try:
            webbrowser.open(url)
            self.toast("Opened map in browser.", level="ok")
        except Exception as e:
            self.toast(f"Could not open browser: {e}", level="error", ms=4500)

    def open_local_ip_in_browser(self):
        ip = _get_local_ip()
        try:
            webbrowser.open(f"http://{ip}:5000")
        except Exception:
            pass

    # ---------------------------
    # Screen share (LAN)
    # ---------------------------
    def _build_share_tab(self, parent):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            head,
            text="Share (View-Only) — LAN Browser",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        warn = (
            "Security: this shares your screen to anyone on your network who has the link + token.\n"
            "Do not use on public Wi‑Fi."
        )
        ctk.CTkLabel(
            head,
            text=warn,
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        card = ctk.CTkFrame(parent, fg_color=self.colors.panel, corner_radius=12)
        card.pack(fill="x", padx=12, pady=(8, 12))

        self.share_running = False
        self.share_port = ctk.IntVar(value=5000)
        self.share_fps = ctk.IntVar(value=5)
        self.share_token = ctk.StringVar(value=secrets.token_urlsafe(12))
        self.share_status = ctk.StringVar(value="Server: stopped")
        self._share_thread = None
        self._share_server = None

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(row, text="Port", text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=11, weight="bold")).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row, textvariable=self.share_port, width=90, fg_color="#000814", text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=12), height=32).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(row, text="FPS", text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=11, weight="bold")).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row, textvariable=self.share_fps, width=70, fg_color="#000814", text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=12), height=32).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(row, text="Token", text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=11, weight="bold")).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row, textvariable=self.share_token, width=220, fg_color="#000814", text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=12), height=32).pack(side="left", padx=(0, 12))

        self.share_start_btn = ctk.CTkButton(
            row,
            text="START",
            command=self.start_share_server,
            fg_color=self.colors.ok,
            hover_color="#1fe27a",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=32,
        )
        self.share_start_btn.pack(side="left", padx=(0, 10))

        self.share_stop_btn = ctk.CTkButton(
            row,
            text="STOP",
            command=self.stop_share_server,
            fg_color=self.colors.danger,
            hover_color="#ff4a68",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=120,
            height=32,
            state="disabled",
        )
        self.share_stop_btn.pack(side="left")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(row2, textvariable=self.share_status, text_color=self.colors.text, font=ctk.CTkFont(family="Consolas", size=11)).pack(side="left")

        ctk.CTkButton(
            row2,
            text="OPEN LINK",
            command=self.open_share_link,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=140,
            height=32,
        ).pack(side="right")

    def _share_auth_ok(self) -> bool:
        return True

    def _share_capture_jpeg(self) -> bytes | None:
        if pyautogui is None:
            return None
        try:
            img = pyautogui.screenshot()
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=70, optimize=True)
            return buf.getvalue()
        except Exception:
            return None

    def _share_windows_list(self) -> list[str]:
        titles = []
        try:
            if self._has_xdotool():
                ids = self._xdotool("search", "--onlyvisible", "--name", ".")
                for wid in [l.strip() for l in ids.splitlines() if l.strip()][:40]:
                    try:
                        t = self._xdotool("getwindowname", wid).strip()
                        if t:
                            titles.append(t)
                    except Exception:
                        continue
        except Exception:
            pass
        return titles

    def start_share_server(self):
        if Flask is None or Response is None or request is None:
            self.toast("Flask not available; share server disabled.", level="error", ms=4500)
            return
        if self.share_running:
            return

        port = int(self.share_port.get())
        fps = max(1, min(int(self.share_fps.get()), 20))
        token = str(self.share_token.get()).strip()
        if not token:
            token = secrets.token_urlsafe(12)
            self.share_token.set(token)

        app = Flask("friday_share")
        self._share_app = app

        def check_token(req) -> bool:
            try:
                return (req.args.get("token") or "") == token
            except Exception:
                return False

        @app.get("/")
        def index():
            if not check_token(request):
                return ("Forbidden", 403)
            ip = _get_local_ip()
            html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>FRIDAY Share</title>
  <style>
    body {{ font-family: monospace; background:#050816; color:#e0f7fa; margin:0; }}
    .top {{ padding:12px 16px; background:#0b1633; }}
    .grid {{ display:grid; grid-template-columns: 1fr 360px; gap:12px; padding:12px 16px; }}
    .card {{ background:#081229; border:1px solid #00e5ff33; border-radius:12px; padding:12px; }}
    img {{ width:100%; border-radius:10px; border:1px solid #00e5ff33; }}
    a {{ color:#00e5ff; }}
  </style>
</head>
<body>
  <div class="top">FRIDAY Share — view-only — {ip}:{port}</div>
  <div class="grid">
    <div class="card">
      <div>Live Screen</div>
      <img src="/stream.mjpg?token={token}" />
    </div>
    <div class="card">
      <div>Windows</div>
      <pre id="wins">Loading…</pre>
      <script>
        async function refresh() {{
          const r = await fetch('/windows?token={token}');
          document.getElementById('wins').textContent = await r.text();
        }}
        refresh();
        setInterval(refresh, 2000);
      </script>
    </div>
  </div>
</body>
</html>
"""
            return html

        @app.get("/windows")
        def windows():
            if not check_token(request):
                return ("Forbidden", 403)
            titles = self._share_windows_list()
            return "\n".join(f"- {t}" for t in titles) + ("\n" if titles else "No windows.\n")

        @app.get("/stream.mjpg")
        def stream():
            if not check_token(request):
                return ("Forbidden", 403)

            def gen():
                delay = 1.0 / float(fps)
                while self.share_running:
                    frame = self._share_capture_jpeg()
                    if not frame:
                        time.sleep(delay)
                        continue
                    yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                    time.sleep(delay)

            return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

        def run_server():
            try:
                from werkzeug.serving import make_server

                srv = make_server("0.0.0.0", port, app, threaded=True)
                self._share_server = srv
                srv.serve_forever()
            except Exception as e:
                self.root.after(0, lambda: self.toast(f"Share server failed: {e}", level="error", ms=4500))

        self.share_running = True
        self._share_thread = threading.Thread(target=run_server, daemon=True)
        self._share_thread.start()

        self.share_start_btn.configure(state="disabled")
        self.share_stop_btn.configure(state="normal")
        ip = _get_local_ip()
        self.share_status.set(f"Server: running — http://{ip}:{port}/?token={token}")
        self.toast("Share server started.", level="ok")

    def stop_share_server(self):
        self.share_running = False
        try:
            if self._share_server:
                self._share_server.shutdown()
        except Exception:
            pass
        self._share_server = None
        try:
            self.share_start_btn.configure(state="normal")
            self.share_stop_btn.configure(state="disabled")
        except Exception:
            pass
        self.share_status.set("Server: stopped")
        self.toast("Share server stopped.", level="ok")

    def open_share_link(self):
        ip = _get_local_ip()
        port = int(self.share_port.get())
        token = str(self.share_token.get()).strip()
        try:
            webbrowser.open(f"http://{ip}:{port}/?token={token}")
        except Exception:
            pass

    def test_camera(self):
        try:
            import cv2  # type: ignore
        except Exception as e:
            messagebox.showerror("OpenCV missing", f"cv2 import failed: {e}")
            return

        idx = int(self.camera_index_var.get())
        cap = cv2.VideoCapture(idx)
        ok = bool(cap.isOpened())
        try:
            if ok:
                ret, _frame = cap.read()
                ok = ok and bool(ret)
        finally:
            try:
                cap.release()
            except Exception:
                pass

        if ok:
            self.toast(f"Camera {idx} OK.", level="ok")
            self._gesture_set_status(f"camera {idx} OK")
        else:
            self.toast(f"Camera {idx} failed to open.", level="error")
            self._gesture_set_status(f"camera {idx} failed")

    def start_gestures(self):
        if GestureController is None:
            self.toast("Gesture controller unavailable (missing deps).", level="error")
            return
        use_tasks = False
        try:
            import mediapipe as mp  # type: ignore

            use_tasks = not hasattr(mp, "solutions")
        except Exception:
            use_tasks = False

        model_path = None
        if use_tasks:
            model_path = self._gesture_model_path
            if not os.path.exists(model_path):
                self.toast("Gesture model missing (hand_landmarker.task).", level="error", ms=5000)
                self._gesture_set_status("missing model (hand_landmarker.task)")
                try:
                    self.show_gesture_model_help()
                except Exception:
                    pass
                return

        idx = int(getattr(self, "camera_index_var", ctk.IntVar(value=0)).get())

        def dispatch(fn):
            try:
                self.root.after(0, fn)
            except Exception:
                pass

        def on_status(msg: str):
            self._gesture_set_status(msg)
            self.log(f"Gesture status: {msg}")

        def on_detection(fingers: int, pointer):
            try:
                if fingers == 1:
                    self._set_last_gesture("1 finger (mouse)")
                elif fingers == 2:
                    self._set_last_gesture("2 fingers (tap=click / hold=camera)")
                elif fingers == 3:
                    self._set_last_gesture("3 fingers (listen)")
                elif fingers == 4:
                    self._set_last_gesture("4 fingers (move window)")
                elif fingers >= 5:
                    self._set_last_gesture("5 fingers (close window)")
                elif fingers == 0:
                    self._set_last_gesture("fist (stop)")
                else:
                    self._set_last_gesture(f"{fingers} fingers")
            except Exception:
                pass

            try:
                if not pointer:
                    # stop drag if we lost tracking
                    self._window_drag_stop()
                    return
                x, y = pointer
                if fingers == 1 and bool(self._mouse_control_enabled.get()):
                    self._mouse_move_from_norm(x, y)
                if fingers == 4 and bool(self._window_move_enabled.get()):
                    if not self._window_drag.get("active"):
                        self._window_drag_start(x, y)
                    self._window_drag_update(x, y)
                else:
                    self._window_drag_stop()
            except Exception:
                pass

        try:
            self.gesture_controller = GestureController(
                on_open_hand=lambda: self.root.after(0, self.start_listening),
                on_closed_fist=lambda: self.root.after(0, self._on_fist_gesture),
                on_two_fingers_hold=lambda: self.root.after(0, self._open_camera_tab),
                on_two_fingers_tap=lambda: self.root.after(0, self._gesture_click),
                on_open_palm=lambda: self.root.after(0, self._gesture_open_palm_action),
                on_detection=lambda f, p: self.root.after(0, lambda: on_detection(f, p)),
                camera_index=idx,
                start_immediately=True,
                cooldown_s=1.2,
                two_finger_hold_s=1.0,
                on_status=on_status,
                dispatcher=dispatch,
                show_preview=False,
                model_path=model_path,
            )
            self.gesture_start_btn.configure(state="disabled")
            self.gesture_stop_btn.configure(state="normal")
            self.toast("Gesture control started.", level="ok")
        except Exception as e:
            self.gesture_controller = None
            self.toast(f"Gesture start failed: {e}", level="error", ms=4500)
            self._gesture_set_status(f"start failed: {e}")

    def stop_gestures(self):
        try:
            if self.gesture_controller:
                self.gesture_controller.stop()
        except Exception:
            pass
        self.gesture_controller = None
        try:
            self.gesture_start_btn.configure(state="normal")
            self.gesture_stop_btn.configure(state="disabled")
        except Exception:
            pass
        self.toast("Gesture control stopped.", level="ok")
        self._gesture_set_status("stopped")

    def start_camera_preview(self):
        if Image is None:
            self.toast("Pillow missing; camera preview unavailable.", level="error")
            return
        try:
            import cv2  # type: ignore
        except Exception as e:
            self.toast(f"OpenCV missing: {e}", level="error", ms=4500)
            return

        if self._camera_preview_thread and self._camera_preview_thread.is_alive():
            return

        # Avoid camera contention with gestures.
        if self.gesture_controller:
            self.stop_gestures()

        idx = int(getattr(self, "camera_index_var", ctk.IntVar(value=0)).get())
        self._camera_preview_stop.clear()

        def worker():
            cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                self.root.after(0, lambda: self.toast(f"Camera {idx} failed to open.", level="error"))
                return
            self._camera_preview_cap = cap
            try:
                while not self._camera_preview_stop.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        break
                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb)
                    img = img.resize((960, 540))
                    with self._camera_preview_lock:
                        self._camera_preview_pil = img
                    time.sleep(0.02)
            finally:
                try:
                    cap.release()
                except Exception:
                    pass
                self._camera_preview_cap = None

        self._camera_preview_thread = threading.Thread(target=worker, daemon=True)
        self._camera_preview_thread.start()
        try:
            self.preview_start_btn.configure(state="disabled")
            self.preview_stop_btn.configure(state="normal")
        except Exception:
            pass
        self.toast("Camera preview started.", level="ok")

    def stop_camera_preview(self):
        self._camera_preview_stop.set()
        try:
            if self._camera_preview_thread and self._camera_preview_thread.is_alive():
                self._camera_preview_thread.join(timeout=1.0)
        except Exception:
            pass
        self._camera_preview_thread = None
        with self._camera_preview_lock:
            self._camera_preview_pil = None
        try:
            self.camera_preview_label.configure(image=None, text="Preview is stopped.")
        except Exception:
            pass
        try:
            self.preview_start_btn.configure(state="normal")
            self.preview_stop_btn.configure(state="disabled")
        except Exception:
            pass
        self.toast("Camera preview stopped.", level="ok")

    def _camera_preview_ui_tick(self):
        try:
            img = None
            with self._camera_preview_lock:
                img = self._camera_preview_pil
            if img is not None:
                self._camera_preview_ctk_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=(960, 540)
                )
                self.camera_preview_label.configure(image=self._camera_preview_ctk_img, text="")
        except Exception:
            pass
        self.root.after(60, self._camera_preview_ui_tick)

    def show_gesture_model_help(self):
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        path = self._gesture_model_path
        text = (
            "Your MediaPipe build uses the Tasks API (no mp.solutions).\n"
            "To enable hand-gesture control, download the MediaPipe model:\n"
            "  hand_landmarker.task\n\n"
            "Place it here:\n"
            f"  {path}\n\n"
            "Then restart FRIDAY and click START in the Camera tab.\n\n"
            "Tip:\n"
            f"  Create folder: {models_dir}\n"
        )
        win = ctk.CTkToplevel(self.root)
        win.title("Gesture Model Help")
        win.geometry("820x460")
        win.configure(fg_color=self.colors.bg)

        box = ctk.CTkTextbox(
            win, fg_color=self.colors.bg, text_color=self.colors.text, font=("Consolas", 11)
        )
        box.pack(fill="both", expand=True, padx=14, pady=14)
        box.insert("end", text)
        box.configure(state="disabled")

    def _build_youtube_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(
            top,
            text="YouTube Downloader",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        note = (
            "Note: Only download content you own or have permission to download.\n"
            "Some sites' Terms of Service may restrict downloading."
        )
        ctk.CTkLabel(
            top,
            text=note,
            text_color=self.colors.muted,
            justify="left",
            font=ctk.CTkFont(family="Consolas", size=10),
        ).pack(anchor="w", pady=(4, 0))

        form = ctk.CTkFrame(parent, fg_color="transparent")
        form.pack(fill="x", padx=12, pady=(4, 6))

        self.yt_url = ctk.StringVar(value="")
        cfg_out = self._get_config(
            "customization",
            "youtube_download_dir",
            default=os.path.join(os.path.expanduser("~"), "Downloads"),
        )
        self.yt_out_dir = ctk.StringVar(value=str(cfg_out))
        self.yt_mode = ctk.StringVar(value="Video (best)")
        try:
            self.yt_out_dir.trace_add("write", lambda *_: self._on_youtube_out_dir_changed())
        except Exception:
            pass

        ctk.CTkLabel(
            form,
            text="URL",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.yt_url_entry = ctk.CTkEntry(
            form,
            textvariable=self.yt_url,
            fg_color="#000814",
            text_color=self.colors.text,
            placeholder_text="https://www.youtube.com/watch?v=…",
            font=ctk.CTkFont(family="Consolas", size=12),
            height=34,
        )
        self.yt_url_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Save to",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=1, column=0, sticky="w", pady=(0, 6))
        out_entry = ctk.CTkEntry(
            form,
            textvariable=self.yt_out_dir,
            fg_color="#000814",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=34,
        )
        out_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 6))

        browse = ctk.CTkButton(
            form,
            text="Browse",
            command=self._browse_youtube_out_dir,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=110,
            height=34,
        )
        browse.grid(row=1, column=2, padx=(10, 0), pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Mode",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=2, column=0, sticky="w", pady=(0, 6))
        mode = ctk.CTkOptionMenu(
            form,
            values=["Video (best)", "Video (mp4)", "Audio (mp3)"],
            variable=self.yt_mode,
            fg_color="#1b2735",
            button_color="#1b2735",
            button_hover_color="#24384e",
            dropdown_fg_color="#0b1633",
            dropdown_text_color=self.colors.text,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=34,
        )
        mode.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(0, 6))

        form.grid_columnconfigure(1, weight=1)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(6, 12))

        self.yt_download_button = ctk.CTkButton(
            actions,
            text="DOWNLOAD",
            command=self.download_youtube_from_ui,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            width=160,
            height=38,
        )
        self.yt_download_button.pack(side="left")

        self.yt_open_folder_button = ctk.CTkButton(
            actions,
            text="OPEN FOLDER",
            command=self._open_youtube_out_dir,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=160,
            height=38,
        )
        self.yt_open_folder_button.pack(side="left", padx=(10, 0))

        self.yt_open_last_button = ctk.CTkButton(
            actions,
            text="OPEN LAST",
            command=self._open_last_download,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=140,
            height=38,
            state="disabled",
        )
        self.yt_open_last_button.pack(side="left", padx=(10, 0))

        queue_card = ctk.CTkFrame(parent, fg_color=self.colors.bg, corner_radius=10)
        queue_card.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ctk.CTkLabel(
            queue_card,
            text="Download Queue",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))
        self.yt_queue_box = ctk.CTkTextbox(
            queue_card,
            fg_color=self.colors.bg,
            text_color=self.colors.text,
            font=("Consolas", 11),
            height=220,
        )
        self.yt_queue_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.yt_queue_box.configure(state="disabled")
        self._yt_queue_render()

    def _on_youtube_out_dir_changed(self):
        try:
            val = str(self.yt_out_dir.get())
            if val:
                self._set_config("customization", "youtube_download_dir", value=val)
                self._schedule_config_write()
        except Exception:
            pass

    def _yt_queue_render(self):
        try:
            box = getattr(self, "yt_queue_box", None)
            if not box:
                return
            with self._yt_queue_lock:
                items = list(self._yt_queue)
                active = getattr(self, "_yt_active", None)
            lines = []
            if active:
                lines.append(f"ACTIVE: {active.get('url')}")
                lines.append(f"  Mode: {active.get('mode')} | Out: {active.get('out_dir')}")
                lines.append("")
            if items:
                lines.append("QUEUED:")
                for i, it in enumerate(items[:12], start=1):
                    lines.append(f"  {i:02d}. {it.get('url')}")
            else:
                lines.append("Queue is empty.")

            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("end", "\n".join(lines) + "\n")
            box.configure(state="disabled")
        except Exception:
            pass

    def _yt_enqueue(self, url: str, out_dir: str, mode: str):
        item = {"url": url, "out_dir": out_dir, "mode": mode}
        with self._yt_queue_lock:
            self._yt_queue.append(item)
        self._yt_queue_render()
        self._yt_queue_kick()

    def _yt_queue_kick(self):
        if self._download_thread and self._download_thread.is_alive():
            return
        self._download_thread = threading.Thread(target=self._yt_queue_worker, daemon=True)
        self._download_thread.start()

    def _yt_queue_worker(self):
        while True:
            with self._yt_queue_lock:
                if not self._yt_queue:
                    self._yt_active = None
                    self.root.after(0, self._yt_queue_render)
                    break
                item = self._yt_queue.pop(0)
                self._yt_active = item
            self.root.after(0, self._yt_queue_render)
            self._download_youtube_once(item["url"], item["out_dir"], item["mode"])

    def _build_files_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(
            top,
            text="Folder Mover",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(anchor="w")

        self.move_src = ctk.StringVar(value="")
        self.move_dst = ctk.StringVar(value="")
        self.move_on_conflict = ctk.StringVar(value="Rename")

        form = ctk.CTkFrame(parent, fg_color="transparent")
        form.pack(fill="x", padx=12, pady=(4, 6))

        ctk.CTkLabel(
            form,
            text="Source folder",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        src_entry = ctk.CTkEntry(
            form,
            textvariable=self.move_src,
            fg_color="#000814",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=34,
        )
        src_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 6))
        src_browse = ctk.CTkButton(
            form,
            text="Browse",
            command=self._browse_move_src,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=110,
            height=34,
        )
        src_browse.grid(row=0, column=2, padx=(10, 0), pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Destination folder",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=1, column=0, sticky="w", pady=(0, 6))
        dst_entry = ctk.CTkEntry(
            form,
            textvariable=self.move_dst,
            fg_color="#000814",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=34,
        )
        dst_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 6))
        dst_browse = ctk.CTkButton(
            form,
            text="Browse",
            command=self._browse_move_dst,
            fg_color="#1b2735",
            hover_color="#24384e",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=110,
            height=34,
        )
        dst_browse.grid(row=1, column=2, padx=(10, 0), pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="If destination exists",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=2, column=0, sticky="w", pady=(0, 6))
        conflict = ctk.CTkOptionMenu(
            form,
            values=["Rename", "Fail"],
            variable=self.move_on_conflict,
            fg_color="#1b2735",
            button_color="#1b2735",
            button_hover_color="#24384e",
            dropdown_fg_color="#0b1633",
            dropdown_text_color=self.colors.text,
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=34,
        )
        conflict.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(0, 6))

        form.grid_columnconfigure(1, weight=1)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(6, 12))

        self.move_button = ctk.CTkButton(
            actions,
            text="MOVE FOLDER",
            command=self.move_folder_from_ui,
            fg_color=self.colors.accent,
            hover_color="#29f2ff",
            text_color=self.colors.bg,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            width=180,
            height=38,
        )
        self.move_button.pack(side="left")

    def _build_windows_panel(self, parent):
        ctk.CTkLabel(
            parent,
            text="ACTIVE WINDOWS",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.window_listbox = self._tk_listbox(
            parent,
            bg="#000814",
            fg=self.colors.text,
            selectbackground="#00bfa5",
            font=("Consolas", 10),
        )
        self.window_listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.window_listbox.bind("<Double-Button-1>", self.on_window_activate)

    def _tk_canvas(self, parent, **kwargs):
        import tkinter as tk

        return tk.Canvas(parent, highlightthickness=0, bd=0, **kwargs)

    def _tk_listbox(self, parent, **kwargs):
        import tkinter as tk

        return tk.Listbox(parent, activestyle="none", **kwargs)

    def _init_orb_visual(self):
        c = self.orb_canvas
        w = int(c["width"])
        h = int(c["height"])
        cx, cy = w // 2, h // 2

        self._orb_outer = c.create_oval(
            cx - 28,
            cy - 28,
            cx + 28,
            cy + 28,
            outline=self.colors.accent,
            width=2,
        )
        self._orb_inner = c.create_oval(
            cx - 16, cy - 16, cx + 16, cy + 16, fill="#00bfa5", outline=""
        )
        self._orb_pulse = c.create_oval(
            cx - 6, cy - 6, cx + 6, cy + 6, fill=self.colors.text, outline=""
        )
        self._orb_pulse_dir = 1
        self._animate_orb_pulse()

    def _animate_orb_pulse(self):
        c = self.orb_canvas
        try:
            x0, y0, x1, y1 = c.coords(self._orb_pulse)
        except Exception:
            return

        delta = 0.8 * self._orb_pulse_dir
        x0 -= delta
        y0 -= delta
        x1 += delta
        y1 += delta

        max_radius = 10
        min_radius = 4
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        r = (x1 - x0) / 2
        if r > max_radius:
            r = max_radius
            self._orb_pulse_dir = -1
        elif r < min_radius:
            r = min_radius
            self._orb_pulse_dir = 1

        c.coords(self._orb_pulse, cx - r, cy - r, cx + r, cy + r)
        self.root.after(90, self._animate_orb_pulse)

    # ---------------------------
    # Logging / status
    # ---------------------------
    def log(self, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.log("Log cleared")

    def export_log(self):
        try:
            self.log_text.configure(state="normal")
            content = self.log_text.get("1.0", "end").strip()
            self.log_text.configure(state="disabled")
        except Exception:
            content = ""

        if not content:
            messagebox.showinfo("Empty log", "There is no log content to export.")
            return

        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(logs_dir, f"friday-{ts}.log")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
                f.write("\n")
            self.toast(f"Log exported: {path}", level="ok", ms=4500)
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def update_status(self, status: str, color: str | None = None):
        self.status_label.configure(text=status, text_color=(color or self.colors.ok))
        self.root.update_idletasks()

    # ---------------------------
    # Active windows
    # ---------------------------
    def refresh_window_list(self):
        self._window_handles = []
        self.window_listbox.delete(0, "end")

        # Backend 1: pygetwindow (not supported on Linux in many versions)
        if gw:
            try:
                windows = gw.getAllWindows()
            except Exception:
                windows = []

            for w in windows:
                try:
                    title = (w.title or "").strip()
                    if not title or not w.isVisible:
                        continue
                    self._window_handles.append(w)
                    self.window_listbox.insert("end", title)
                except Exception:
                    continue
        else:
            # Backend 2 (Linux/X11): xdotool
            if self._has_xdotool():
                try:
                    ids = self._xdotool("search", "--onlyvisible", "--name", ".")
                    win_ids = [line.strip() for line in ids.splitlines() if line.strip()]
                except Exception:
                    win_ids = []

                for wid in win_ids[:80]:
                    try:
                        title = self._xdotool("getwindowname", wid).strip()
                        if not title:
                            continue
                        self._window_handles.append(("xdotool", wid))
                        self.window_listbox.insert("end", title)
                    except Exception:
                        continue

        self.root.after(4000, self.refresh_window_list)

    def on_window_activate(self, event=None):
        if not self._window_handles:
            return
        try:
            idx = self.window_listbox.curselection()
            if not idx:
                return
            w = self._window_handles[idx[0]]
            if isinstance(w, tuple) and w and w[0] == "xdotool":
                self._xdotool("windowactivate", "--sync", str(w[1]))
            else:
                try:
                    w.activate()
                except Exception:
                    try:
                        w.minimize()
                        w.restore()
                    except Exception:
                        pass
        except Exception:
            pass

    def _has_xdotool(self) -> bool:
        return shutil.which("xdotool") is not None

    def _xdotool(self, *args: str) -> str:
        out = subprocess.check_output(["xdotool", *args], text=True, stderr=subprocess.DEVNULL)
        return (out or "").strip()

    def _xdotool_active_window_id(self) -> str | None:
        if not self._has_xdotool():
            return None
        try:
            wid = self._xdotool("getactivewindow").strip()
            return wid or None
        except Exception:
            return None

    def _xdotool_window_geometry(self, wid: str) -> dict | None:
        try:
            out = self._xdotool("getwindowgeometry", "--shell", wid)
            data = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
            # Expect X,Y,WIDTH,HEIGHT
            if "X" in data and "Y" in data:
                return data
        except Exception:
            return None
        return None

    def _xdotool_window_move(self, wid: str, x: int, y: int):
        try:
            self._xdotool("windowmove", wid, str(int(x)), str(int(y)))
        except Exception:
            pass

    def _xdotool_window_close(self, wid: str):
        try:
            self._xdotool("windowclose", wid)
        except Exception:
            pass

    # ---------------------------
    # Voice control
    # ---------------------------
    def update_voice_settings(self):
        try:
            speed = int(self.speed_var.get())
            volume = float(self.volume_var.get())
            self.voice_engine.set_voice_properties(rate=speed, volume=volume)
            self.log(f"Voice updated: speed={speed}, volume={volume:.2f}")
            self._set_config("assistant", "voice_speed", value=speed)
            self._set_config("assistant", "voice_volume", value=volume)
            self._schedule_config_write()
        except Exception:
            pass

    def start_listening(self):
        try:
            self.voice_engine.stop_speaking()
        except Exception:
            pass

        if self.is_listening:
            return

        self.is_listening = True
        self.listen_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.update_status("Listening…", self.colors.warn)
        self.log("Voice listening started")

        threading.Thread(target=self.listen_loop, daemon=True).start()

    def stop_listening(self):
        self.is_listening = False
        self.listen_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.update_status("Stopped", self.colors.danger)
        self.log("Voice listening stopped")

    def listen_loop(self):
        while self.is_listening:
            try:
                try:
                    if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                        time.sleep(0.2)
                        continue
                except Exception:
                    pass

                text = None
                try:
                    if hasattr(self.voice_engine, "listen_for_command"):
                        text = self.voice_engine.listen_for_command()
                    elif hasattr(self.voice_engine, "listen"):
                        text = self.voice_engine.listen()
                except Exception:
                    text = None

                if text:
                    text = text.strip()
                    self.root.after(0, lambda t=text: self._handle_recognized_text(t))

                time.sleep(0.1)
            except Exception:
                time.sleep(0.5)

        self.root.after(0, self.stop_listening)

    def _handle_recognized_text(self, text: str):
        text = (text or "").strip()
        if not text:
            return

        self.log(f"Heard: {text}")

        if self._voice_form:
            self._voice_form_handle(text)
            return

        lowered = text.lower()
        if any(w in lowered for w in ("hide", "sleep", "go to sleep")):
            self.hide_interface()
            return
        if ("create" in lowered and "folder" in lowered) or "new folder" in lowered:
            self._voice_form_start_create_folder()
            return

        if ("move" in lowered and "folder" in lowered) or lowered.strip() == "move":
            self._voice_form_start_move_folder()
            return

        handled = False
        try:
            handled = bool(self.command_processor.process(text))
        except Exception as e:
            self.log(f"Command processor error: {e}")

        if not handled:
            self._fallback_handle_command(text)

    def background_listener(self):
        while True:
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    time.sleep(1)
                    continue

                if (
                    self.wake_word_enabled
                    and self.is_hidden
                    and hasattr(self.voice_engine, "listen_offline")
                ):
                    result = self.voice_engine.listen_offline(timeout=2)
                    if (result or "").strip().lower() == "friday":
                        self.root.after(0, self.show_interface)
            except Exception:
                pass
            time.sleep(0.4)

    def show_interface(self):
        self.is_hidden = False
        try:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.after(1200, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass
        try:
            self.voice_engine.speak("I'm here. What can I do for you?")
        except Exception:
            pass
        self.start_listening()

    def hide_interface(self):
        self.is_hidden = True
        try:
            self.stop_listening()
        except Exception:
            pass
        try:
            self.root.withdraw()
        except Exception:
            pass
        try:
            self.voice_engine.speak("Standing by.")
        except Exception:
            pass

    def toggle_wake_word(self):
        try:
            self.wake_word_enabled = bool(self._wake_var.get())
            self.log(f"Wake word: {'ON' if self.wake_word_enabled else 'OFF'}")
        except Exception:
            pass

    def toggle_chatbot(self):
        try:
            enabled = bool(self._chatbot_var.get())
            if hasattr(self.command_processor, "chatbot_mode"):
                self.command_processor.chatbot_mode = enabled
            self.log(f"Chatbot mode: {'ON' if enabled else 'OFF'}")
        except Exception:
            pass

    # ---------------------------
    # Voice-controlled popups (no keyboard)
    # ---------------------------
    def _voice_form_reset(self):
        if not self._voice_form:
            return
        try:
            win = self._voice_form.get("window")
            if win and win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        self._voice_form = None
        self.update_status("Ready", self.colors.ok)

    def _default_user_location(self) -> str:
        home = os.path.expanduser("~")
        for candidate in ("Desktop", "Downloads", "Documents"):
            p = os.path.join(home, candidate)
            if os.path.isdir(p):
                return p
        return home

    def _extract_folder_name(self, text: str) -> str:
        t = (text or "").strip()
        for prefix in ("name it", "call it", "folder name", "the name is"):
            if t.lower().startswith(prefix):
                t = t[len(prefix) :].strip()
                break
        t = t.strip("\"' ").strip()
        t = t.replace("/", " ").replace("\\", " ").strip()
        return t

    def _location_from_speech(self, text: str) -> str | None:
        t = (text or "").lower()
        home = os.path.expanduser("~")
        if "desktop" in t:
            return os.path.join(home, "Desktop")
        if "downloads" in t:
            return os.path.join(home, "Downloads")
        if "documents" in t:
            return os.path.join(home, "Documents")
        if "home" in t:
            return home
        if t.startswith("/") or (":" in t and "\\" in t):
            return text.strip()
        if "path " in t:
            return text.split(" ", 1)[1].strip() if " " in text else None
        return None

    def _unique_path(self, path: str) -> str:
        if not os.path.exists(path):
            return path
        base = path
        n = 1
        while True:
            candidate = f"{base} ({n})"
            if not os.path.exists(candidate):
                return candidate
            n += 1

    def _voice_form_start_create_folder(self):
        if self._voice_form:
            return

        dest_dir = self._default_user_location()
        self._voice_form = {
            "mode": "create_folder",
            "step": "name",
            "name": "",
            "dest_dir": dest_dir,
        }

        win = ctk.CTkToplevel(self.root)
        win.title("Create Folder (Voice)")
        win.geometry("560x260")
        win.configure(fg_color=self.colors.bg)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self._voice_form_reset)

        title = ctk.CTkLabel(
            win,
            text="CREATE NEW FOLDER",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
        )
        title.pack(anchor="w", padx=16, pady=(16, 8))

        body = ctk.CTkFrame(win, fg_color=self.colors.panel, corner_radius=12)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        name_label = ctk.CTkLabel(
            body,
            text="Name: (waiting…) ",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        )
        name_label.pack(anchor="w", padx=14, pady=(14, 6))

        loc_label = ctk.CTkLabel(
            body,
            text=f"Location: {dest_dir}",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=11),
            wraplength=520,
            justify="left",
        )
        loc_label.pack(anchor="w", padx=14, pady=(0, 10))

        hint = ctk.CTkLabel(
            body,
            text="Say the folder name. Then say: desktop / downloads / documents / home, or say: confirm. Say: cancel to stop.",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            wraplength=520,
            justify="left",
        )
        hint.pack(anchor="w", padx=14, pady=(0, 12))

        self._voice_form["window"] = win
        self._voice_form["name_label"] = name_label
        self._voice_form["loc_label"] = loc_label

        try:
            self.voice_engine.speak("What should I name the folder?")
        except Exception:
            pass
        self.update_status("Voice: folder name?", self.colors.warn)

    def _voice_form_start_move_folder(self):
        if self._voice_form:
            return

        self._voice_form = {
            "mode": "move_folder",
            "step": "source",
            "src": "",
            "dst": "",
            "on_conflict": "Rename",
        }

        win = ctk.CTkToplevel(self.root)
        win.title("Move Folder (Voice)")
        win.geometry("680x320")
        win.configure(fg_color=self.colors.bg)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self._voice_form_reset)

        title = ctk.CTkLabel(
            win,
            text="MOVE FOLDER",
            text_color=self.colors.accent,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
        )
        title.pack(anchor="w", padx=16, pady=(16, 8))

        body = ctk.CTkFrame(win, fg_color=self.colors.panel, corner_radius=12)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        src_label = ctk.CTkLabel(
            body,
            text="Source: (waiting…)",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            wraplength=640,
            justify="left",
        )
        src_label.pack(anchor="w", padx=14, pady=(14, 6))

        dst_label = ctk.CTkLabel(
            body,
            text="Destination: (waiting…)",
            text_color=self.colors.text,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            wraplength=640,
            justify="left",
        )
        dst_label.pack(anchor="w", padx=14, pady=(0, 10))

        hint = ctk.CTkLabel(
            body,
            text="Say the source folder path. Then say the destination folder path. Say: confirm to move. Say: cancel to stop.",
            text_color=self.colors.muted,
            font=ctk.CTkFont(family="Consolas", size=10),
            wraplength=640,
            justify="left",
        )
        hint.pack(anchor="w", padx=14, pady=(0, 12))

        self._voice_form["window"] = win
        self._voice_form["src_label"] = src_label
        self._voice_form["dst_label"] = dst_label

        try:
            self.voice_engine.speak("Tell me the source folder path.")
        except Exception:
            pass
        self.update_status("Voice: source folder?", self.colors.warn)

    def _voice_form_handle(self, text: str):
        form = self._voice_form
        if not form:
            return

        lowered = (text or "").strip().lower()
        if "cancel" in lowered or lowered in {"stop", "never mind", "nevermind"}:
            self.log("Voice operation cancelled.")
            try:
                self.voice_engine.speak("Cancelled.")
            except Exception:
                pass
            self._voice_form_reset()
            return

        if form.get("mode") == "create_folder":
            self._voice_form_handle_create_folder(text)
            return
        if form.get("mode") == "move_folder":
            self._voice_form_handle_move_folder(text)
            return

    def _voice_form_handle_create_folder(self, text: str):
        form = self._voice_form or {}
        step = form.get("step")

        if step == "name":
            name = self._extract_folder_name(text)
            if not name:
                try:
                    self.voice_engine.speak("I didn't catch the name. Please say it again.")
                except Exception:
                    pass
                return

            form["name"] = name
            form["step"] = "location_or_confirm"
            try:
                lbl = form.get("name_label")
                if lbl:
                    lbl.configure(text=f"Name: {name}")
            except Exception:
                pass

            try:
                self.voice_engine.speak(
                    "Where should I create it? Say desktop, downloads, documents, home, or say confirm."
                )
            except Exception:
                pass
            self.update_status("Voice: location or confirm?", self.colors.warn)
            self._voice_form = form
            return

        if step == "location_or_confirm":
            if "confirm" in text.lower() or text.strip().lower() in {"create", "go ahead"}:
                self._voice_form_create_folder_now()
                return

            loc = self._location_from_speech(text)
            if loc:
                loc = os.path.expanduser(loc)
                form["dest_dir"] = loc
                try:
                    lbl = form.get("loc_label")
                    if lbl:
                        lbl.configure(text=f"Location: {loc}")
                except Exception:
                    pass
                try:
                    self.voice_engine.speak("Say confirm to create the folder.")
                except Exception:
                    pass
                self.update_status("Voice: confirm to create", self.colors.warn)
                self._voice_form = form
                return

            try:
                self.voice_engine.speak("Say desktop, downloads, documents, home, or confirm.")
            except Exception:
                pass
            return

    def _voice_form_create_folder_now(self):
        form = self._voice_form
        if not form:
            return
        name = (form.get("name") or "").strip()
        dest_dir = (form.get("dest_dir") or "").strip()
        if not name:
            return

        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            self.log(f"Create folder failed (location): {e}")
            try:
                self.voice_engine.speak("I couldn't access that location.")
            except Exception:
                pass
            return

        target = os.path.join(dest_dir, name)
        target = self._unique_path(target)
        try:
            os.makedirs(target, exist_ok=False)
            self.log(f"Folder created: {target}")
            self.toast("Folder created.", level="ok")
            try:
                self.voice_engine.speak("Folder created.")
            except Exception:
                pass
            self._voice_form_reset()
        except Exception as e:
            self.log(f"Create folder failed: {e}")
            self.toast("Create folder failed.", level="error")
            try:
                self.voice_engine.speak("I couldn't create that folder.")
            except Exception:
                pass

    def _voice_form_handle_move_folder(self, text: str):
        form = self._voice_form or {}
        step = form.get("step")

        if step == "source":
            src = self._location_from_speech(text) or text.strip()
            src = os.path.expanduser(src)
            if not os.path.isdir(src):
                self.log("Source not found; waiting again.")
                try:
                    self.voice_engine.speak("That source folder does not exist. Please say the full path again.")
                except Exception:
                    pass
                return
            form["src"] = src
            form["step"] = "destination"
            try:
                lbl = form.get("src_label")
                if lbl:
                    lbl.configure(text=f"Source: {src}")
            except Exception:
                pass
            try:
                self.voice_engine.speak("Now tell me the destination folder path.")
            except Exception:
                pass
            self.update_status("Voice: destination folder?", self.colors.warn)
            self._voice_form = form
            return

        if step == "destination":
            dst = self._location_from_speech(text) or text.strip()
            dst = os.path.expanduser(dst)
            if not os.path.isdir(dst):
                self.log("Destination not found; waiting again.")
                try:
                    self.voice_engine.speak(
                        "That destination folder does not exist. Please say the full path again."
                    )
                except Exception:
                    pass
                return
            form["dst"] = dst
            form["step"] = "confirm"
            try:
                lbl = form.get("dst_label")
                if lbl:
                    lbl.configure(text=f"Destination: {dst}")
            except Exception:
                pass
            try:
                self.voice_engine.speak("Say confirm to move the folder.")
            except Exception:
                pass
            self.update_status("Voice: confirm to move", self.colors.warn)
            self._voice_form = form
            return

        if step == "confirm":
            if "confirm" not in text.lower() and text.strip().lower() not in {"move", "go ahead"}:
                try:
                    self.voice_engine.speak("Say confirm to move, or cancel.")
                except Exception:
                    pass
                return
            src = form.get("src") or ""
            dst = form.get("dst") or ""
            self.log(f"Voice move confirmed: {src} -> {dst}")
            self.start_folder_move(src=src, dst=dst, on_conflict=form.get("on_conflict", "Rename"))
            try:
                self.voice_engine.speak("Moving now.")
            except Exception:
                pass
            self._voice_form_reset()

    # ---------------------------
    # Typed commands
    # ---------------------------
    def handle_text_command(self):
        text = (self.command_entry.get() or "").strip()
        self.command_entry.delete(0, "end")

        if not text:
            try:
                self.voice_engine.speak("Please type a command.")
            except Exception:
                pass
            return

        self.log(f"Typed command: {text}")
        self._history_push(text)

        if self._handle_local_text_commands(text):
            return

        handled = False
        try:
            handled = bool(self.command_processor.process(text))
        except Exception as e:
            self.log(f"Error processing command: {e}")

        if not handled:
            self._fallback_handle_command(text)

    def _history_push(self, text: str):
        t = (text or "").strip()
        if not t:
            return
        if self._cmd_history and self._cmd_history[-1] == t:
            self._cmd_history_idx = None
            return
        self._cmd_history.append(t)
        if len(self._cmd_history) > 200:
            self._cmd_history = self._cmd_history[-200:]
        self._cmd_history_idx = None

    def _history_prev(self):
        if not self._cmd_history:
            return "break"
        if self._cmd_history_idx is None:
            self._cmd_history_idx = len(self._cmd_history) - 1
        else:
            self._cmd_history_idx = max(0, self._cmd_history_idx - 1)
        self._history_apply()
        return "break"

    def _history_next(self):
        if not self._cmd_history:
            return "break"
        if self._cmd_history_idx is None:
            return "break"
        self._cmd_history_idx += 1
        if self._cmd_history_idx >= len(self._cmd_history):
            self._cmd_history_idx = None
            self.command_entry.delete(0, "end")
            return "break"
        self._history_apply()
        return "break"

    def _history_apply(self):
        if self._cmd_history_idx is None:
            return
        try:
            text = self._cmd_history[self._cmd_history_idx]
        except Exception:
            return
        self.command_entry.delete(0, "end")
        self.command_entry.insert(0, text)

    def _handle_local_text_commands(self, text: str) -> bool:
        try:
            parts = shlex.split(text)
        except Exception:
            parts = text.split()

        if not parts:
            return False

        cmd = parts[0].lower()
        if cmd in {"hide", "sleep"}:
            self.hide_interface()
            return True
        if cmd == "download" and len(parts) >= 2:
            url = parts[1]
            out_dir = parts[2] if len(parts) >= 3 else self.yt_out_dir.get()
            self.start_youtube_download(url=url, out_dir=out_dir, mode=self.yt_mode.get())
            return True

        if cmd == "move" and len(parts) >= 3:
            src = parts[1]
            dst = parts[2]
            self.start_folder_move(
                src=src, dst=dst, on_conflict=self.move_on_conflict.get()
            )
            return True

        return False

    def _fallback_handle_command(self, text: str):
        if "hello" in text.lower():
            try:
                self.voice_engine.speak("Hello. How can I help you today?")
            except Exception:
                pass
        else:
            try:
                self.voice_engine.speak(
                    "I understood the command, but I don't have a protocol for that yet."
                )
            except Exception:
                pass

    # ---------------------------
    # YouTube download (yt-dlp)
    # ---------------------------
    def _browse_youtube_out_dir(self):
        directory = filedialog.askdirectory(title="Select download folder")
        if directory:
            self.yt_out_dir.set(directory)

    def _open_youtube_out_dir(self):
        path = self.yt_out_dir.get().strip()
        if not path:
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"Could not open folder: {e}")

    def _open_last_download(self):
        path = self._last_download_path
        if not path:
            messagebox.showinfo("No file yet", "No completed download to open yet.")
            return
        if not os.path.exists(path):
            messagebox.showwarning("Missing file", "Last downloaded file was not found.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"Could not open file: {e}")

    def download_youtube_from_ui(self):
        url = self.yt_url.get().strip()
        out_dir = self.yt_out_dir.get().strip()
        mode = self.yt_mode.get()
        self.start_youtube_download(url=url, out_dir=out_dir, mode=mode)

    def start_youtube_download(self, url: str, out_dir: str, mode: str):
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube URL first.")
            return
        if not out_dir:
            messagebox.showwarning("Missing folder", "Choose a download folder.")
            return
        os.makedirs(out_dir, exist_ok=True)
        self.log(f"Download queued: {url}")
        self.toast("Added to download queue.", level="ok")
        self._yt_enqueue(url=url, out_dir=out_dir, mode=mode)

    def _download_youtube_once(self, url: str, out_dir: str, mode: str):
        try:
            try:
                import yt_dlp  # type: ignore
            except Exception:
                yt_dlp = None

            if yt_dlp is None:
                self.root.after(
                    0,
                    lambda: self.log(
                        "yt-dlp not installed. Install with: pip install yt-dlp"
                    ),
                )
                return

            outtmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
            ydl_opts: dict = {"outtmpl": outtmpl, "noplaylist": True}

            if mode == "Audio (mp3)":
                ydl_opts.update(
                    {
                        "format": "bestaudio/best",
                        "postprocessors": [
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192",
                            }
                        ],
                    }
                )
            elif mode == "Video (mp4)":
                ydl_opts.update({"format": "bv*+ba/best", "merge_output_format": "mp4"})
            else:
                ydl_opts.update({"format": "bv*+ba/best"})

            last_progress = {"t": 0.0, "msg": ""}

            def hook(d):
                status = d.get("status")
                if status == "finished":
                    filename = d.get("filename")
                    if filename:
                        self._last_download_path = filename
                        self.root.after(0, lambda: self.yt_open_last_button.configure(state="normal"))
                        self.root.after(0, self._yt_queue_render)
                    return
                if status != "downloading":
                    return
                now = time.time()
                if now - last_progress["t"] < 0.6:
                    return
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total * 100.0) if total else 0.0
                speed = d.get("speed") or 0
                eta = d.get("eta")
                msg = (
                    f"Downloading… {pct:5.1f}% | {self._human_bytes(speed)}/s | ETA {eta}s"
                    if eta
                    else f"Downloading… {pct:5.1f}%"
                )
                if msg == last_progress["msg"]:
                    return
                last_progress["t"] = now
                last_progress["msg"] = msg
                self.root.after(0, lambda m=msg: self.update_status(m, self.colors.warn))

            ydl_opts["progress_hooks"] = [hook]

            self.root.after(0, lambda: self.log(f"Saving to: {out_dir}"))
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.root.after(0, lambda: self.log("Download complete."))
            self.root.after(0, lambda: self.toast("Download complete.", level="ok"))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Download failed: {e}"))
            self.root.after(0, lambda: self.toast("Download failed.", level="error"))
        finally:
            self.root.after(0, lambda: self.update_status("Ready", self.colors.ok))
            self.root.after(0, self._yt_queue_render)

    def _human_bytes(self, n: float) -> str:
        try:
            n = float(n)
        except Exception:
            return "0B"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while n >= 1024 and i < len(units) - 1:
            n /= 1024.0
            i += 1
        return f"{n:.1f}{units[i]}"

    # ---------------------------
    # Folder move
    # ---------------------------
    def _browse_move_src(self):
        directory = filedialog.askdirectory(title="Select source folder")
        if directory:
            self.move_src.set(directory)

    def _browse_move_dst(self):
        directory = filedialog.askdirectory(title="Select destination folder")
        if directory:
            self.move_dst.set(directory)

    def move_folder_from_ui(self):
        src = self.move_src.get().strip()
        dst = self.move_dst.get().strip()
        self.start_folder_move(src=src, dst=dst, on_conflict=self.move_on_conflict.get())

    def start_folder_move(self, src: str, dst: str, on_conflict: str):
        if not src or not dst:
            messagebox.showwarning(
                "Missing paths", "Choose a source and destination folder."
            )
            return
        if not os.path.isdir(src):
            messagebox.showerror("Invalid source", "Source folder does not exist.")
            return
        if not os.path.isdir(dst):
            messagebox.showerror("Invalid destination", "Destination folder does not exist.")
            return

        if self._move_thread and self._move_thread.is_alive():
            messagebox.showinfo("Move busy", "A move operation is already running.")
            return

        self.move_button.configure(state="disabled")
        self.update_status("Moving…", self.colors.warn)
        self.log(f"Move requested: {src} -> {dst}")

        self._move_thread = threading.Thread(
            target=self._move_folder_worker,
            args=(src, dst, on_conflict),
            daemon=True,
        )
        self._move_thread.start()

    def _move_folder_worker(self, src: str, dst: str, on_conflict: str):
        try:
            base = os.path.basename(os.path.normpath(src))
            dest_path = os.path.join(dst, base)

            if os.path.abspath(src) == os.path.abspath(dest_path):
                raise RuntimeError("Source and destination are the same folder.")

            if os.path.exists(dest_path):
                if on_conflict == "Fail":
                    raise FileExistsError(f"Destination already exists: {dest_path}")
                ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                dest_path = os.path.join(dst, f"{base}-moved-{ts}")
                self.root.after(
                    0, lambda: self.log(f"Destination exists; renaming to: {dest_path}")
                )

            shutil.move(src, dest_path)
            self.root.after(0, lambda: self.log(f"Move complete: {dest_path}"))
            self.root.after(0, lambda: self.toast("Move complete.", level="ok"))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Move failed: {e}"))
            self.root.after(0, lambda: self.toast("Move failed.", level="error"))
        finally:
            self.root.after(0, lambda: self.update_status("Ready", self.colors.ok))
            self.root.after(0, lambda: self.move_button.configure(state="normal"))

    # ---------------------------
    # Help
    # ---------------------------
    def show_help(self):
        help_text = (
            "FRIDAY COMMAND GUIDE\n"
            "====================\n\n"
            "Voice commands depend on your local CommandProcessor.\n"
            "Typed commands always work in the Console tab.\n\n"
            "VOICE POPUPS (NO KEYBOARD):\n"
            "  - Say: create a new folder\n"
            "    - Then say the folder name\n"
            "    - Then say: desktop / downloads / documents / home, or say: confirm\n"
            "  - Say: move folder\n"
            "    - Then say the source folder path\n"
            "    - Then say the destination folder path (parent folder)\n"
            "    - Then say: confirm\n"
            "  - Say: cancel to stop\n\n"
            "TYPED COMMANDS:\n"
            "  download <url> [out_dir]\n"
            "  move \"<src_folder>\" \"<dst_folder>\"\n\n"
            "UI FEATURES:\n"
            "  - YouTube tab: download video/audio (requires yt-dlp + ffmpeg for mp3)\n"
            "  - Files tab: move a folder to another location\n\n"
            "NOTES:\n"
            "  - Only download content you own or have permission to download.\n"
        )

        win = ctk.CTkToplevel(self.root)
        win.title("Help")
        win.geometry("700x520")
        win.configure(fg_color=self.colors.bg)

        box = ctk.CTkTextbox(
            win, fg_color=self.colors.bg, text_color=self.colors.text, font=("Consolas", 11)
        )
        box.pack(fill="both", expand=True, padx=14, pady=14)
        box.insert("end", help_text)
        box.configure(state="disabled")

    def show_dependency_help(self):
        err = self.command_processor_error or "Unknown import error."
        text = (
            "Some optional dependencies are missing, so FRIDAY is running in LIMITED MODE.\n\n"
            f"Import error:\n{err}\n\n"
            "Fix:\n"
            "  pip install -r requirements.txt\n\n"
            "Then run:\n"
            "  python main.py\n"
        )
        win = ctk.CTkToplevel(self.root)
        win.title("Fix Dependencies")
        win.geometry("760x420")
        win.configure(fg_color=self.colors.bg)

        box = ctk.CTkTextbox(
            win, fg_color=self.colors.bg, text_color=self.colors.text, font=("Consolas", 11)
        )
        box.pack(fill="both", expand=True, padx=14, pady=14)
        box.insert("end", text)
        box.configure(state="disabled")


def main():
    app = FridayGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
