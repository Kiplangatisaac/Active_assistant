"""
Futuristic UI for Active Assistant using CustomTkinter.
NVIDIA-inspired dark theme with neon green accents, glassmorphism,
rounded corners, and responsive layout.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from loguru import logger

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus, AppState
from active_assistant.agents.manager import agent_manager
from active_assistant.plugins.manager import plugin_manager
from active_assistant.tools.base import tool_registry
from active_assistant.voice.assistant import voice_assistant
from active_assistant.web.crawler import web_manager


# ============================================================================
# Theme & Styling — NVIDIA Inspired
# ============================================================================

class FuturisticTheme:
    """Futuristic color themes with NVIDIA-inspired dark neon green."""

    THEMES = {
        "nvidia": {
            "name": "NVIDIA Dark",
            "bg_primary": "#0a0a0c",
            "bg_secondary": "#16161d",
            "bg_tertiary": "#1e1e24",
            "bg_card": "#0f0f12",
            "border": "#2d2d34",
            "border_focus": "#76b900",
            "text_primary": "#f0f0f3",
            "text_secondary": "#8a8a91",
            "text_muted": "#5a5a61",
            "accent": "#76b900",
            "accent_hover": "#8fd600",
            "accent_dim": "#1a2e00",
            "warning": "#ffd60a",
            "error": "#ff4b55",
            "info": "#00a2ff",
            "success": "#00ff41",
            "glow": "#76b900",
            "accent_alt": "#00a2ff",
            "bg_gradient_start": "#0a0a0c",
            "bg_gradient_end": "#16161d",
            "glass": "rgba(22, 22, 29, 0.7)",
            "glow_blur": "15px",
            "panel_bg": "#0a0a0c",
            "card_bg": "#0f0f12",
            "input_bg": "#0d0d11",
            "border_subtle": "#2a2a2a",
            "border_bright": "#76b900",
            "text_dim": "#6a6a71",
        },
        "dark": {
            "name": "Dark Professional",
            "bg_primary": "#0a0a0c",
            "bg_secondary": "#16161d",
            "bg_tertiary": "#1e1e24",
            "bg_card": "#0f0f12",
            "border": "#2d2d34",
            "border_focus": "#76b900",
            "text_primary": "#f0f0f3",
            "text_secondary": "#8a8a91",
            "text_muted": "#5a5a61",
            "accent": "#76b900",
            "accent_hover": "#8fd600",
            "accent_dim": "#1a2e00",
            "warning": "#ffd60a",
            "error": "#ff4b55",
            "info": "#00a2ff",
            "success": "#00ff41",
            "glow": "#76b900",
            "accent_alt": "#3b82f6",
            "bg_gradient_start": "#0a0a0c",
            "bg_gradient_end": "#16161d",
            "glass": "rgba(22, 22, 29, 0.7)",
            "glow_blur": "10px",
        },
        "light": {
            "name": "Light Clean",
            "bg_primary": "#ffffff",
            "bg_secondary": "#f6f8fa",
            "bg_tertiary": "#eaeef2",
            "bg_card": "#ffffff",
            "border": "#d0d7de",
            "border_focus": "#0969da",
            "text_primary": "#24292f",
            "text_secondary": "#656d76",
            "text_muted": "#8b949e",
            "accent": "#1a7f37",
            "accent_hover": "#166534",
            "accent_dim": "#1a7f3733",
            "warning": "#bf8700",
            "error": "#cf222e",
            "info": "#0550ae",
            "success": "#1a7f37",
            "glow": "#1a7f37",
            "accent_alt": "#3b82f6",
            "bg_gradient_start": "#ffffff",
            "bg_gradient_end": "#f6f8fa",
            "glass": "rgba(255, 255, 255, 0.7)",
            "glow_blur": "10px",
        },
        "matrix": {
            "name": "Matrix Green",
            "bg_primary": "#000000",
            "bg_secondary": "#001100",
            "bg_tertiary": "#002200",
            "bg_card": "#001a00",
            "border": "#003300",
            "border_focus": "#00ff00",
            "text_primary": "#00ff00",
            "text_secondary": "#00cc00",
            "text_muted": "#008800",
            "accent": "#00ff00",
            "accent_hover": "#00cc00",
            "accent_dim": "#003300",
            "warning": "#ffff00",
            "error": "#ff0000",
            "info": "#00ffff",
            "success": "#00ff00",
            "glow": "#00ff00",
            "accent_alt": "#00ff88",
            "bg_gradient_start": "#000000",
            "bg_gradient_end": "#001100",
            "glass": "rgba(0, 17, 0, 0.7)",
            "glow_blur": "20px",
        },
        "cyberpunk": {
            "name": "Cyberpunk Neon",
            "bg_primary": "#0a0a0f",
            "bg_secondary": "#1a0a2e",
            "bg_tertiary": "#2d1b4e",
            "bg_card": "#160a2a",
            "border": "#ff00ff",
            "border_focus": "#00ffff",
            "text_primary": "#ffffff",
            "text_secondary": "#ff00ff",
            "text_muted": "#8800ff",
            "accent": "#ff00ff",
            "accent_hover": "#ff66ff",
            "accent_dim": "#330033",
            "warning": "#ffcc00",
            "error": "#ff0066",
            "info": "#00ffff",
            "success": "#00ff88",
            "glow": "#ff00ff",
            "accent_alt": "#00ffff",
            "bg_gradient_start": "#0a0a0f",
            "bg_gradient_end": "#1a0a2e",
            "glass": "rgba(26, 10, 46, 0.7)",
            "glow_blur": "25px",
        },
        "neon_blue": {
            "name": "Neon Blue AI",
            "bg_primary": "#00001a",
            "bg_secondary": "#000033",
            "bg_tertiary": "#00004d",
            "bg_card": "#000026",
            "border": "#0088ff",
            "border_focus": "#00ccff",
            "text_primary": "#ccffff",
            "text_secondary": "#66ccff",
            "text_muted": "#3399ff",
            "accent": "#0088ff",
            "accent_hover": "#00aaff",
            "accent_dim": "#001a33",
            "warning": "#ffaa00",
            "error": "#ff3333",
            "info": "#00ddff",
            "success": "#00ff88",
            "glow": "#0088ff",
            "accent_alt": "#00ffff",
            "bg_gradient_start": "#00001a",
            "bg_gradient_end": "#00004d",
            "glass": "rgba(0, 0, 26, 0.7)",
            "glow_blur": "20px",
        },
        "sunset_ai": {
            "name": "Sunset AI",
            "bg_primary": "#1a001a",
            "bg_secondary": "#330033",
            "bg_tertiary": "#4d004d",
            "bg_card": "#260026",
            "border": "#ff6600",
            "border_focus": "#ff9900",
            "text_primary": "#ffccaa",
            "text_secondary": "#ff9966",
            "text_muted": "#cc6633",
            "accent": "#ff6600",
            "accent_hover": "#ff8800",
            "accent_dim": "#331100",
            "warning": "#ffff00",
            "error": "#ff3333",
            "info": "#ff9900",
            "success": "#ff8844",
            "glow": "#ff6600",
            "accent_alt": "#ffcc00",
            "bg_gradient_start": "#1a001a",
            "bg_gradient_end": "#330033",
            "glass": "rgba(26, 0, 26, 0.7)",
            "glow_blur": "15px",
        },
    }

    @classmethod
    def get(cls, theme: str = "nvidia") -> Dict:
        return cls.THEMES.get(theme, cls.THEMES["nvidia"])

    @classmethod
    def get_theme_names(cls) -> List[str]:
        return [v["name"] for v in cls.THEMES.values()]

    @classmethod
    def get_theme_keys(cls) -> List[str]:
        return list(cls.THEMES.keys())


# ============================================================================
# Custom Widgets — NVIDIA Styling
# ============================================================================

class GlowingFrame(ctk.CTkFrame):
    """Frame with animated glow effect."""

    def __init__(self, master, **kwargs):
        self.glow_color = kwargs.pop("glow_color", None)
        super().__init__(master, **kwargs)
        self._glow_animation = None

    def start_glow(self, color: str = None):
        if color:
            self.glow_color = color
        self._animate_border(0)

    def _animate_border(self, step: int):
        if not self.glow_color:
            return
        pass

    def stop_glow(self):
        if self._glow_animation:
            self.after_cancel(self._glow_animation)


class MetricCard(ctk.CTkFrame):
    """Animated metric display card with NVIDIA styling."""

    def __init__(self, master, title: str, value: str = "0", icon: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self.theme = FuturisticTheme.get("nvidia")
        self.configure(
            fg_color=self.theme["bg_card"],
            border_width=1,
            border_color=self.theme["border"],
            corner_radius=12,
        )

        if icon:
            self.icon_label = ctk.CTkLabel(
                self, text=icon, font=("Segoe UI Variable", 24),
                text_color=self.theme["accent"]
            )
            self.icon_label.pack(pady=(12, 6))
        else:
            self.icon_label = None

        self.value_label = ctk.CTkLabel(
            self, text=value, font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        )
        self.value_label.pack(pady=(0, 2))

        self.title_label = ctk.CTkLabel(
            self, text=title, font=("Segoe UI Variable", 12),
            text_color=self.theme["text_secondary"]
        )
        self.title_label.pack(pady=(0, 12))

    def update_value(self, value: str, animate: bool = True):
        self.value_label.configure(text=value)

    def apply_theme(self, theme: Dict):
        self.theme = theme
        self.configure(fg_color=theme["bg_card"], border_color=theme["border"])
        if self.icon_label:
            self.icon_label.configure(text_color=theme["accent"])
        self.value_label.configure(text_color=theme["text_primary"])
        self.title_label.configure(text_color=theme["text_secondary"])


class StatusIndicator(ctk.CTkFrame):
    """Animated status indicator with NVIDIA styling."""

    def __init__(self, master, status: str = "idle", **kwargs):
        super().__init__(master, **kwargs)
        self.theme = FuturisticTheme.get("nvidia")
        self._status = status
        self._animation_id = None

        self.configure(
            fg_color=self.theme["bg_card"],
            border_width=1,
            border_color=self.theme["border"],
            corner_radius=20,
        )

        self.dot = ctk.CTkLabel(self, text="●", font=("Segoe UI Variable", 16))
        self.dot.pack(side="left", padx=8)

        self.label = ctk.CTkLabel(
            self, text=status.capitalize(), font=("Segoe UI Variable", 12, "bold")
        )
        self.label.pack(side="left", padx=8)

        self.set_status(status)

    def set_status(self, status: str):
        self._status = status
        colors = {
            "running": self.theme["success"],
            "paused": self.theme["warning"],
            "stopped": self.theme["text_muted"],
            "error": self.theme["error"],
            "idle": self.theme["text_secondary"],
            "listening": self.theme["accent"],
            "processing": self.theme["info"],
        }
        color = colors.get(status, self.theme["text_secondary"])
        self.dot.configure(text_color=color)
        self.label.configure(text=status.capitalize())

        if status in ("running", "listening", "processing"):
            self._animate_pulse(color)
        else:
            self._stop_animation()

    def _animate_pulse(self, color: str):
        def pulse():
            current = self.dot.cget("text_color")
            new_color = color if current != color else self.theme["text_muted"]
            self.dot.configure(text_color=new_color)
            self._animation_id = self.after(800, pulse)
        pulse()

    def _stop_animation(self):
        if self._animation_id:
            self.after_cancel(self._animation_id)
            self._animation_id = None

    def apply_theme(self, theme: Dict):
        self.theme = theme
        self.configure(fg_color=theme["bg_card"], border_color=theme["border"])
        self.set_status(self._status)


class ChatMessage(ctk.CTkFrame):
    """Chat message bubble with NVIDIA styling."""

    def __init__(self, master, role: str, content: str, **kwargs):
        super().__init__(master, **kwargs)
        self.theme = FuturisticTheme.get("nvidia")

        is_user = role == "user"
        align = "e" if is_user else "w"
        bg_color = self.theme["accent_dim"] if is_user else self.theme["bg_card"]

        self.configure(fg_color=bg_color, border_width=1, border_color=self.theme["border"], corner_radius=12)

        role_text = "You" if is_user else "Assistant"
        role_label = ctk.CTkLabel(
            self, text=role_text, font=("Segoe UI Variable", 10, "bold"),
            text_color=self.theme["accent"] if is_user else self.theme["accent_alt"]
        )
        role_label.pack(anchor=align, padx=12, pady=(8, 0))

        self.content_label = ctk.CTkLabel(
            self, text=content, font=("Segoe UI Variable", 11),
            text_color=self.theme["text_primary"], wraplength=450,
            justify="right" if is_user else "left"
        )
        self.content_label.pack(anchor=align, padx=12, pady=(0, 8))

    def apply_theme(self, theme: Dict):
        self.theme = theme
        self.configure(fg_color=self.theme["bg_card"])
        self.content_label.configure(text_color=theme["text_primary"])


# ============================================================================
# Main Window
# ============================================================================

class MainWindow(ctk.CTk):
    """Main application window with futuristic UI."""

    def __init__(self):
        super().__init__()

        # DPI scaling support
        try:
            self.tk.call('tk', 'scaling', self.tk.call('tk', 'scaling') * 1.25)
        except Exception:
            pass

        self.theme_name = get_config().ui.theme or "nvidia"
        self.theme = FuturisticTheme.get(self.theme_name)

        # Window setup
        window_cfg = get_config().ui.window
        self.title("Active Assistant")
        self.geometry(f"{window_cfg['width']}x{window_cfg['height']}")
        self.minsize(window_cfg['min_width'], window_cfg['min_height'])

        if sys.platform == "win32":
            self.after(100, lambda: self.state("zoomed"))  # Maximize on Windows

        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Initialize components
        self._setup_sidebar()
        self._setup_main_area()
        self._setup_event_handlers()

        # State
        self._chat_history: List[Dict] = []
        self._update_task = None

        # Start update loop
        self._start_updates()

        # Bind resize event for responsive adjustments
        self.bind("<Configure>", self._on_window_resize)

        logger.info("Main window initialized")

    def _setup_sidebar(self):
        """Create sidebar navigation with responsive width."""
        sidebar_width = 260 if self.winfo_screenwidth() > 1000 else 200
        self.sidebar = ctk.CTkFrame(self, width=sidebar_width, fg_color=self.theme["bg_secondary"])
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(2, weight=1)

        # Logo/Title
        header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        logo = ctk.CTkLabel(
            header, text="🤖 Active Assistant", font=("Segoe UI Variable", 18, "bold"),
            text_color=self.theme["accent"]
        )
        logo.pack()

        # Status indicator
        self.status_indicator = StatusIndicator(header, "starting")
        self.status_indicator.pack(pady=(10, 0))

        # Navigation buttons
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=10)

        self.nav_buttons = {}
        nav_items = [
            ("🏠 Dashboard", "dashboard"),
            ("💬 Chat", "chat"),
            ("👁️ Vision", "vision"),
            ("🎤 Voice", "voice"),
            ("🤖 Agents", "agents"),
            ("🔌 Plugins", "plugins"),
            ("🔍 Search", "search"),
            ("⚙️ Settings", "settings"),
        ]

        for label, key in nav_items:
            btn = ctk.CTkButton(
                nav_frame, text=label, font=("Segoe UI Variable", 13, "bold"),
                fg_color="transparent", text_color=self.theme["text_secondary"],
                hover_color=self.theme["accent_dim"], anchor="w", height=45,
                corner_radius=10,
                command=lambda k=key: self._switch_tab(k)
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn

        # Highlight default
        self._active_tab = "dashboard"
        self._update_nav_selection()

        # Quick actions at bottom
        actions_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        actions_frame.pack(fill="x", side="bottom", padx=10, pady=20)

        ctk.CTkButton(
            actions_frame, text="⏸️ Pause Monitoring", font=("Segoe UI Variable", 12, "bold"),
            fg_color=self.theme["warning"], hover_color=self.theme["accent_hover"],
            corner_radius=10, height=40,
            command=self._toggle_monitoring
        ).pack(fill="x", pady=3)

        ctk.CTkButton(
            actions_frame, text="🗂️ Organize Downloads", font=("Segoe UI Variable", 12, "bold"),
            fg_color=self.theme["bg_card"], hover_color=self.theme["border"],
            text_color=self.theme["text_primary"], corner_radius=10, height=40,
            command=self._organize_downloads
        ).pack(fill="x", pady=3)

        ctk.CTkButton(
            actions_frame, text="📸 Capture Screen", font=("Segoe UI Variable", 12, "bold"),
            fg_color=self.theme["bg_card"], hover_color=self.theme["border"],
            text_color=self.theme["text_primary"], corner_radius=10, height=40,
            command=self._capture_screen
        ).pack(fill="x", pady=3)

    def _setup_main_area(self):
        """Create main content area with tabbed interface."""
        self.main_frame = ctk.CTkFrame(self, fg_color=self.theme["bg_primary"])
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Create tab frames
        self.tabs = {}
        self._create_dashboard_tab()
        self._create_chat_tab()
        self._create_vision_tab()
        self._create_voice_tab()
        self._create_agents_tab()
        self._create_plugins_tab()
        self._create_search_tab()
        self._create_settings_tab()

        # Show default
        self._show_tab("dashboard")

    def _show_tab(self, tab_name: str):
        """Show a tab and hide others."""
        for name, tab in self.tabs.items():
            if name == tab_name:
                tab.grid(row=0, column=0, sticky="nsew")
            else:
                tab.grid_remove()

    def _switch_tab(self, tab_name: str):
        """Switch active tab."""
        self._active_tab = tab_name
        self._update_nav_selection()
        self._show_tab(tab_name)

    def _update_nav_selection(self):
        """Update navigation button highlights."""
        for key, btn in self.nav_buttons.items():
            if key == self._active_tab:
                btn.configure(fg_color=self.theme["accent_dim"], text_color=self.theme["accent"])
            else:
                btn.configure(fg_color="transparent", text_color=self.theme["text_secondary"])

    def _create_dashboard_tab(self):
        """Create dashboard with metrics and activity."""
        tab = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.tabs["dashboard"] = tab

        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Dashboard", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Metrics grid
        metrics_frame = ctk.CTkFrame(tab, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=30, pady=(0, 20))

        screen_width = self.winfo_screenwidth()
        if screen_width > 1200:
            col_count = 4
        elif screen_width > 800:
            col_count = 2
        else:
            col_count = 1

        metrics_frame.grid_columnconfigure(tuple(range(col_count)), weight=1)

        self.metric_cards = {}
        metrics_data = [
            ("uptime", "Uptime", "0s", "⏱️"),
            ("captures", "Screens Captured", "0", "📸"),
            ("issues", "Issues Detected", "0", "⚠️"),
            ("tools", "Tools Executed", "0", "🔧"),
        ]

        for i, (key, title, value, icon) in enumerate(metrics_data):
            card = MetricCard(metrics_frame, title, value, icon)
            self.metric_cards[key] = card
            row = i // col_count
            col = i % col_count
            card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

        # Activity feed
        activity_frame = ctk.CTkFrame(tab, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        activity_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        activity_frame.grid_columnconfigure(0, weight=1)
        activity_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            activity_frame, text="Recent Activity", font=("Segoe UI Variable", 18, "bold"),
            text_color=self.theme["text_primary"]
        ).grid(row=0, column=0, padx=20, pady=15, sticky="w")

        self.activity_list = ctk.CTkScrollableFrame(activity_frame, fg_color=self.theme["bg_secondary"])
        self.activity_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.activity_list.grid_columnconfigure(0, weight=1)

    def _create_chat_tab(self):
        """Create chat interface with file upload."""
        tab = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.tabs["chat"] = tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Chat", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Model selector
        self.chat_model_var = ctk.StringVar(value="auto")
        model_combo = ctk.CTkComboBox(
            header, values=["auto", "vision", "chat", "fast", "reasoning"],
            variable=self.chat_model_var, width=140, font=("Segoe UI Variable", 11)
        )
        model_combo.pack(side="right", padx=10)

        # Chat history
        self.chat_scroll = ctk.CTkScrollableFrame(tab, fg_color=self.theme["bg_secondary"])
        self.chat_scroll.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 10))
        self.chat_scroll.grid_columnconfigure(0, weight=1)

        # Input area with file upload
        input_frame = ctk.CTkFrame(tab, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        input_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)

        # File attachments preview
        self.chat_attachments = []
        self.attachment_frame = ctk.CTkFrame(input_frame, fg_color="transparent", height=0)
        self.attachment_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        self.attachment_frame.grid_remove()

        # Text input
        self.chat_input = ctk.CTkTextbox(
            input_frame, height=100, font=("Segoe UI Variable", 13),
            fg_color=self.theme["bg_secondary"], border_color=self.theme["border"],
            border_width=1, corner_radius=10
        )
        self.chat_input.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.chat_input.bind("<Return>", lambda e: self._send_chat() if not e.state & 0x1 else None)
        self.chat_input.bind("<Shift-Return>", lambda e: None)

        # Upload button
        upload_btn = ctk.CTkButton(
            input_frame, text="📎", font=("Segoe UI", 16),
            fg_color=self.theme["bg_secondary"], hover_color=self.theme["border"],
            width=45, height=45, corner_radius=12, command=self._upload_file
        )
        upload_btn.grid(row=1, column=1, sticky="n", padx=(0, 5))

        send_btn = ctk.CTkButton(
            input_frame, text="Send →", font=("Segoe UI Variable", 13, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            width=100, height=45, corner_radius=12, command=self._send_chat
        )
        send_btn.grid(row=1, column=2, sticky="n")

    def _create_vision_tab(self):
        """Create vision monitoring tab."""
        tab = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.tabs["vision"] = tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Vision Monitor", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Controls
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right")

        self.vision_paused = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            controls, text="Pause", variable=self.vision_paused,
            command=self._toggle_vision, font=("Segoe UI Variable", 12, "bold"),
            button_color=self.theme["accent"], fg_color=self.theme["bg_secondary"]
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            controls, text="🔍 Analyze Now", font=("Segoe UI Variable", 12, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            corner_radius=10, command=self._analyze_current_screen
        ).pack(side="left", padx=10)

        # Preview area
        self.vision_preview = ctk.CTkFrame(tab, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        self.vision_preview.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 30))
        self.vision_preview.grid_columnconfigure(0, weight=1)
        self.vision_preview.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.vision_preview, text="Screen Capture Preview",
            font=("Segoe UI Variable", 14), text_color=self.theme["text_secondary"]
        ).grid(row=0, column=0, pady=15)

        self.vision_image_label = ctk.CTkLabel(
            self.vision_preview, text="No capture yet", font=("Segoe UI Variable", 14),
            text_color=self.theme["text_muted"]
        )
        self.vision_image_label.grid(row=1, column=0, sticky="nsew")

        # Analysis results
        self.vision_results = ctk.CTkTextbox(
            tab, height=200, font=("Segoe UI Variable", 12),
            fg_color=self.theme["bg_secondary"], border_color=self.theme["border"],
            border_width=1, corner_radius=10
        )
        self.vision_results.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 30))
        self.vision_results.insert("1.0", "Vision analysis results will appear here...")
        self.vision_results.configure(state="disabled")

    def _create_voice_tab(self):
        """Create voice assistant tab."""
        tab = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.tabs["voice"] = tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Voice Assistant", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Voice status
        self.voice_status = StatusIndicator(header, "idle")
        self.voice_status.pack(side="right", padx=20)

        # Waveform visualization placeholder
        self.voice_waveform = ctk.CTkFrame(tab, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12, height=150)
        self.voice_waveform.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 20))
        self.voice_waveform.grid_propagate(False)

        ctk.CTkLabel(
            self.voice_waveform, text="🎤 Voice Waveform Visualization",
            font=("Segoe UI Variable", 14), text_color=self.theme["text_muted"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Commands
        commands_frame = ctk.CTkFrame(tab, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        commands_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 20))

        ctk.CTkLabel(
            commands_frame, text="Voice Commands", font=("Segoe UI Variable", 16, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(anchor="w", padx=20, pady=15)

        commands_list = ctk.CTkScrollableFrame(commands_frame, fg_color=self.theme["bg_secondary"], height=200)
        commands_list.pack(fill="x", padx=20, pady=(0, 15))

        for cmd in get_config().voice.commands:
            ctk.CTkLabel(
                commands_list, text=f"• {cmd}", font=("Segoe UI Variable", 12),
                text_color=self.theme["text_secondary"], anchor="w"
            ).pack(fill="x", padx=10, pady=3)

        # Test button
        ctk.CTkButton(
            tab, text="🎤 Test Voice", font=("Segoe UI Variable", 13, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            height=45, corner_radius=12, command=self._test_voice
        ).grid(row=3, column=0, padx=30, pady=(0, 30), sticky="ew")

    def _create_agents_tab(self):
        """Create agents management tab."""
        tab = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.tabs["agents"] = tab

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Multi-Agent System", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Agent cards container - responsive columns
        self.agents_container = ctk.CTkFrame(tab, fg_color="transparent")
        self.agents_container.pack(fill="both", expand=True, padx=30, pady=(0, 30))

        screen_width = self.winfo_screenwidth()
        if screen_width > 1000:
            col_count = 2
        else:
            col_count = 1

        self.agents_container.grid_columnconfigure(tuple(range(col_count)), weight=1)

        self.agent_cards = {}
        self._refresh_agents()

    def _refresh_agents(self):
        """Refresh agent cards."""
        for widget in self.agents_container.winfo_children():
            widget.destroy()
        self.agent_cards.clear()

        agents = agent_manager.list_agents()
        screen_width = self.winfo_screenwidth()
        col_count = 2 if screen_width > 1000 else 1

        for i, agent_info in enumerate(agents):
            card = self._create_agent_card(agent_info)
            row = i // col_count
            col = i % col_count
            card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            self.agent_cards[agent_info["id"]] = card

        if not agents:
            ctk.CTkLabel(
                self.agents_container, text="No agents configured",
                font=("Segoe UI Variable", 14), text_color=self.theme["text_muted"]
            ).pack(pady=50)

    def _create_agent_card(self, agent_info: Dict) -> ctk.CTkFrame:
        """Create agent status card with NVIDIA styling."""
        theme = self.theme
        card = ctk.CTkFrame(self.agents_container, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            header, text=agent_info["name"], font=("Segoe UI Variable", 16, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        status_indicator = StatusIndicator(header, agent_info["status"])
        status_indicator.pack(side="right")

        # Description
        ctk.CTkLabel(
            card, text=agent_info.get("role", ""), font=("Segoe UI Variable", 11),
            text_color=self.theme["text_secondary"], wraplength=250, justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(
            actions, text="🧪 Test Agent", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["bg_secondary"], hover_color=self.theme["border"],
            text_color=self.theme["text_primary"], corner_radius=8,
            command=lambda a=agent_info["id"]: self._test_agent(a)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            actions, text="📋 View Logs", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["bg_secondary"], hover_color=self.theme["border"],
            text_color=self.theme["text_primary"], corner_radius=8,
            command=lambda a=agent_info["id"]: self._view_agent_logs(a)
        ).pack(side="left", padx=5)

        return card

    def _create_plugins_tab(self):
        """Create plugins management tab."""
        tab = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.tabs["plugins"] = tab

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Plugin Manager", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        ctk.CTkButton(
            header, text="🔄 Refresh", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            corner_radius=10, command=self._refresh_plugins
        ).pack(side="right", padx=10)

        # Plugin list
        self.plugins_container = ctk.CTkFrame(tab, fg_color="transparent")
        self.plugins_container.pack(fill="both", expand=True, padx=30, pady=(0, 30))

        self._refresh_plugins()

    def _refresh_plugins(self):
        """Refresh plugin list."""
        for widget in self.plugins_container.winfo_children():
            widget.destroy()

        plugins = plugin_manager.list_plugins()
        for plugin in plugins:
            card = self._create_plugin_card(plugin)
            card.pack(fill="x", padx=0, pady=6)

    def _create_plugin_card(self, plugin_info: PluginInfo) -> ctk.CTkFrame:
        """Create plugin card with NVIDIA styling."""
        theme = self.theme
        card = ctk.CTkFrame(self.plugins_container, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        card.pack(fill="x", pady=5)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=12)

        # Info
        info = ctk.CTkFrame(content, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            info, text=f"{plugin_info.name} v{plugin_info.version}",
            font=("Segoe UI Variable", 14, "bold"), text_color=self.theme["text_primary"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            info, text=plugin_info.description, font=("Segoe UI Variable", 11),
            text_color=self.theme["text_secondary"], wraplength=400
        ).pack(anchor="w")

        # Actions
        actions = ctk.CTkFrame(content, fg_color="transparent")
        actions.pack(side="right", padx=10)

        ctk.CTkButton(
            actions, text="▶️ Run", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            width=80, corner_radius=8,
            command=lambda p=plugin_info.name: self._run_plugin(p)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            actions, text="ℹ️ Details", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["bg_secondary"], hover_color=self.theme["border"],
            text_color=self.theme["text_primary"], width=80, corner_radius=8,
            command=lambda p=plugin_info.name: self._show_plugin_details(p)
        ).pack(side="left", padx=5)

        return card

    def _create_search_tab(self):
        """Create multimodal search tab."""
        tab = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.tabs["search"] = tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Multimodal Search", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Search input
        search_frame = ctk.CTkFrame(tab, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        search_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 20))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_input = ctk.CTkEntry(
            search_frame, placeholder_text="Describe what you're looking for...",
            font=("Segoe UI Variable", 14), height=45, fg_color=self.theme["bg_secondary"],
            border_color=self.theme["border"], border_width=1
        )
        self.search_input.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search_input.bind("<Return>", lambda e: self._perform_search())

        self.search_type = ctk.StringVar(value="all")
        ctk.CTkComboBox(
            search_frame, values=["all", "images", "videos", "audio", "documents"],
            variable=self.search_type, width=120, font=("Segoe UI Variable", 11)
        ).grid(row=0, column=1, padx=(0, 10))

        ctk.CTkButton(
            search_frame, text="🔍 Search", font=("Segoe UI Variable", 13, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            width=100, corner_radius=10, command=self._perform_search
        ).grid(row=0, column=2)

        # Results
        self.search_results = ctk.CTkScrollableFrame(tab, fg_color=self.theme["bg_secondary"], corner_radius=10)
        self.search_results.grid(row=2, column=0, sticky="nsew", padx=30, pady=(0, 30))
        self.search_results.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.search_results, text="Search results will appear here",
            font=("Segoe UI Variable", 14), text_color=self.theme["text_muted"]
        ).pack(pady=50)

    def _create_settings_tab(self):
        """Create settings tab."""
        tab = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.tabs["settings"] = tab

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(
            header, text="Settings", font=("Segoe UI Variable", 28, "bold"),
            text_color=self.theme["text_primary"]
        ).pack(side="left")

        # Settings sections
        self._create_api_settings(tab)
        self._create_permissions_settings(tab)
        self._create_ui_settings(tab)
        self._create_startup_settings(tab)
        self._create_advanced_settings(tab)

        # Save button
        ctk.CTkButton(
            tab, text="💾 Save Settings", font=("Segoe UI Variable", 14, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            height=45, corner_radius=10, command=self._save_settings
        ).pack(fill="x", padx=30, pady=30)

    def _setup_event_handlers(self):
        """Set up event subscriptions."""
        try:
            event_bus.subscribe("state_changed", self._on_state_changed)
            event_bus.subscribe("window_changed", self._on_window_changed)
            event_bus.subscribe("notification", self._on_notification)
            event_bus.subscribe("agent_task_started", self._on_agent_task)
            event_bus.subscribe("agent_task_completed", self._on_agent_task)
        except Exception:
            pass  # Event bus may not be fully initialized yet

    def _create_api_settings(self, parent):
        """API provider settings with custom provider support and auto-detection."""
        section = self._create_settings_section(parent, "🔑 API Providers")

        # Header with refresh button
        header_frame = ctk.CTkFrame(section, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header_frame, text="Manage API Providers", font=("Segoe UI Variable", 16, "bold"),
            text_color=self.theme["accent"]
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            header_frame, text="🔄 Refresh All", font=("Segoe UI Variable", 11),
            fg_color=self.theme["accent"], width=120,
            command=self._refresh_providers
        ).pack(side="right", padx=10)

        # Status label
        self.provider_status_var = ctk.StringVar(value="Loading...")
        ctk.CTkLabel(
            header_frame, textvariable=self.provider_status_var,
            font=("Segoe UI", 10), text_color=self.theme["text_muted"]
        ).pack(side="right", padx=10)

        # Load current config
        cfg = get_config()

        # Built-in providers
        builtin_providers = [
            {"id": "groq", "name": "Groq", "icon": "⚡", "env_var": "GROQ_API_KEY",
             "default_url": "https://api.groq.com/openai/v1",
             "models_endpoint": "/models"},
            {"id": "openai", "name": "OpenAI", "icon": "🤖", "env_var": "OPENAI_API_KEY",
             "default_url": "https://api.openai.com/v1",
             "models_endpoint": "/models"},
            {"id": "anthropic", "name": "Anthropic", "icon": "🧠", "env_var": "ANTHROPIC_API_KEY",
             "default_url": "https://api.anthropic.com",
             "models_endpoint": None},
            {"id": "ollama", "name": "Ollama (Local)", "icon": "🏠", "env_var": "",
             "default_url": "http://localhost:11434", "local": True,
             "models_endpoint": "/api/tags"},
        ]

        self.api_vars = {}
        self.provider_frames = {}

        for prov in builtin_providers:
            self._create_provider_row(section, prov, cfg)

        # Custom provider section
        self._create_custom_provider_section(section, cfg)

        # Initial status update
        self._update_provider_status()

    def _create_provider_row(self, section, prov, cfg):
        """Create a row for a built-in provider with model auto-detection."""
        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", pady=8)

        prov_cfg = get_config().api_providers.get(prov["id"])
        enabled = prov_cfg.enabled if prov_cfg else False
        default = prov_cfg.default if prov_cfg else False

        # Store frame data for later updates
        frame_data = {
            "frame": frame,
            "status_var": ctk.StringVar(value="⚪ Unknown"),
            "model_var": ctk.StringVar(value=""),
            "models_combo": None,
            "model_var": ctk.StringVar(value=""),
        }
        self.provider_frames[prov["id"]] = frame_data

        # Header with icon and status
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=4)

        var = ctk.BooleanVar(value=enabled)
        self.api_vars[f"{prov['id']}_enabled"] = var

        ctk.CTkCheckBox(
            header, text=f"{prov['icon']} {prov['name']}", variable=var,
            font=("Segoe UI Variable", 12, "bold"), text_color=self.theme["text_primary"],
            command=lambda p=prov["id"]: self._on_provider_toggled(p)
        ).pack(side="left", padx=10)

        if default:
            ctk.CTkLabel(
                header, text="⭐ Default", font=("Segoe UI", 10),
                text_color=self.theme["accent"]
            ).pack(side="left", padx=10)

        # Status indicator
        status_label = ctk.CTkLabel(
            header, textvariable=frame_data["status_var"],
            font=("Segoe UI", 10), text_color=self.theme["text_muted"]
        )
        status_label.pack(side="left", padx=10)

        # API Key entry
        key_var = ctk.StringVar(value="")
        self.api_vars[f"{prov['id']}_key"] = key_var

        key_frame = ctk.CTkFrame(frame, fg_color="transparent")
        key_frame.pack(fill="x", padx=40, pady=4)
        key_frame.grid_columnconfigure(0, weight=1)

        # Show/hide password toggle
        show_var = ctk.BooleanVar(value=False)

        def toggle_show(p=prov["id"]):
            entry = self._get_key_entry(p)
            if entry:
                entry.configure(show="" if show_var.get() else "•")

        key_entry = ctk.CTkEntry(
            key_frame, placeholder_text=f"{prov['name']} API Key", textvariable=key_var,
            font=("Segoe UI Variable", 11), show="•"
        )
        key_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkCheckBox(
            key_frame, text="👁️", variable=show_var, width=30,
            command=toggle_show, font=("Segoe UI Variable", 12)
        ).pack(side="left")

        # Model selection dropdown (for providers with model detection)
        if prov.get("models_endpoint") or prov.get("local"):
            self._add_model_dropdown(key_frame, prov)

        # Test connection button
        ctk.CTkButton(
            key_frame, text="🔗 Test", width=70, font=("Segoe UI Variable", 10, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            corner_radius=8,
            command=lambda p=prov["id"]: self._test_provider_connection(p)
        ).pack(side="right", padx=3)

        # Auto-detect models button (for Ollama and cloud providers)
        if prov.get("models_endpoint") or prov.get("local"):
            ctk.CTkButton(
                key_frame, text="🔍 Detect Models", width=100, font=("Segoe UI Variable", 10, "bold"),
                fg_color=self.theme["info"], hover_color=self.theme["accent_alt"],
                corner_radius=8,
                command=lambda p=prov["id"]: self._detect_provider_models(p)
            ).pack(side="right", padx=3)

        # Save to .env button
        if prov.get("env_var"):
            ctk.CTkButton(
                key_frame, text="💾 Save", width=80, font=("Segoe UI Variable", 10, "bold"),
                fg_color=self.theme["success"], hover_color=self.theme["accent_hover"],
                corner_radius=8,
                command=lambda p=prov["id"], env=prov["env_var"]: self._save_api_key_to_env(p, env)
            ).pack(side="right", padx=3)

        # Set as default button
        ctk.CTkButton(
            key_frame, text="⭐ Default", width=80, font=("Segoe UI Variable", 10, "bold"),
            fg_color=self.theme["warning"], hover_color=self.theme["accent_hover"],
            corner_radius=8,
            command=lambda p=prov["id"]: self._set_default_provider(p)
        ).pack(side="right", padx=3)

        return frame

    def _get_key_entry(self, provider_id: str):
        """Find the key entry widget for a provider."""
        frame_data = self.provider_frames.get(provider_id)
        if frame_data and "frame" in frame_data:
            frame = frame_data["frame"]
            for child in frame.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for widget in child.winfo_children():
                        if isinstance(widget, ctk.CTkEntry) and "API Key" in str(widget.cget("placeholder_text")):
                            return widget
        return None

    def _add_model_dropdown(self, parent_frame, prov):
        """Add model selection dropdown with auto-detection."""
        provider_id = prov["id"]
        frame_data = self.provider_frames.get(provider_id, {})

        model_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        model_frame.pack(fill="x", padx=40, pady=(4, 0))

        ctk.CTkLabel(
            model_frame, text="Model:", font=("Segoe UI", 10),
            text_color=self.theme["text_secondary"], width=60
        ).pack(side="left", padx=(0, 10))

        model_var = ctk.StringVar(value="")
        self.api_vars[f"{provider_id}_model"] = model_var
        frame_data["model_var"] = model_var

        combo = ctk.CTkComboBox(
            model_frame, variable=model_var, width=250, font=("Segoe UI", 10),
            values=["Loading..."], state="readonly"
        )
        combo.pack(side="left", padx=(0, 10), fill="x", expand=True)
        frame_data["models_combo"] = combo
        frame_data["model_var"] = model_var

        # Set default from config
        prov_cfg = get_config().api_providers.get(prov["id"])
        if prov_cfg and prov_cfg.models:
            default_model = prov_cfg.models.get("chat") or prov_cfg.models.get("vision") or ""
            if default_model:
                model_var.set(default_model)

        # Refresh models button
        ctk.CTkButton(
            model_frame, text="↻", width=30, font=("Segoe UI", 10),
            fg_color=self.theme["accent"],
            command=lambda p=prov["id"]: self._detect_provider_models(p)
        ).pack(side="left", padx=3)

    def _create_custom_provider_section(self, section, cfg):
        """Create section for adding custom providers."""
        # Separator
        sep = ctk.CTkFrame(section, height=2, fg_color=self.theme["border"])
        sep.pack(fill="x", pady=15)

        # Custom provider header
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", pady=8)

        ctk.CTkLabel(
            header, text="➕ Add Custom Provider", font=("Segoe UI Variable", 16, "bold"),
            text_color=self.theme["accent"]
        ).pack(side="left", padx=10)

        # Custom provider form
        self.custom_provider_vars = {}

        form_frame = ctk.CTkFrame(section, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"], corner_radius=12)
        form_frame.pack(fill="x", pady=8, padx=10)

        # Row 1: Name & ID
        row1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(row1, text="Display Name:", font=("Segoe UI Variable", 11), text_color=self.theme["text_primary"], width=120).pack(side="left", padx=5)
        name_var = ctk.StringVar()
        self.custom_provider_vars["name"] = name_var
        ctk.CTkEntry(row1, textvariable=name_var, placeholder_text="My AI Provider", width=180).pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkLabel(row1, text="ID:", font=("Segoe UI Variable", 11), text_color=self.theme["text_primary"], width=40).pack(side="left", padx=5)
        id_var = ctk.StringVar()
        self.custom_provider_vars["id"] = id_var
        ctk.CTkEntry(row1, textvariable=id_var, placeholder_text="my_provider", width=150).pack(side="left", padx=5, fill="x", expand=True)

        # Row 2: Base URL & Env Var
        row2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(row2, text="Base URL:", font=("Segoe UI Variable", 11), text_color=self.theme["text_primary"], width=120).pack(side="left", padx=5)
        url_var = ctk.StringVar()
        self.custom_provider_vars["base_url"] = url_var
        ctk.CTkEntry(row2, textvariable=url_var, placeholder_text="https://api.example.com/v1", width=250).pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkLabel(row2, text="Env Var:", font=("Segoe UI Variable", 11), text_color=self.theme["text_primary"], width=80).pack(side="left", padx=5)
        env_var = ctk.StringVar()
        self.custom_provider_vars["env_var"] = env_var
        ctk.CTkEntry(row2, textvariable=env_var, placeholder_text="MY_PROVIDER_API_KEY", width=180).pack(side="left", padx=5, fill="x", expand=True)

        # Row 3: Models
        row3 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(row3, text="Models:", font=("Segoe UI Variable", 11), text_color=self.theme["text_primary"], width=120).pack(side="left", padx=5)

        model_types = ["vision", "chat", "fast", "reasoning"]
        self.custom_provider_vars["models"] = {}
        for mt in model_types:
            m_var = ctk.StringVar()
            self.custom_provider_vars["models"][mt] = m_var
            ctk.CTkEntry(row3, textvariable=m_var, placeholder_text=mt, width=110).pack(side="left", padx=2)

        # Row 4: Actions
        row4 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row4.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(
            row4, text="➕ Add Custom Provider", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            corner_radius=8, command=self._add_custom_provider
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            row4, text="🗑️ Clear Form", font=("Segoe UI Variable", 11, "bold"),
            fg_color=self.theme["warning"], hover_color=self.theme["accent_hover"],
            corner_radius=8, command=self._clear_custom_provider_form
        ).pack(side="left", padx=5)

    def _test_provider_connection(self, provider_id: str):
        """Test connection to a provider."""
        key_var = self.api_vars.get(f"{provider_id}_key")
        if not key_var or not key_var.get().strip():
            self._add_activity("Provider Test", f"Please enter API key for {provider_id}", "warning")
            return

        self._add_activity("Provider Test", f"Testing {provider_id} connection...", "info")
        self._run_async(self._async_test_provider(provider_id, key_var.get().strip()))

    async def _async_test_provider(self, provider_id: str, api_key: str):
        """Test provider connection asynchronously."""
        try:
            from active_assistant.core.providers import get_provider
            provider = provider_manager.get_provider(provider_id)
            if not provider:
                self.after(0, lambda: self._add_activity("Test Failed", f"Provider {provider_id} not loaded", "error"))
                return

            from active_assistant.core.providers import Message, ModelType, chat_completion
            messages = [Message(role="user", content="Test")]
            result = await chat_completion(messages, ModelType.FAST, provider=provider_id)
            self.after(0, lambda: self._add_activity("Test Success", f"{provider_id} connected successfully!", "success"))
        except Exception as err:
            self.after(0, lambda e=err: self._add_activity("Test Failed", f"{provider_id}: {str(e)}", "error"))

    def _save_api_key_to_env(self, provider_id: str, env_var: str):
        """Save API key to .env file."""
        key_var = self.api_vars.get(f"{provider_id}_key")
        if not key_var or not key_var.get().strip():
            self._add_activity("Save Failed", "Please enter API key first", "warning")
            return

        if not env_var:
            self._add_activity("Save Failed", "This provider doesn't use an environment variable", "warning")
            return

        key = key_var.get().strip()
        env_path = Path.cwd() / ".env"

        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        key_found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{env_var}="):
                new_lines.append(f"{env_var}={key}")
                key_found = True
            else:
                new_lines.append(line)

        if not key_found:
            new_lines.append(f"{env_var}={key}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        import os
        os.environ[env_var] = key

        self._add_activity("Saved", f"API key saved to .env for {provider_id}", "success")

    def _add_custom_provider(self):
        """Add custom provider from form."""
        for key, var in self.custom_provider_vars.items():
            if key == "models":
                continue
            if isinstance(var, ctk.StringVar) and not var.get().strip():
                self._add_activity("Add Failed", "Please fill in all fields", "warning")
                return

        models = {}
        for mt, var in self.custom_provider_vars["models"].items():
            if not var.get().strip():
                self._add_activity("Add Failed", f"Please enter {mt} model", "warning")
                return
            models[mt] = var.get().strip()

        name = self.custom_provider_vars["name"].get().strip()
        prov_id = self.custom_provider_vars["id"].get().strip()
        base_url = self.custom_provider_vars["base_url"].get().strip()
        env_var = self.custom_provider_vars["env_var"].get().strip()

        new_prov = {
            "id": prov_id,
            "name": name,
            "icon": "🔧",
            "env_var": env_var,
            "default_url": base_url,
            "models": models,
            "enabled": True,
            "custom": True
        }

        self._create_provider_row_custom(prov_id, prov_id, name, base_url, env_var, models)
        self._save_custom_provider_config(prov_id, name, base_url, env_var, models)
        self._clear_custom_provider_form()
        self._add_activity("Provider Added", f"Custom provider '{name}' added", "success")

    def _create_provider_row_custom(self, prov_id, display_name, name, base_url, env_var, models):
        """Create a row for a custom provider."""
        frame = ctk.CTkFrame(self.tabs["settings"], fg_color="transparent")

    def _save_custom_provider_config(self, prov_id, name, base_url, env_var, models):
        """Save custom provider to config."""
        cfg = get_config()
        cfg.api_providers[prov_id] = type('obj', (object,), {
            'enabled': True,
            'default': False,
            'api_key': '',
            'base_url': base_url,
            'models': models,
            'headers': {},
            'rate_limit': 30,
            'timeout': 30,
        })()
        cfg.save()

        if env_var:
            env_path = Path.cwd() / ".env"
            lines = []
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()

            new_lines = [f"# Custom provider: {name} ({prov_id})"] + lines
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def _clear_custom_provider_form(self):
        """Clear custom provider form."""
        for key, var in self.custom_provider_vars.items():
            if key == "models":
                for v in var.values():
                    if isinstance(v, ctk.StringVar):
                        v.set("")
            elif isinstance(var, ctk.StringVar):
                var.set("")

    def _refresh_providers(self):
        """Refresh all provider statuses and models."""
        self._update_provider_status()
        for prov_id in self.provider_frames:
            self._detect_provider_models(prov_id)

    def _update_provider_status(self):
        """Update provider status labels."""
        for prov_id, frame_data in self.provider_frames.items():
            status_var = frame_data.get("status_var")
            if status_var:
                key_var = self.api_vars.get(f"{prov_id}_key")
                if key_var and key_var.get().strip():
                    status_var.set("🟢 Connected")
                else:
                    status_var.set("🔴 Not configured")

    def _on_provider_toggled(self, provider_id: str):
        """Handle provider enable/disable toggle."""
        enabled = self.api_vars.get(f"{provider_id}_enabled", ctk.BooleanVar()).get()
        cfg = get_config()
        if provider_id in cfg.api_providers:
            prov_cfg = cfg.api_providers[provider_id]
            prov_cfg.enabled = enabled
            cfg.save()
            self._add_activity("Provider", f"{provider_id} {'enabled' if enabled else 'disabled'}", "info")

    def _detect_provider_models(self, provider_id: str):
        """Auto-detect models for a provider (Ollama or cloud)."""
        frame_data = self.provider_frames.get(provider_id)
        if not frame_data:
            return

        status_var = frame_data.get("status_var")
        if status_var:
            status_var.set("🟡 Detecting...")

        prov_cfg = get_config().api_providers.get(provider_id)
        if not prov_cfg:
            if status_var:
                status_var.set("🔴 Not configured")
            return

        base_url = prov_cfg.base_url or ""
        api_key = ""
        key_var = self.api_vars.get(f"{provider_id}_key")
        if key_var:
            api_key = key_var.get().strip()

        self._run_async(self._async_detect_models(provider_id, base_url, api_key))

    async def _async_detect_models(self, provider_id: str, base_url: str, api_key: str):
        """Detect models asynchronously for a provider."""
        try:
            models = []

            if provider_id == "ollama":
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base_url}/api/tags", timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = [m["name"] for m in data.get("models", [])]
            elif provider_id in ["groq", "openai"]:
                import aiohttp
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                async with aiohttp.ClientSession() as session:
                    models_endpoint = f"{base_url}/models" if provider_id != "anthropic" else None
                    if models_endpoint:
                        async with session.get(models_endpoint, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if provider_id == "groq":
                                    models = [m["id"] for m in data.get("data", [])]
                                elif provider_id == "openai":
                                    models = [m["id"] for m in data.get("data", [])]
            elif provider_id == "anthropic":
                models = [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307"
                ]

            if models:
                frame_data = self.provider_frames.get(provider_id)
                if frame_data and "models_combo" in frame_data:
                    combo = frame_data["models_combo"]
                    model_var = frame_data.get("model_var")
                    if combo:
                        combo.configure(values=sorted(models))
                        if models and not model_var.get():
                            model_var.set(models[0])

                cfg = get_config()
                if provider_id in cfg.api_providers:
                    prov_cfg = cfg.api_providers[provider_id]
                    if not prov_cfg.models:
                        prov_cfg.models = {}
                    model_map = {
                        "vision": next((m for m in models if "vision" in m.lower()), models[0]),
                        "chat": next((m for m in models if "chat" in m.lower() or "sonnet" in m.lower()), models[0]),
                        "fast": next((m for m in models if "fast" in m.lower() or "mini" in m.lower() or "haiku" in m.lower()), models[0]),
                        "reasoning": next((m for m in models if "reason" in m.lower() or "opus" in m.lower()), models[0]),
                    }
                    prov_cfg.models.update({k: v for k, v in model_map.items() if v})
                    cfg.save()

                self.after(0, lambda: self.provider_frames[provider_id]["status_var"].set(f"🟢 {len(models)} models"))
                self._add_activity("Models Detected", f"{provider_id}: {len(models)} models found", "success")
            else:
                self.after(0, lambda: self.provider_frames[provider_id]["status_var"].set("🟡 No models"))
        except Exception as e:
            self.after(0, lambda: self.provider_frames[provider_id]["status_var"].set("🔴 Error"))
            self._add_activity("Detection Failed", f"{provider_id}: {str(e)}", "error")

    def _create_permissions_settings(self, parent):
        """Permissions settings."""
        section = self._create_settings_section(parent, "🛡️ Permissions")

        self.perm_vars = {}
        perms = [
            ("read_files", "Read Files", True),
            ("write_files", "Write Files", True),
            ("delete_files", "Delete Files", False),
            ("execute_commands", "Execute Commands", True),
            ("web_search", "Web Search", True),
            ("web_crawl", "Web Crawl", True),
            ("use_vision", "Use Vision", True),
            ("use_voice", "Use Voice", True),
            ("multi_agent", "Multi-Agent", True),
            ("plugin_execution", "Plugin Execution", True),
        ]

        for key, label, default in perms:
            frame = ctk.CTkFrame(section, fg_color="transparent")
            frame.pack(fill="x", pady=5)

            cfg_val = getattr(get_config().rules.permissions, key, default)
            var = ctk.BooleanVar(value=cfg_val)
            self.perm_vars[key] = var

            ctk.CTkCheckBox(
                frame, text=label, variable=var, font=("Segoe UI Variable", 12, "bold"),
                text_color=self.theme["text_primary"],
                checkbox_width=24, checkbox_height=24,
                border_color=self.theme["border"], fg_color=self.theme["accent"]
            ).pack(side="left", padx=10)

            conf_key = f"confirm_{key}"
            conf_val = getattr(get_config().rules.confirmations, key.replace("use_", "").replace("_", ""), False)
            conf_var = ctk.BooleanVar(value=conf_val)
            self.perm_vars[conf_key] = conf_var

            ctk.CTkCheckBox(
                frame, text="Require Confirmation", variable=conf_var,
                font=("Segoe UI Variable", 10, "bold"),
                text_color=self.theme["text_muted"],
                checkbox_width=20, checkbox_height=20,
                border_color=self.theme["border"], fg_color=self.theme["border"]
            ).pack(side="right", padx=10)

    def _create_ui_settings(self, parent):
        """UI settings."""
        section = self._create_settings_section(parent, "🎨 Interface")

        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", pady=8)

        ctk.CTkLabel(frame, text="Theme:", font=("Segoe UI Variable", 12), text_color=self.theme["text_primary"]).pack(side="left", padx=10)

        self.theme_var = ctk.StringVar(value=get_config().ui.theme or "nvidia")
        ctk.CTkComboBox(
            frame, values=["nvidia", "dark", "light", "system", "futuristic", "matrix", "cyberpunk", "neon_blue", "sunset_ai"],
            variable=self.theme_var, width=160, font=("Segoe UI Variable", 11)
        ).pack(side="left", padx=10)

        frame2 = ctk.CTkFrame(section, fg_color="transparent")
        frame2.pack(fill="x", pady=8)

        ctk.CTkLabel(frame2, text="Accent Color:", font=("Segoe UI Variable", 12), text_color=self.theme["text_primary"]).pack(side="left", padx=10)

        self.accent_var = ctk.StringVar(value=get_config().ui.accent_color)
        ctk.CTkEntry(frame2, textvariable=self.accent_var, width=100, font=("Segoe UI Variable", 11)).pack(side="left", padx=10)

        frame3 = ctk.CTkFrame(section, fg_color="transparent")
        frame3.pack(fill="x", pady=8)

        ctk.CTkLabel(frame3, text="Font Size:", font=("Segoe UI Variable", 12), text_color=self.theme["text_primary"]).pack(side="left", padx=10)

        self.font_size_var = ctk.IntVar(value=get_config().ui.font_size)
        ctk.CTkSlider(frame3, from_=10, to=20, variable=self.font_size_var, width=150).pack(side="left", padx=10)
        ctk.CTkLabel(frame3, textvariable=self.font_size_var, font=("Segoe UI Variable", 11), text_color=self.theme["text_secondary"]).pack(side="left")

    def _create_startup_settings(self, parent):
        """Windows startup settings."""
        section = self._create_settings_section(parent, "🚀 Windows Startup")

        cfg = get_config().startup

        self.startup_vars = {}

        enabled_var = ctk.BooleanVar(value=cfg.enabled)
        self.startup_vars["enabled"] = enabled_var
        ctk.CTkCheckBox(
            section, text="Start with Windows", variable=enabled_var,
            font=("Segoe UI Variable", 12, "bold"), text_color=self.theme["text_primary"],
            checkbox_width=24, checkbox_height=24,
            border_color=self.theme["border"], fg_color=self.theme["accent"]
        ).pack(anchor="w", padx=10, pady=5)

        minimized_var = ctk.BooleanVar(value=cfg.run_minimized)
        self.startup_vars["run_minimized"] = minimized_var
        ctk.CTkCheckBox(
            section, text="Start Minimized to Tray", variable=minimized_var,
            font=("Segoe UI Variable", 12, "bold"), text_color=self.theme["text_primary"],
            checkbox_width=24, checkbox_height=24,
            border_color=self.theme["border"], fg_color=self.theme["accent"]
        ).pack(anchor="w", padx=30, pady=5)

        admin_var = ctk.BooleanVar(value=cfg.run_as_admin)
        self.startup_vars["run_as_admin"] = admin_var
        ctk.CTkCheckBox(
            section, text="Run as Administrator", variable=admin_var,
            font=("Segoe UI Variable", 12, "bold"), text_color=self.theme["text_primary"],
            checkbox_width=24, checkbox_height=24,
            border_color=self.theme["border"], fg_color=self.theme["accent"]
        ).pack(anchor="w", padx=30, pady=5)

        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Startup Delay (seconds):", font=("Segoe UI Variable", 12), text_color=self.theme["text_primary"]).pack(side="left", padx=5)

        delay_var = ctk.IntVar(value=cfg.delay_seconds)
        self.startup_vars["delay_seconds"] = delay_var
        ctk.CTkSlider(frame, from_=0, to=60, variable=delay_var, width=150).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(frame, textvariable=delay_var, font=("Segoe UI Variable", 11), text_color=self.theme["text_secondary"]).pack(side="left", padx=5)

        ctk.CTkButton(
            section, text="🔧 Configure Startup", font=("Segoe UI Variable", 12, "bold"),
            fg_color=self.theme["accent"], hover_color=self.theme["accent_hover"],
            command=self._configure_startup
        ).pack(anchor="w", padx=10, pady=10)

    def _create_advanced_settings(self, parent):
        """Advanced settings."""
        section = self._create_settings_section(parent, "⚙️ Advanced")

        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", pady=8)

        ctk.CTkLabel(frame, text="Log Level:", font=("Segoe UI Variable", 12), text_color=self.theme["text_primary"]).pack(side="left", padx=10)

        self.log_level_var = ctk.StringVar(value=get_config().logging.level)
        ctk.CTkComboBox(
            frame, values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self.log_level_var, width=150, font=("Segoe UI Variable", 11)
        ).pack(side="left", padx=10)

        frame2 = ctk.CTkFrame(section, fg_color="transparent")
        frame2.pack(fill="x", pady=8)

        ctk.CTkLabel(frame2, text="Max Workers:", font=("Segoe UI Variable", 12), text_color=self.theme["text_primary"]).pack(side="left", padx=10)

        self.workers_var = ctk.IntVar(value=get_config().performance.max_worker_threads)
        ctk.CTkSlider(frame2, from_=1, to=16, variable=self.workers_var, width=150).pack(side="left", padx=10)
        ctk.CTkLabel(frame2, textvariable=self.workers_var, font=("Segoe UI Variable", 11), text_color=self.theme["text_secondary"]).pack(side="left")

        local_var = ctk.BooleanVar(value=get_config().privacy.local_only_mode)
        self.privacy_vars = {"local_only": local_var}
        ctk.CTkCheckBox(
            section, text="Local Only Mode (No Cloud APIs)", variable=local_var,
            font=("Segoe UI Variable", 12, "bold"), text_color=self.theme["text_primary"],
            checkbox_width=24, checkbox_height=24,
            border_color=self.theme["border"], fg_color=self.theme["accent"]
        ).pack(anchor="w", padx=10, pady=5)

    def _create_settings_section(self, parent, title: str) -> ctk.CTkFrame:
        """Create a settings section."""
        section = ctk.CTkFrame(parent, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"])
        section.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            section, text=title, font=("Segoe UI Variable", 16, "bold"),
            text_color=self.theme["accent"]
        ).pack(anchor="w", padx=15, pady=(15, 10))

        content = ctk.CTkFrame(section, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=(0, 15))

        return content

    def _toggle_monitoring(self):
        """Toggle monitoring pause/resume."""
        state.set_paused(not state.is_paused)

    def _toggle_vision(self):
        """Toggle vision monitoring pause/resume."""
        self.vision_paused.set(not self.vision_paused.get())
        state.set_paused(self.vision_paused.get())

    def _organize_downloads(self):
        """Trigger downloads organization."""
        self._run_async(agent_manager.run_agent("file_organizer", "Organize downloads now"))

    def _capture_screen(self):
        """Capture and analyze current screen."""
        self._analyze_current_screen()

    def _analyze_current_screen(self):
        """Analyze current screen with vision agent."""
        self.vision_results.configure(state="normal")
        self.vision_results.delete("1.0", "end")
        self.vision_results.insert("1.0", "Capturing screen and analyzing...\n")
        self.vision_results.configure(state="disabled")

        self._run_async(self._do_vision_analysis())

    async def _do_vision_analysis(self):
        """Perform vision analysis."""
        try:
            result = await agent_manager.run_agent("vision_analyst", "Analyze current screen for issues")
            self.after(0, lambda: self._update_vision_results(result.output if result.success else result.error))
        except Exception as e:
            self.after(0, lambda: self._update_vision_results(f"Error: {e}"))

    def _update_vision_results(self, text: str):
        """Update vision results display."""
        self.vision_results.configure(state="normal")
        self.vision_results.delete("1.0", "end")
        self.vision_results.insert("1.0", text)
        self.vision_results.configure(state="disabled")

    def _test_voice(self):
        """Test voice assistant."""
        self._run_async(voice_assistant.speak("Voice assistant is working correctly."))

    def _test_agent(self, agent_id: str):
        """Test an agent."""
        self._run_async(agent_manager.run_agent(agent_id, "Run a self-test"))

    def _view_agent_logs(self, agent_id: str):
        """View agent logs."""
        pass

    def _run_plugin(self, plugin_name: str):
        """Run a plugin."""
        pass

    def _show_plugin_details(self, plugin_name: str):
        """Show plugin details."""
        pass

    def _perform_search(self):
        """Perform multimodal search."""
        query = self.search_input.get().strip()
        if not query:
            return

        for widget in self.search_results.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.search_results, text="Searching...", font=("Segoe UI", 14),
            text_color=self.theme["text_muted"]
        ).pack(pady=50)

        self._run_async(self._do_search(query))

    async def _do_search(self, query: str):
        """Execute search."""
        try:
            results = await web_manager.search(query)
            self.after(0, lambda: self._display_search_results(results))
        except Exception as e:
            self.after(0, lambda: self._display_search_error(str(e)))

    def _display_search_results(self, results: List):
        """Display search results."""
        for widget in self.search_results.winfo_children():
            widget.destroy()

        for r in results:
            item = ctk.CTkFrame(self.search_results, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"])
            item.pack(fill="x", padx=5, pady=3)

            ctk.CTkLabel(item, text=r.title, font=("Segoe UI", 12, "bold"), text_color=self.theme["text_primary"], anchor="w").pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(item, text=r.url, font=("Segoe UI", 10), text_color=self.theme["accent"], anchor="w").pack(fill="x", padx=10)
            ctk.CTkLabel(item, text=r.description[:200], font=("Segoe UI", 10), text_color=self.theme["text_secondary"], anchor="w", wraplength=600).pack(fill="x", padx=10, pady=(0, 8))

    def _display_search_error(self, error: str):
        """Display search error."""
        for widget in self.search_results.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.search_results, text=f"Search error: {error}",
            font=("Segoe UI", 14), text_color=self.theme["error"]
        ).pack(pady=50)

    def _save_settings(self):
        """Save settings to config."""
        from active_assistant.core.config import config

        for key, var in self.api_vars.items():
            parts = key.split("_")
            if len(parts) == 2:
                prov, attr = parts
                config.update(f"api_providers.{prov}.{attr}", var.get())

        for key, var in self.perm_vars.items():
            if key.startswith("confirm_"):
                perm_key = key[8:]
                config.update(f"rules.confirmations.{perm_key}", var.get())
            else:
                config.update(f"rules.permissions.{key}", var.get())

        config.update("ui.theme", self.theme_var.get())
        config.update("ui.accent_color", self.accent_var.get())
        config.update("ui.font_size", self.font_size_var.get())

        for key, var in self.startup_vars.items():
            config.update(f"startup.{key}", var.get())

        config.update("logging.level", self.log_level_var.get())
        config.update("performance.max_worker_threads", self.workers_var.get())
        config.update("privacy.local_only_mode", self.privacy_vars["local_only"].get())

        config.save()

        self._add_activity("Settings", "Configuration saved", "success")

    def _configure_startup(self):
        """Configure Windows startup."""
        from active_assistant.startup.manager import startup_manager
        self._run_async(startup_manager.configure())

    async def _async_shutdown(self):
        """Async shutdown."""
        await agent_manager.shutdown()
        await plugin_manager.shutdown()
        await voice_assistant.stop()
        state.request_shutdown()
        self.quit()
        self.destroy()

    def _on_state_changed(self, event):
        """Handle state changes."""
        new_state = event.payload.get("new", "")
        self.after(0, lambda: self._update_state_ui(new_state))

    def _update_state_ui(self, new_state: str):
        """Update UI based on state."""
        status_map = {
            "running": "running",
            "paused": "paused",
            "stopping": "stopped",
            "stopped": "stopped",
            "error": "error",
        }
        status = status_map.get(new_state, "idle")
        self.status_indicator.set_status(status)

    def _on_window_changed(self, event):
        """Handle window changes."""
        self.after(0, lambda: self._update_vision_preview(event.payload))

    def _on_notification(self, event):
        """Handle notifications."""
        notif = event.payload
        self.after(0, lambda: self._add_activity(
            notif.get("title", ""), notif.get("message", ""), notif.get("level", "info")
        ))

    def _on_agent_task(self, event):
        """Handle agent task events."""
        self.after(0, self._refresh_agents)

    def _start_updates(self):
        """Start periodic UI updates."""
        self._update_metrics()
        self.after(2000, self._start_updates)

    def _update_metrics(self):
        """Update dashboard metrics."""
        metrics = state.metrics

        self.metric_cards["uptime"].update_value(f"{int(metrics.uptime_seconds)}s")
        self.metric_cards["captures"].update_value(str(metrics.screens_captured))
        self.metric_cards["issues"].update_value(str(metrics.issues_detected))
        self.metric_cards["tools"].update_value(str(metrics.tools_executed))

    def _add_activity(self, title: str, message: str, level: str = "info"):
        """Add activity to feed."""
        colors = {
            "info": self.theme["info"],
            "warning": self.theme["warning"],
            "error": self.theme["error"],
            "success": self.theme["success"],
        }
        color = colors.get(level, self.theme["text_primary"])

        item = ctk.CTkFrame(self.activity_list, fg_color=self.theme["bg_card"], border_width=1, border_color=self.theme["border"])
        item.pack(fill="x", padx=5, pady=3)
        item.grid_columnconfigure(1, weight=1)

        indicator = ctk.CTkFrame(item, width=4, fg_color=color)
        indicator.grid(row=0, column=0, rowspan=2, sticky="ns", padx=0)

        ctk.CTkLabel(
            item, text=title, font=("Segoe UI", 11, "bold"),
            text_color=self.theme["text_primary"], anchor="w"
        ).grid(row=0, column=1, sticky="ew", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            item, text=message[:100], font=("Segoe UI", 10),
            text_color=self.theme["text_secondary"], anchor="w"
        ).grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 8))

        time_str = datetime.now().strftime("%H:%M:%S")
        ctk.CTkLabel(
            item, text=time_str, font=("Segoe UI", 9),
            text_color=self.theme["text_muted"]
        ).grid(row=0, column=2, rowspan=2, padx=15)

        children = self.activity_list.winfo_children()
        if len(children) > 50:
            children[0].destroy()

    def _update_vision_preview(self, window_data: Dict):
        """Update vision preview with latest capture."""
        title = window_data.get("title", "Unknown")
        self.vision_image_label.configure(text=f"Monitoring: {title}")

    def _upload_file(self):
        """Open file dialog and add file to attachments."""
        from tkinter import filedialog
        filetypes = [
            ("All files", "*.*"),
            ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("Documents", "*.pdf *.docx *.doc *.txt *.md *.xlsx *.csv *.pptx"),
            ("Code", "*.py *.js *.ts *.html *.css *.json *.yaml *.yml *.cpp *.c *.h *.rs *.go"),
            ("Archives", "*.zip *.tar *.gz *.7z *.rar"),
        ]
        files = filedialog.askopenfilenames(
            title="Select files to attach",
            filetypes=filetypes
        )

        for file_path in files:
            self._add_attachment(file_path)

    def _add_attachment(self, file_path: str):
        """Add file to attachment list and show in UI."""
        import os
        from pathlib import Path

        file_info = {
            "path": file_path,
            "name": Path(file_path).name,
            "size": os.path.getsize(file_path),
            "type": self._get_file_type(file_path)
        }

        self.chat_attachments.append(file_info)
        self._update_attachment_ui()

    def _get_file_type(self, file_path: str) -> str:
        """Determine file type for display."""
        ext = Path(file_path).suffix.lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            return "image"
        elif ext in ['.pdf', '.docx', '.doc', '.txt', '.md', '.xlsx', '.csv', '.pptx']:
            return "document"
        elif ext in ['.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml', '.cpp', '.c', '.h', '.rs', '.go']:
            return "code"
        elif ext in ['.zip', '.tar', '.gz', '.7z', '.rar']:
            return "archive"
        elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
            return "video"
        elif ext in ['.mp3', '.wav', '.flac', '.m4a']:
            return "audio"
        return "file"

    def _update_attachment_ui(self):
        """Update attachment display in UI."""
        for widget in self.attachment_frame.winfo_children():
            widget.destroy()

        if not self.chat_attachments:
            self.attachment_frame.grid_remove()
            return

        self.attachment_frame.grid()

        for i, att in enumerate(self.chat_attachments):
            att_frame = ctk.CTkFrame(self.attachment_frame, fg_color=self.theme["bg_tertiary"])
            att_frame.pack(fill="x", padx=5, pady=2)

            icons = {"image": "🖼️", "document": "📄", "code": "💻", "archive": "📦", "video": "🎬", "audio": "🎵", "file": "📎"}
            icon = icons.get(att["type"], "📎")

            ctk.CTkLabel(
                att_frame, text=f"{icon} {att['name']}", font=("Segoe UI", 11),
                text_color=self.theme["text_primary"]
            ).pack(side="left", padx=10, pady=5)

            size_kb = att['size'] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
            ctk.CTkLabel(
                att_frame, text=size_str, font=("Segoe UI", 9),
                text_color=self.theme["text_muted"]
            ).pack(side="left", padx=10)

            ctk.CTkButton(
                att_frame, text="✕", width=32, height=32,
                fg_color=self.theme["error"], hover_color="#dc2626",
                command=lambda idx=i: self._remove_attachment(idx)
            ).pack(side="right", padx=5)

    def _remove_attachment(self, index: int):
        """Remove attachment from list."""
        if 0 <= index < len(self.chat_attachments):
            self.chat_attachments.pop(index)
            self._update_attachment_ui()

    def _send_chat(self):
        """Send chat message with attachments."""
        text = self.chat_input.get("1.0", "end-1c").strip()
        if not text and not self.chat_attachments:
            return

        self.chat_input.delete("1.0", "end")

        message_parts = [text] if text else []

        for att in self.chat_attachments:
            message_parts.append(f"\n[Attached: {att['name']} ({att['type']})]")

        full_message = "\n".join(message_parts)

        self._add_chat_message("user", full_message)

        self.chat_attachments.clear()
        self._update_attachment_ui()

        self._run_async(self._process_chat(full_message))

    async def _process_chat(self, text: str):
        """Process chat with agent."""
        try:
            result = await agent_manager.delegate_to_best(text)
            response = result.output if result.success else f"Error: {result.error}"
            self.after(0, lambda: self._add_chat_message("assistant", response))
        except Exception as e:
            self.after(0, lambda: self._add_chat_message("assistant", f"Error: {e}"))

    def _add_chat_message(self, role: str, content: str):
        """Add message to chat."""
        msg = ChatMessage(self.chat_scroll, role, content)
        msg.pack(fill="x", padx=10, pady=5, anchor="e" if role == "user" else "w")

        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _run_async(self, coro):
        """Run async coroutine from sync context (thread-safe)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            import threading

            def run_in_thread():
                asyncio.run(coro)

            threading.Thread(target=run_in_thread, daemon=True).start()

    def _on_window_resize(self, event):
        """Handle window resize for responsive layout adjustments."""
        if event.widget == self:
            width = self.winfo_width()
            if width > 1200:
                new_width = 260
            elif width > 800:
                new_width = 220
            else:
                new_width = 180

            current_width = self.sidebar.winfo_width()
            if abs(current_width - new_width) > 20:
                self.sidebar.configure(width=new_width)


def main():
    """Run the Active Assistant UI."""
    app = MainWindow()
    app.mainloop()