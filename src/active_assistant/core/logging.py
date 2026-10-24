"""
Logging setup for Active Assistant.
Uses loguru for structured logging with rotation.
"""
from __future__ import annotations

import sys
from pathlib import Path
from loguru import logger
from active_assistant.core.config import get_config


def setup_logging(config_path: str | Path | None = None) -> None:
    """Configure loguru logging based on config."""
    # Remove default handler
    logger.remove()
    
    # Get config
    try:
        from active_assistant.core.config import load_config
        cfg = load_config(config_path)
        log_cfg = cfg.logging
    except Exception:
        # Fallback defaults
        log_cfg = type('LogConfig', (), {
            'level': 'INFO',
            'file': '~/.active_assistant/logs/active_assistant.log',
            'max_size_mb': 10,
            'backup_count': 5,
            'format': '{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}',
            'console': True,
            'json_format': False,
        })()
    
    # Console handler
    if log_cfg.console:
        logger.add(
            sys.stdout,
            level=log_cfg.level,
            format=log_cfg.format if not log_cfg.json_format else None,
            serialize=log_cfg.json_format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    
    # File handler with rotation
    log_file = Path(log_cfg.file).expanduser()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # loguru uses "X days" for retention, not "X files"
    retention = f"{log_cfg.backup_count} days"
    
    logger.add(
        str(log_file),
        level=log_cfg.level,
        format=log_cfg.format if not log_cfg.json_format else None,
        serialize=log_cfg.json_format,
        rotation=f"{log_cfg.max_size_mb} MB",
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Thread-safe
    )
    
    # Also log to error file for errors only
    error_file = log_file.with_name(log_file.stem + "_errors" + log_file.suffix)
    logger.add(
        str(error_file),
        level="ERROR",
        format=log_cfg.format,
        rotation=f"{log_cfg.max_size_mb} MB",
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )
    
    logger.info("Logging initialized")


def get_logger(name: str):
    """Get a logger instance for a module."""
    return logger.bind(name=name)


# Initialize on import
setup_logging()