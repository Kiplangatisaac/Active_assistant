"""Core module for Active Assistant."""
from .config import get_config, load_config, ConfigManager, ActiveAssistantConfig
from .state import state, event_bus, StateManager, SettingsStore
from .providers import provider_manager, get_provider, chat_completion, stream_chat_completion
from .monitor import screen_monitor, initialize_monitor, shutdown_monitor
from .logging import setup_logging, get_logger

__all__ = [
    "get_config", "load_config", "ConfigManager", "ActiveAssistantConfig",
    "state", "event_bus", "StateManager", "SettingsStore",
    "provider_manager", "get_provider", "chat_completion", "stream_chat_completion",
    "screen_monitor", "initialize_monitor", "shutdown_monitor",
    "setup_logging", "get_logger",
]