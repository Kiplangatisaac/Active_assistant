"""
Windows startup management for Active Assistant.
Creates shortcuts, registry entries, and protocol handlers.
"""
from __future__ import annotations

import os
import sys
import winreg
from pathlib import Path
from typing import Optional

from loguru import logger
from active_assistant.core.config import get_config


class StartupManager:
    """Manage Windows startup integration."""
    
    def __init__(self):
        self.config = get_config().startup
        self.app_name = "ActiveAssistant"
        self.exe_path = self._get_exe_path()
    
    def _get_exe_path(self) -> Path:
        """Get the executable path."""
        # If frozen (PyInstaller)
        if getattr(sys, 'frozen', False):
            return Path(sys.executable)
        # Otherwise use python -m
        return Path(sys.executable).parent / "python.exe"
    
    def _get_startup_args(self) -> str:
        """Get command line arguments for startup."""
        args = []
        if self.config.run_minimized:
            args.append("--minimized")
        if self.config.delay_seconds > 0:
            args.append(f"--startup-delay={self.config.delay_seconds}")
        return " ".join(args)
    
    def is_startup_enabled(self) -> bool:
        """Check if startup is currently enabled."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            value, _ = winreg.QueryValueEx(key, self.app_name)
            winreg.CloseKey(key)
            return bool(value)
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking startup status: {e}")
            return False
    
    def enable_startup(self) -> bool:
        """Enable Windows startup."""
        try:
            # Create shortcut in Startup folder as backup
            self._create_shortcut()
            
            # Registry entry (more reliable)
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            
            cmd = f'"{self.exe_path}" {self._get_startup_args()}'
            if self.config.run_as_admin:
                # For admin, use Task Scheduler instead
                return self._create_scheduled_task()
            
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            
            logger.info(f"Startup enabled: {cmd}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable startup: {e}")
            return False
    
    def disable_startup(self) -> bool:
        """Disable Windows startup."""
        try:
            # Remove registry entry
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, self.app_name)
            winreg.CloseKey(key)
            
            # Remove shortcut
            self._remove_shortcut()
            
            # Remove scheduled task
            self._remove_scheduled_task()
            
            logger.info("Startup disabled")
            return True
            
        except FileNotFoundError:
            return True
        except Exception as e:
            logger.error(f"Failed to disable startup: {e}")
            return False
    
    def _create_shortcut(self) -> bool:
        """Create shortcut in Startup folder."""
        try:
            import win32com.client
            
            startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            shortcut_path = startup_folder / f"{self.app_name}.lnk"
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = str(self.exe_path)
            shortcut.Arguments = self._get_startup_args()
            shortcut.WorkingDirectory = str(self.exe_path.parent)
            shortcut.Description = "Active Assistant - AI-powered desktop assistant"
            shortcut.Save()
            
            return True
        except Exception as e:
            logger.warning(f"Could not create shortcut: {e}")
            return False
    
    def _remove_shortcut(self) -> bool:
        """Remove shortcut from Startup folder."""
        try:
            startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            shortcut_path = startup_folder / f"{self.app_name}.lnk"
            if shortcut_path.exists():
                shortcut_path.unlink()
            return True
        except Exception:
            return False
    
    def _create_scheduled_task(self) -> bool:
        """Create scheduled task for admin startup."""
        try:
            import subprocess
            
            task_name = f"ActiveAssistant_{self.app_name}"
            cmd = f'"{self.exe_path}" {self._get_startup_args()}'
            
            # Create task that runs at logon with highest privileges
            ps_script = f'''
            $action = New-ScheduledTaskAction -Execute "{self.exe_path}" -Argument "{self._get_startup_args()}"
            $trigger = New-ScheduledTaskTrigger -AtLogOn
            $principal = New-ScheduledTaskPrincipal -UserId (Get-CimInstance Win32_ComputerSystem).UserName -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
            Register-ScheduledTask -TaskName "{task_name}" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
            '''
            
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Scheduled task created for admin startup")
                return True
            else:
                logger.error(f"Failed to create scheduled task: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Scheduled task creation failed: {e}")
            return False
    
    def _remove_scheduled_task(self) -> bool:
        """Remove scheduled task."""
        try:
            import subprocess
            
            task_name = f"ActiveAssistant_{self.app_name}"
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", task_name, "/F"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def register_protocol(self) -> bool:
        """Register custom URI protocol (active-assistant://)."""
        try:
            # HKCU\Software\Classes\active-assistant
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\active-assistant")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Active Assistant Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            
            # Icon
            icon_key = winreg.CreateKey(key, r"DefaultIcon")
            winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, f"{self.exe_path},0")
            
            # Command
            cmd_key = winreg.CreateKey(key, r"shell\open\command")
            cmd = f'"{self.exe_path}" --protocol "%1"'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            
            winreg.CloseKey(key)
            winreg.CloseKey(icon_key)
            winreg.CloseKey(cmd_key)
            
            logger.info("Protocol handler registered: active-assistant://")
            return True
            
        except Exception as e:
            logger.error(f"Protocol registration failed: {e}")
            return False
    
    def unregister_protocol(self) -> bool:
        """Unregister custom URI protocol."""
        try:
            import winreg
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\active-assistant\shell\open\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\active-assistant\DefaultIcon")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\active-assistant\shell\open")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\active-assistant\shell")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\active-assistant")
            return True
        except Exception:
            return False
    
    async def configure(self) -> bool:
        """Interactive configuration."""
        # This would show a dialog - for now just apply config
        if self.config.enabled:
            return self.enable_startup()
        else:
            return self.disable_startup()
    
    def get_status(self) -> dict:
        """Get startup status."""
        return {
            "enabled": self.is_startup_enabled(),
            "configured_enabled": self.config.enabled,
            "run_minimized": self.config.run_minimized,
            "run_as_admin": self.config.run_as_admin,
            "delay_seconds": self.config.delay_seconds,
            "exe_path": str(self.exe_path),
        }


# Global instance
startup_manager = StartupManager()


def configure_startup(enabled: bool = None, **kwargs) -> bool:
    """Configure startup with optional parameters."""
    if enabled is not None:
        get_config().update("startup.enabled", enabled)
    for key, value in kwargs.items():
        if hasattr(get_config().startup, key):
            get_config().update(f"startup.{key}", value)
    return startup_manager.configure()