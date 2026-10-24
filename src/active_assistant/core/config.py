"""
Configuration management for Active Assistant.
Supports YAML config files, environment variables, and runtime updates.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from copy import deepcopy

import ruamel.yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


# ============================================================
# Pydantic Models for Type-Safe Configuration
# ============================================================

class APIProviderConfig(BaseModel):
    """Configuration for a single API provider."""
    enabled: bool = False
    default: bool = False
    api_key: str = ""
    base_url: str = ""
    models: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    rate_limit: int = 30
    timeout: int = 30
    
    @field_validator('api_key', mode='before')
    @classmethod
    def resolve_api_key(cls, v: str, info) -> str:
        """Allow API key to be set via environment variable."""
        if not v:
            # Try to get from environment
            provider_name = info.data.get('provider_name', '').upper()
            if provider_name:
                env_key = f"{provider_name}_API_KEY"
                v = os.environ.get(env_key, "")
        return v


class ScreenMonitoringConfig(BaseModel):
    """Screen monitoring configuration."""
    enabled: bool = True
    check_interval_seconds: int = 5
    hash_difference_threshold: int = 5
    max_image_dimension: int = 1280
    jpeg_quality: int = 80
    monitored_processes: List[str] = Field(default_factory=list)
    ignored_title_keywords: List[str] = Field(default_factory=list)


class PermissionsConfig(BaseModel):
    """Permission configuration for assistant capabilities."""
    # File Operations
    read_files: bool = True
    write_files: bool = True
    delete_files: bool = False
    list_directories: bool = True
    search_files: bool = True
    
    # System Operations
    execute_commands: bool = True
    install_packages: bool = False
    modify_system_settings: bool = False
    access_registry: bool = False
    
    # Network Operations
    web_search: bool = True
    web_crawl: bool = True
    download_files: bool = False
    api_calls: bool = True
    
    # AI Operations
    use_vision: bool = True
    use_voice: bool = True
    multi_agent: bool = True
    plugin_execution: bool = True
    
    # Privacy
    send_screen_data: bool = True
    send_file_contents: bool = True
    send_voice_data: bool = True
    log_interactions: bool = True
    
    # Automation
    auto_fix_code: bool = True
    auto_organize_downloads: bool = True
    auto_reply_notifications: bool = False
    schedule_tasks: bool = False


class ConfirmationsConfig(BaseModel):
    """Confirmation requirements for sensitive actions."""
    write_file: bool = True
    execute_command: bool = True
    delete_file: bool = True
    install_package: bool = True
    modify_system: bool = True
    web_download: bool = True
    send_notification: bool = False
    voice_command: bool = False


class AgentConfig(BaseModel):
    """Configuration for a single agent."""
    id: str
    name: str
    role: str
    model: str
    system_prompt: str
    tools: List[str] = Field(default_factory=list)
    auto_approve: bool = False


class AgentsConfig(BaseModel):
    """Multi-agent configuration."""
    enabled: bool = True
    max_concurrent: int = 3
    default_provider: str = "groq"
    agents: List[AgentConfig] = Field(default_factory=list)


class RulesConfig(BaseModel):
    """All behavioral rules."""
    screen_monitoring: ScreenMonitoringConfig = Field(default_factory=ScreenMonitoringConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    confirmations: ConfirmationsConfig = Field(default_factory=ConfirmationsConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)


class VoiceConfig(BaseModel):
    """Voice assistant configuration."""
    enabled: bool = True
    wake_words: List[str] = Field(default_factory=lambda: ["hey assistant", "okay assistant", "assistant"])
    engine: str = "vosk"
    language: str = "en-US"
    sample_rate: int = 16000
    vad_threshold: float = 0.5
    silence_timeout: float = 2.0
    response_voice: Dict[str, Any] = Field(default_factory=lambda: {
        "engine": "pyttsx3",
        "rate": 180,
        "volume": 0.9,
        "voice_id": ""
    })
    commands: List[str] = Field(default_factory=list)


class WebSearchConfig(BaseModel):
    """Web search configuration."""
    enabled: bool = True
    default_engine: str = "brave"
    max_results: int = 10
    safe_search: bool = True
    region: str = "US"


class WebCrawlConfig(BaseModel):
    """Web crawling configuration."""
    enabled: bool = True
    max_pages: int = 5
    max_depth: int = 2
    timeout: int = 30
    respect_robots_txt: bool = True
    user_agent: str = "ActiveAssistant/2.0"


class WebConfig(BaseModel):
    """Web configuration."""
    brave_api_key: str = ""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    crawl: WebCrawlConfig = Field(default_factory=WebCrawlConfig)
    
    @field_validator('brave_api_key', mode='before')
    @classmethod
    def resolve_brave_key(cls, v: str) -> str:
        if not v:
            v = os.environ.get("BRAVE_API_KEY", "")
        return v


class MultimodalSearchConfig(BaseModel):
    """Multimodal search (CLIP-based) configuration."""
    enabled: bool = True
    clip_model: str = "openai/clip-vit-base-patch32"
    index_path: str = "~/.active_assistant/search_index"
    supported_extensions: Dict[str, List[str]] = Field(default_factory=dict)
    batch_size: int = 32
    device: str = "auto"
    similarity_threshold: float = 0.75
    max_results: int = 20


class PluginsConfig(BaseModel):
    """Plugin system configuration."""
    enabled: bool = True
    auto_load: bool = True
    plugin_dirs: List[str] = Field(default_factory=list)
    builtin_plugins: List[str] = Field(default_factory=list)
    custom_plugins: List[str] = Field(default_factory=list)
    sandbox: bool = True
    timeout: int = 30


class DownloadsOrganizerConfig(BaseModel):
    """Downloads organizer configuration."""
    enabled: bool = True
    watch_directory: str = "~/Downloads"
    check_interval_seconds: int = 10
    file_ready_stability_checks: int = 3
    file_ready_stability_interval: float = 0.5
    categories: Dict[str, List[str]] = Field(default_factory=dict)


class UIConfig(BaseModel):
    """UI configuration."""
    theme: str = "dark"
    accent_color: str = "#22c55e"
    font_family: str = "Segoe UI Variable"
    font_size: int = 13
    window: Dict[str, Any] = Field(default_factory=dict)
    system_tray: Dict[str, Any] = Field(default_factory=dict)
    dashboard: Dict[str, Any] = Field(default_factory=dict)
    chat: Dict[str, Any] = Field(default_factory=dict)


class StartupConfig(BaseModel):
    """Windows startup configuration."""
    enabled: bool = False
    run_minimized: bool = True
    delay_seconds: int = 10
    run_as_admin: bool = False
    create_shortcut: bool = True
    register_protocol: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "~/.active_assistant/logs/active_assistant.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
    console: bool = True
    json_format: bool = False


class PerformanceConfig(BaseModel):
    """Performance tuning."""
    max_worker_threads: int = 4
    max_async_tasks: int = 10
    cache_ttl_seconds: int = 300
    image_cache_size_mb: int = 100
    embedding_cache_size_mb: int = 50
    enable_gpu: bool = True
    batch_processing: bool = True


class PrivacyConfig(BaseModel):
    """Privacy and security."""
    local_only_mode: bool = False
    encrypt_config: bool = False
    encrypt_logs: bool = False
    telemetry: bool = False
    crash_reports: bool = False
    data_retention_days: int = 30
    auto_delete_temp: bool = True


class ActiveAssistantConfig(BaseModel):
    """Main configuration model."""
    api_providers: Dict[str, APIProviderConfig] = Field(default_factory=dict)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    multimodal_search: MultimodalSearchConfig = Field(default_factory=MultimodalSearchConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    downloads_organizer: DownloadsOrganizerConfig = Field(default_factory=DownloadsOrganizerConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    startup: StartupConfig = Field(default_factory=StartupConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)


# ============================================================
# Configuration Manager
# ============================================================

class ConfigManager:
    """Singleton configuration manager with hot-reload support."""
    
    _instance: Optional[ConfigManager] = None
    _lock = threading.RLock()
    
    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._config: Optional[ActiveAssistantConfig] = None
        self._config_path: Optional[Path] = None
        self._callbacks: List[callable] = []
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_watching = threading.Event()
        self._initialized = True
    
    def load(self, config_path: Optional[Union[str, Path]] = None) -> ActiveAssistantConfig:
        """Load configuration from file."""
        if config_path is None:
            # Search for config in standard locations
            search_paths = [
                Path.cwd() / "config.yaml",
                Path.cwd() / "config" / "config.yaml",
                Path.home() / ".active_assistant" / "config.yaml",
                Path(__file__).parent.parent.parent.parent / "config" / "default_config.yaml",
            ]
            for p in search_paths:
                if p.exists():
                    config_path = p
                    break
            else:
                # Use default
                config_path = Path(__file__).parent.parent.parent.parent / "config" / "default_config.yaml"
        
        self._config_path = Path(config_path).expanduser().resolve()
        
        # Load default config first
        default_path = Path(__file__).parent.parent.parent.parent / "config" / "default_config.yaml"
        with open(default_path, 'r', encoding='utf-8') as f:
            yaml_loader = ruamel.yaml.YAML()
            yaml_loader.preserve_quotes = True
            default_data = yaml_loader.load(f)
        
        # Load user config if exists
        user_data = {}
        if self._config_path != default_path and self._config_path.exists():
            with open(self._config_path, 'r', encoding='utf-8') as f:
                user_data = yaml_loader.load(f) or {}
        
        # Merge configs (user overrides default)
        merged_data = self._deep_merge(default_data, user_data)
        
        # Inject provider names for env var resolution
        for name, provider_data in merged_data.get('api_providers', {}).items():
            if isinstance(provider_data, dict):
                provider_data['provider_name'] = name
        
        # Parse with Pydantic
        self._config = ActiveAssistantConfig(**merged_data)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        logger.info(f"Configuration loaded from {self._config_path}")
        return self._config
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        if not self._config:
            return
        
        # API Keys
        env_mapping = {
            'GROQ_API_KEY': ('api_providers', 'groq', 'api_key'),
            'OPENAI_API_KEY': ('api_providers', 'openai', 'api_key'),
            'ANTHROPIC_API_KEY': ('api_providers', 'anthropic', 'api_key'),
            'BRAVE_API_KEY': ('web', 'brave_api_key'),
        }
        
        for env_var, path in env_mapping.items():
            value = os.environ.get(env_var)
            if value:
                self._set_nested(path, value)
        
        # Other overrides
        other_overrides = {
            'ACTIVE_ASSISTANT_THEME': ('ui', 'theme'),
            'ACTIVE_ASSISTANT_LOG_LEVEL': ('logging', 'level'),
            'ACTIVE_ASSISTANT_STARTUP': ('startup', 'enabled'),
        }
        
        for env_var, path in other_overrides.items():
            value = os.environ.get(env_var)
            if value:
                self._set_nested(path, value == 'true' if value.lower() in ('true', 'false') else value)
    
    def _set_nested(self, path: tuple, value: Any):
        """Set a nested config value (handles both dict and object)."""
        if not self._config:
            return
        
        obj = self._config
        for key in path[:-1]:
            if isinstance(obj, dict):
                obj = obj.get(key, {})
            else:
                obj = getattr(obj, key, None)
            if obj is None:
                return
        
        if isinstance(obj, dict):
            obj[path[-1]] = value
        else:
            setattr(obj, path[-1], value)
    
    def get(self) -> ActiveAssistantConfig:
        """Get current configuration."""
        if self._config is None:
            self.load()
        return self._config
    
    def update(self, path: str, value: Any, persist: bool = True) -> bool:
        """Update a configuration value at runtime."""
        if not self._config:
            return False
        
        keys = path.split('.')
        obj = self._config
        for key in keys[:-1]:
            if not hasattr(obj, key):
                return False
            obj = getattr(obj, key)
        
        if not hasattr(obj, keys[-1]):
            return False
        
        old_value = getattr(obj, keys[-1])
        setattr(obj, keys[-1], value)
        
        logger.info(f"Config updated: {path} = {value} (was {old_value})")
        
        if persist and self._config_path:
            self.save()
        
        self._notify_callbacks(path, value, old_value)
        return True
    
    def save(self, path: Optional[Union[str, Path]] = None) -> bool:
        """Save current configuration to file."""
        if not self._config:
            return False
        
        target_path = Path(path or self._config_path).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict, excluding defaults
        data = self._config.model_dump(exclude_defaults=False)
        
        yaml_dumper = ruamel.yaml.YAML()
        yaml_dumper.preserve_quotes = True
        yaml_dumper.default_flow_style = False
        yaml_dumper.indent(mapping=2, sequence=4, offset=2)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            yaml_dumper.dump(data, f)
        
        logger.info(f"Configuration saved to {target_path}")
        return True
    
    def register_callback(self, callback: callable):
        """Register a callback for config changes."""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: callable):
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, path: str, new_value: Any, old_value: Any):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(path, new_value, old_value)
            except Exception as e:
                logger.error(f"Config callback error: {e}")
    
    def start_watching(self, interval: float = 2.0):
        """Start watching config file for changes."""
        if self._watch_thread and self._watch_thread.is_alive():
            return
        
        self._stop_watching.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(interval,),
            daemon=True,
            name="ConfigWatcher"
        )
        self._watch_thread.start()
        logger.info("Config file watching started")
    
    def stop_watching(self):
        """Stop watching config file."""
        self._stop_watching.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=5)
        logger.info("Config file watching stopped")
    
    def _watch_loop(self, interval: float):
        """Watch loop for config file changes."""
        last_mtime = 0
        if self._config_path and self._config_path.exists():
            last_mtime = self._config_path.stat().st_mtime
        
        while not self._stop_watching.is_set():
            try:
                if self._config_path and self._config_path.exists():
                    mtime = self._config_path.stat().st_mtime
                    if mtime > last_mtime:
                        last_mtime = mtime
                        logger.info("Config file changed, reloading...")
                        self.load()
                self._stop_watching.wait(interval)
            except Exception as e:
                logger.error(f"Config watch error: {e}")
                self._stop_watching.wait(interval)


# Global instance
config = ConfigManager()


def get_config() -> ActiveAssistantConfig:
    """Get the global configuration."""
    return config.get()


def load_config(path: Optional[Union[str, Path]] = None) -> ActiveAssistantConfig:
    """Load configuration from file."""
    return config.load(path)