"""Plugins module for Active Assistant."""
from .manager import (
    plugin_manager, PluginManager, PluginBase, PluginInfo, PluginAction,
    DocumentHandlerPlugin, CodeAnalyzerPlugin, MediaProcessorPlugin,
    SystemMonitorPlugin, NetworkToolsPlugin, ArchiveManagerPlugin, DatabaseToolsPlugin,
    PluginSandbox
)

__all__ = [
    "plugin_manager", "PluginManager", "PluginBase", "PluginInfo", "PluginAction",
    "DocumentHandlerPlugin", "CodeAnalyzerPlugin", "MediaProcessorPlugin",
    "SystemMonitorPlugin", "NetworkToolsPlugin", "ArchiveManagerPlugin", "DatabaseToolsPlugin",
    "PluginSandbox",
]