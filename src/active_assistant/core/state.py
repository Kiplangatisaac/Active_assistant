"""
Global state management and event system for Active Assistant.
Thread-safe state with observers for reactive UI updates.
"""
from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic
from contextlib import contextmanager

from loguru import logger


# ============================================================
# Event System
# ============================================================

T = TypeVar('T')


@dataclass
class Event(Generic[T]):
    """Generic event with typed payload."""
    type: str
    payload: T
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class EventBus:
    """Thread-safe event bus for decoupled communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.RLock()
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> Callable[[], None]:
        """Subscribe to an event type. Returns unsubscribe function."""
        with self._lock:
            self._subscribers[event_type].append(callback)
        
        def unsubscribe():
            with self._lock:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)
        
        return unsubscribe
    
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            subscribers = self._subscribers[event.type].copy()
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
        
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error for {event.type}: {e}")
    
    def publish_async(self, event: Event) -> None:
        """Publish event asynchronously."""
        threading.Thread(target=self.publish, args=(event,), daemon=True).start()
    
    def get_history(self, event_type: str | None = None, limit: int = 100) -> List[Event]:
        """Get recent event history."""
        with self._lock:
            if event_type:
                return [e for e in self._event_history if e.type == event_type][-limit:]
            return self._event_history[-limit:]


# Global event bus
event_bus = EventBus()


# ============================================================
# Application State
# ============================================================

class AppState(Enum):
    """Application lifecycle states."""
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MonitoredWindow:
    """Information about currently monitored window."""
    hwnd: int = 0
    title: str = ""
    process_name: str = ""
    process_id: int = 0
    bounds: tuple = (0, 0, 0, 0)
    last_capture: datetime | None = None
    last_hash: int | None = None
    is_monitored: bool = False


@dataclass
class AssistantMetrics:
    """Runtime metrics for dashboard."""
    uptime_seconds: float = 0
    screens_captured: int = 0
    issues_detected: int = 0
    tools_executed: int = 0
    api_calls: int = 0
    api_errors: int = 0
    voice_commands: int = 0
    files_organized: int = 0
    last_activity: datetime | None = None
    memory_mb: float = 0
    cpu_percent: float = 0


class StateManager:
    """Centralized application state management."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._state = AppState.STARTING
        self._monitored_window = MonitoredWindow()
        self._metrics = AssistantMetrics()
        self._start_time = time.time()
        self._paused = False
        self._shutdown_requested = False
        self._active_agents: Set[str] = set()
        self._pending_confirmations: Dict[str, Dict] = {}
        self._notification_queue: List[Dict] = []
    
    @property
    def state(self) -> AppState:
        with self._lock:
            return self._state
    
    @state.setter
    def state(self, value: AppState):
        with self._lock:
            old = self._state
            self._state = value
        if old != value:
            event_bus.publish(Event("state_changed", {"old": old.value, "new": value.value}))
            logger.info(f"State changed: {old.value} -> {value.value}")
    
    @property
    def is_running(self) -> bool:
        return self.state == AppState.RUNNING
    
    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused or self.state == AppState.PAUSED
    
    def set_paused(self, paused: bool):
        with self._lock:
            self._paused = paused
        self.state = AppState.PAUSED if paused else AppState.RUNNING
    
    @property
    def monitored_window(self) -> MonitoredWindow:
        with self._lock:
            return self._monitored_window
    
    def update_window(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._monitored_window, k):
                    setattr(self._monitored_window, k, v)
            self._monitored_window.last_capture = datetime.now()
        event_bus.publish(Event("window_changed", self._monitored_window.__dict__))
    
    @property
    def metrics(self) -> AssistantMetrics:
        with self._lock:
            self._metrics.uptime_seconds = time.time() - self._start_time
            return self._metrics
    
    def increment_metric(self, metric: str, value: int = 1):
        with self._lock:
            if hasattr(self._metrics, metric):
                current = getattr(self._metrics, metric, 0)
                setattr(self._metrics, metric, current + value)
                self._metrics.last_activity = datetime.now()
    
    def request_shutdown(self):
        with self._lock:
            self._shutdown_requested = True
        self.state = AppState.STOPPING
    
    @property
    def shutdown_requested(self) -> bool:
        with self._lock:
            return self._shutdown_requested
    
    def add_active_agent(self, agent_id: str):
        with self._lock:
            self._active_agents.add(agent_id)
        event_bus.publish(Event("agent_started", {"agent_id": agent_id}))
    
    def remove_active_agent(self, agent_id: str):
        with self._lock:
            self._active_agents.discard(agent_id)
        event_bus.publish(Event("agent_stopped", {"agent_id": agent_id}))
    
    @property
    def active_agents(self) -> Set[str]:
        with self._lock:
            return self._active_agents.copy()
    
    def add_confirmation(self, confirmation_id: str, data: Dict):
        with self._lock:
            self._pending_confirmations[confirmation_id] = data
        event_bus.publish(Event("confirmation_requested", {"id": confirmation_id, **data}))
    
    def resolve_confirmation(self, confirmation_id: str, approved: bool):
        with self._lock:
            if confirmation_id in self._pending_confirmations:
                data = self._pending_confirmations.pop(confirmation_id)
                data['approved'] = approved
                data['resolved_at'] = datetime.now()
                event_bus.publish(Event("confirmation_resolved", data))
                return data
        return None
    
    def get_pending_confirmations(self) -> List[Dict]:
        with self._lock:
            return list(self._pending_confirmations.values())
    
    def add_notification(self, title: str, message: str, level: str = "info", **kwargs):
        """Add notification to queue."""
        notification = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.now(),
            **kwargs
        }
        with self._lock:
            self._notification_queue.append(notification)
        event_bus.publish(Event("notification", notification))
    
    def get_notifications(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return self._notification_queue[-limit:]
    
    def clear_notifications(self):
        with self._lock:
            self._notification_queue.clear()


# Global state manager
state = StateManager()


# ============================================================
# Context Managers
# ============================================================

@contextmanager
def agent_context(agent_id: str):
    """Context manager for agent lifecycle."""
    state.add_active_agent(agent_id)
    try:
        yield
    finally:
        state.remove_active_agent(agent_id)


@contextmanager
def error_context(operation: str):
    """Context manager for error tracking."""
    try:
        yield
    except Exception as e:
        state.increment_metric("api_errors")
        logger.error(f"Error in {operation}: {e}")
        raise


# ============================================================
# Settings Persistence
# ============================================================

class SettingsStore:
    """Persistent settings storage using JSON."""
    
    def __init__(self, path: Path | str = "~/.active_assistant/settings.json"):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict = {}
        self._lock = threading.RLock()
        self.load()
    
    def load(self) -> Dict:
        with self._lock:
            if self.path.exists():
                try:
                    import json
                    with open(self.path, 'r') as f:
                        self._data = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load settings: {e}")
                    self._data = {}
            return self._data
    
    def save(self) -> bool:
        with self._lock:
            try:
                import json
                with open(self.path, 'w') as f:
                    json.dump(self._data, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Failed to save settings: {e}")
                return False
    
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            keys = key.split('.')
            data = self._data
            for k in keys:
                if isinstance(data, dict) and k in data:
                    data = data[k]
                else:
                    return default
            return data
    
    def set(self, key: str, value: Any) -> bool:
        with self._lock:
            keys = key.split('.')
            data = self._data
            for k in keys[:-1]:
                if k not in data:
                    data[k] = {}
                data = data[k]
            data[keys[-1]] = value
            return self.save()
    
    def delete(self, key: str) -> bool:
        with self._lock:
            keys = key.split('.')
            data = self._data
            for k in keys[:-1]:
                if isinstance(data, dict) and k in data:
                    data = data[k]
                else:
                    return False
            if keys[-1] in data:
                del data[keys[-1]]
                return self.save()
            return False


settings = SettingsStore()