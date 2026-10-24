"""
System tray integration for Active Assistant.
Provides quick access, status display, and controls.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import pystray
from PIL import Image, ImageDraw
from loguru import logger

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus, AppState
from active_assistant.agents.manager import agent_manager
from active_assistant.plugins.manager import plugin_manager


class TrayIcon:
    """System tray icon for Active Assistant."""
    
    def __init__(self, on_open_ui=None, on_exit=None):
        self.icon: Optional[pystray.Icon] = None
        self.on_open_ui = on_open_ui
        self.on_exit = on_exit
        self._thread: Optional[threading.Thread] = None
        
        # Load config
        self.config = get_config()
    
    def create_icon_image(self, active: bool = True) -> Image.Image:
        """Create dynamic tray icon image."""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Color based on state
        if not active:
            color = (249, 115, 22, 255)  # Orange - Paused
        elif state.state == AppState.ERROR:
            color = (248, 113, 113, 255)  # Red - Error
        else:
            color = (34, 197, 94, 255)  # Green - Active
        
        # Outer circle
        draw.ellipse((4, 4, 60, 60), fill=color)
        
        # Inner ring
        draw.ellipse((14, 14, 50, 50), fill=(255, 255, 255, 230))
        
        # Center dot
        draw.ellipse((24, 24, 40, 40), fill=color)
        
        # Center dot (smaller, for "active" indicator)
        draw.ellipse((29, 29, 35, 35), fill=(255, 255, 255, 255))
        
        return img
    
    def _get_status_text(self, item) -> str:
        """Get dynamic status text for menu."""
        metrics = state.metrics
        status = state.state.value.capitalize()
        return f"Status: {status} | {int(metrics.uptime_seconds)}s uptime"
    
    def _get_toggle_text(self, item) -> str:
        """Get dynamic pause/resume text."""
        return "Pause Monitoring" if not state.is_paused else "Resume Monitoring"
    
    def toggle_pause(self, icon: pystray.Icon, item):
        """Toggle monitoring pause/resume."""
        try:
            if state.is_paused:
                state.set_paused(False)
                icon.icon = self.create_icon_image(active=True)
                icon.title = "Active Assistant (Active)"
                logger.info("[Tray] Monitoring RESUMED.")
            else:
                state.set_paused(True)
                icon.icon = self.create_icon_image(active=False)
                icon.title = "Active Assistant (Paused)"
                logger.info("[Tray] Monitoring PAUSED.")
        except Exception as e:
            logger.error(f"Tray toggle error: {e}")
    
    def open_dashboard(self, icon: pystray.Icon, item):
        """Open the main UI window."""
        logger.info("[Tray] Opening dashboard")
        if self.on_open_ui:
            try:
                self.on_open_ui()
            except Exception as e:
                logger.error(f"Failed to open UI: {e}")
    
    def quick_capture(self, icon: pystray.Icon, item):
        """Quick screen capture analysis."""
        logger.info("[Tray] Quick capture requested")
        state.add_notification("Quick Capture", "Analyzing current screen...", "info")
    
    def organize_downloads(self, icon: pystray.Icon, item):
        """Organize downloads."""
        logger.info("[Tray] Organize downloads requested")
        state.add_notification("Organizer", "Organizing downloads...", "info")
    
    def show_status(self, icon: pystray.Icon, item):
        """Show current status."""
        metrics = state.metrics
        agents = len(agent_manager.list_agents())
        plugins = len(plugin_manager.list_plugins())
        
        message = (
            f"Uptime: {int(metrics.uptime_seconds)}s\n"
            f"Captures: {metrics.screens_captured}\n"
            f"Issues: {metrics.issues_detected}\n"
            f"Tools: {metrics.tools_executed}\n"
            f"Agents: {agents} | Plugins: {plugins}"
        )
        
        try:
            from plyer import notification
            notification.notify(
                title="Active Assistant Status",
                message=message,
                app_name="Active Assistant",
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Notification failed: {e}")
        
        state.add_notification("Status", message, "info")
    
    def exit_app(self, icon: pystray.Icon, item):
        """Exit the application."""
        logger.info("[Tray] Exiting application")
        state.request_shutdown()
        if self.on_exit:
            try:
                self.on_exit()
            except Exception as e:
                logger.error(f"Exit callback error: {e}")
        icon.stop()
    
    def build_menu(self) -> pystray.Menu:
        """Build the tray menu."""
        return pystray.Menu(
            pystray.MenuItem(
                self._get_status_text,
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Open Dashboard",
                self.open_dashboard,
                default=True,
            ),
            pystray.MenuItem(
                self._get_toggle_text,
                self.toggle_pause,
            ),
            pystray.MenuItem(
                "Quick Screen Analysis",
                self.quick_capture,
            ),
            pystray.MenuItem(
                "Organize Downloads",
                self.organize_downloads,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Status",
                self.show_status,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                self.exit_app,
            ),
        )
    
    def run(self):
        """Run the tray icon (blocking)."""
        self.icon = pystray.Icon(
            name="ActiveAssistant",
            icon=self.create_icon_image(active=True),
            title="Active Assistant (Active)",
            menu=self.build_menu(),
        )
        self.icon.run()
    
    def run_in_thread(self):
        """Run the tray icon in a background thread."""
        self._thread = threading.Thread(target=self.run, daemon=True, name="TrayIcon")
        self._thread.start()
    
    def stop(self):
        """Stop the tray icon."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
    
    def update_icon(self):
        """Update the icon based on current state."""
        if self.icon:
            try:
                self.icon.icon = self.create_icon_image(active=not state.is_paused)
                self.icon.title = (
                    "Active Assistant (Paused)" if state.is_paused
                    else "Active Assistant (Active)"
                )
            except Exception as e:
                logger.warning(f"Icon update failed: {e}")
