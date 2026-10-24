"""Active Assistant - AI-powered desktop assistant with vision, voice, and plugins."""

__version__ = "2.0.0"
__author__ = "Isaac"
__license__ = "MIT"

# Core exports
from .core.config import get_config, load_config, ConfigManager, ActiveAssistantConfig
from .core.state import state, event_bus, StateManager, SettingsStore
from .core.providers import provider_manager, get_provider, chat_completion, stream_chat_completion
from .core.monitor import screen_monitor, initialize_monitor, shutdown_monitor
from .core.logging import setup_logging, get_logger

# Tools
from .tools.base import tool_registry, Tool, ToolResult, ToolExecutor, ToolCategory, ConfirmationLevel

# Agents
from .agents.manager import agent_manager, AgentManager, BaseAgent, AgentConfig

# Plugins
from .plugins.manager import plugin_manager, PluginManager, PluginBase, PluginInfo

# Voice
from .voice.assistant import voice_assistant, initialize_voice, start_voice, stop_voice

# Web
from .web.crawler import web_manager, initialize_web, search_web, crawl_web

# Startup
from .startup.manager import startup_manager, StartupManager

# UI
from .ui.main_window import main as run_ui

# Tray
from .tray import TrayIcon

# Main
from .main import main, run_tray_mode, run_console_mode, run_ui_mode, run_setup

__all__ = [
    # Version
    "__version__",
    # Core
    "get_config", "load_config", "ConfigManager", "ActiveAssistantConfig",
    "state", "event_bus", "StateManager", "SettingsStore",
    "provider_manager", "get_provider", "chat_completion", "stream_chat_completion",
    "screen_monitor", "initialize_monitor", "shutdown_monitor",
    "setup_logging", "get_logger",
    # Tools
    "tool_registry", "Tool", "ToolResult", "ToolExecutor", "ToolCategory", "ConfirmationLevel",
    # Agents
    "agent_manager", "AgentManager", "BaseAgent", "AgentConfig",
    # Plugins
    "plugin_manager", "PluginManager", "PluginBase", "PluginInfo",
    # Voice
    "voice_assistant", "initialize_voice", "start_voice", "stop_voice",
    # Web
    "web_manager", "initialize_web", "search_web", "crawl_web",
    # Startup
    "startup_manager", "StartupManager",
    # UI
    "run_ui",
    # Tray
    "TrayIcon",
    # Main
    "main", "run_tray_mode", "run_console_mode", "run_ui_mode", "run_setup",
]