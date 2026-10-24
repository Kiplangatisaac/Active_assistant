"""
Plugin system for Active Assistant.
Supports dynamic loading, sandboxing, and built-in plugins.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import json
import os
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type
from contextlib import asynccontextmanager

from loguru import logger
from pydantic import BaseModel, Field

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus


# ============================================================
# Plugin Models
# ============================================================

@dataclass
class PluginInfo:
    """Plugin metadata."""
    name: str
    version: str
    description: str
    author: str = ""
    license: str = "MIT"
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = ""
    config_schema: Dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class PluginAction:
    """Plugin action definition."""
    name: str
    description: str
    parameters: Dict = field(default_factory=dict)
    returns: str = "Any"
    requires_permission: str = ""


class PluginBase(ABC):
    """Base class for all plugins."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._initialized = False
        self._actions: Dict[str, PluginAction] = {}
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Plugin metadata."""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Shutdown plugin."""
        pass
    
    @abstractmethod
    async def execute(self, action: str, **kwargs) -> Any:
        """Execute a plugin action."""
        pass
    
    def get_actions(self) -> List[PluginAction]:
        """Get available actions."""
        return list(self._actions.values())
    
    def register_action(self, action: PluginAction):
        """Register an action."""
        self._actions[action.name] = action


class PluginSandbox:
    """Sandbox for plugin execution."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._allowed_modules: Set[str] = {
            'json', 're', 'datetime', 'pathlib', 'typing',
            'dataclasses', 'collections', 'itertools', 'functools',
        }
        self._blocked_modules: Set[str] = {
            'os', 'sys', 'subprocess', 'shutil', 'importlib',
            'ctypes', 'socket', 'urllib', 'requests', 'http',
        }
    
    def is_module_allowed(self, module: str) -> bool:
        """Check if module is allowed."""
        base = module.split('.')[0]
        return base in self._allowed_modules and base not in self._blocked_modules
    
    async def execute_with_timeout(self, coro, *args, **kwargs):
        """Execute coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro(*args, **kwargs), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Plugin execution timed out after {self.timeout}s")


# ============================================================
# Built-in Plugins
# ============================================================

class DocumentHandlerPlugin(PluginBase):
    """Handle document processing (PDF, DOCX, etc.)."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="document_handler",
            version="1.0.0",
            description="Process and extract content from documents",
            author="ActiveAssistant",
            tags=["document", "pdf", "docx", "text"],
        )
    
    async def initialize(self) -> bool:
        try:
            # Check for optional dependencies
            import pdfplumber
            import docx
            import openpyxl
            self._pdfplumber = pdfplumber
            self._docx = docx
            self._openpyxl = openpyxl
            self._initialized = True
            return True
        except ImportError as e:
            logger.warning(f"Document handler missing dependencies: {e}")
            self._initialized = False
            return False
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "extract_text":
            return await self._extract_text(**kwargs)
        elif action == "extract_metadata":
            return await self._extract_metadata(**kwargs)
        elif action == "convert_to_text":
            return await self._convert_to_text(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _extract_text(self, file_path: str) -> str:
        """Extract text from document."""
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        suffix = path.suffix.lower()
        
        if suffix == '.pdf':
            return await self._extract_pdf(path)
        elif suffix in ['.docx', '.doc']:
            return await self._extract_docx(path)
        elif suffix in ['.xlsx', '.xls']:
            return await self._extract_excel(path)
        elif suffix in ['.txt', '.md', '.csv']:
            return path.read_text(encoding='utf-8', errors='ignore')
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    async def _extract_pdf(self, path: Path) -> str:
        text_parts = []
        with self._pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)
    
    async def _extract_docx(self, path: Path) -> str:
        doc = self._docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    
    async def _extract_excel(self, path: Path) -> str:
        wb = self._openpyxl.load_workbook(path, read_only=True)
        sheets_data = []
        for sheet in wb.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                rows.append([str(c) if c is not None else "" for c in row])
            sheets_data.append(f"Sheet: {sheet.title}\n" + "\n".join("\t".join(r) for r in rows))
        return "\n\n".join(sheets_data)
    
    async def _extract_metadata(self, file_path: str) -> Dict:
        path = Path(file_path).expanduser().resolve()
        stat = path.stat()
        return {
            "name": path.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": path.suffix,
        }
    
    async def _convert_to_text(self, file_path: str, output_path: str = "") -> str:
        text = await self._extract_text(file_path)
        if output_path:
            Path(output_path).expanduser().write_text(text, encoding='utf-8')
        return text


class CodeAnalyzerPlugin(PluginBase):
    """Analyze code files for issues, complexity, etc."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="code_analyzer",
            version="1.0.0",
            description="Analyze code for issues, complexity, and quality",
            author="ActiveAssistant",
            tags=["code", "analysis", "linting", "metrics"],
        )
    
    async def initialize(self) -> bool:
        try:
            import ast
            import radon.complexity as radon_cc
            import radon.metrics as radon_metrics
            self._ast = ast
            self._radon_cc = radon_cc
            self._radon_metrics = radon_metrics
            self._initialized = True
            return True
        except ImportError:
            logger.warning("Code analyzer missing radon dependency")
            self._initialized = False
            return False
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "analyze_python":
            return await self._analyze_python(**kwargs)
        elif action == "calculate_complexity":
            return await self._calculate_complexity(**kwargs)
        elif action == "find_issues":
            return await self._find_issues(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _analyze_python(self, file_path: str) -> Dict:
        path = Path(file_path).expanduser().resolve()
        code = path.read_text(encoding='utf-8')
        
        tree = self._ast.parse(code)
        
        # Count various nodes
        stats = {
            "functions": 0,
            "classes": 0,
            "imports": 0,
            "lines": len(code.splitlines()),
        }
        
        for node in self._ast.walk(tree):
            if isinstance(node, self._ast.FunctionDef):
                stats["functions"] += 1
            elif isinstance(node, self._ast.ClassDef):
                stats["classes"] += 1
            elif isinstance(node, (self._ast.Import, self._ast.ImportFrom)):
                stats["imports"] += 1
        
        return stats
    
    async def _calculate_complexity(self, file_path: str) -> Dict:
        path = Path(file_path).expanduser().resolve()
        code = path.read_text(encoding='utf-8')
        
        try:
            cc = self._radon_cc.cc_visit(code)
            return {
                "functions": [
                    {"name": f.name, "complexity": f.complexity, "lineno": f.lineno}
                    for f in cc
                ],
                "average": sum(f.complexity for f in cc) / len(cc) if cc else 0,
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _find_issues(self, file_path: str) -> List[Dict]:
        path = Path(file_path).expanduser().resolve()
        code = path.read_text(encoding='utf-8')
        
        issues = []
        lines = code.splitlines()
        
        for i, line in enumerate(lines, 1):
            # Simple checks
            if len(line) > 120:
                issues.append({"line": i, "type": "style", "message": "Line too long (>120 chars)"})
            if "TODO" in line or "FIXME" in line:
                issues.append({"line": i, "type": "note", "message": line.strip()})
            if "print(" in line and "debug" not in line.lower():
                issues.append({"line": i, "type": "warning", "message": "Print statement found"})
            if "password" in line.lower() and "=" in line:
                issues.append({"line": i, "type": "security", "message": "Possible hardcoded password"})
        
        return issues


class MediaProcessorPlugin(PluginBase):
    """Process media files (images, video, audio)."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="media_processor",
            version="1.0.0",
            description="Process and analyze media files",
            author="ActiveAssistant",
            tags=["media", "image", "video", "audio", "ffmpeg"],
        )
    
    async def initialize(self) -> bool:
        try:
            import cv2
            import PIL.Image
            self._cv2 = cv2
            self._pil = PIL.Image
            self._initialized = True
            return True
        except ImportError as e:
            logger.warning(f"Media processor missing dependencies: {e}")
            self._initialized = False
            return False
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "get_image_info":
            return await self._get_image_info(**kwargs)
        elif action == "resize_image":
            return await self._resize_image(**kwargs)
        elif action == "extract_frames":
            return await self._extract_frames(**kwargs)
        elif action == "get_video_info":
            return await self._get_video_info(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _get_image_info(self, file_path: str) -> Dict:
        path = Path(file_path).expanduser().resolve()
        img = self._pil.open(path)
        return {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "size_bytes": path.stat().st_size,
        }
    
    async def _resize_image(self, file_path: str, width: int, height: int, output_path: str = "") -> str:
        path = Path(file_path).expanduser().resolve()
        img = self._pil.open(path)
        resized = img.resize((width, height), self._pil.Resampling.LANCZOS)
        
        if not output_path:
            output_path = str(path.with_stem(f"{path.stem}_resized"))
        
        resized.save(output_path)
        return output_path
    
    async def _get_video_info(self, file_path: str) -> Dict:
        path = Path(file_path).expanduser().resolve()
        cap = self._cv2.VideoCapture(str(path))
        
        info = {
            "width": int(cap.get(self._cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(self._cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT)),
            "duration": 0,
        }
        info["duration"] = info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
        cap.release()
        return info
    
    async def _extract_frames(self, file_path: str, interval: float = 1.0, output_dir: str = "") -> List[str]:
        path = Path(file_path).expanduser().resolve()
        cap = self._cv2.VideoCapture(str(path))
        fps = cap.get(self._cv2.CAP_PROP_FPS)
        frame_interval = int(fps * interval)
        
        if not output_dir:
            output_dir = str(path.parent / f"{path.stem}_frames")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        frames = []
        frame_count = 0
        saved_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frame_path = Path(output_dir) / f"frame_{saved_count:06d}.jpg"
                self._cv2.imwrite(str(frame_path), frame)
                frames.append(str(frame_path))
                saved_count += 1
            
            frame_count += 1
        
        cap.release()
        return frames


class SystemMonitorPlugin(PluginBase):
    """Monitor system resources."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="system_monitor",
            version="1.0.0",
            description="Monitor system resources and processes",
            author="ActiveAssistant",
            tags=["system", "monitor", "performance", "resources"],
        )
    
    async def initialize(self) -> bool:
        try:
            import psutil
            self._psutil = psutil
            self._initialized = True
            return True
        except ImportError:
            self._initialized = False
            return False
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "get_processes":
            return await self._get_processes(**kwargs)
        elif action == "get_system_stats":
            return await self._get_system_stats(**kwargs)
        elif action == "get_disk_usage":
            return await self._get_disk_usage(**kwargs)
        elif action == "get_network_stats":
            return await self._get_network_stats(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _get_processes(self, limit: int = 20, sort_by: str = "cpu") -> List[Dict]:
        processes = []
        for proc in self._psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                info = proc.info
                if info['cpu_percent'] > 0 or info['memory_percent'] > 0:
                    processes.append(info)
            except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
                pass
        
        if sort_by == "cpu":
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
        
        return processes[:limit]
    
    async def _get_system_stats(self) -> Dict:
        return {
            "cpu_percent": self._psutil.cpu_percent(interval=1),
            "cpu_count": self._psutil.cpu_count(),
            "memory": dict(self._psutil.virtual_memory()._asdict()),
            "swap": dict(self._psutil.swap_memory()._asdict()),
            "disk": {p.mountpoint: dict(self._psutil.disk_usage(p.mountpoint)._asdict()) 
                     for p in self._psutil.disk_partitions() if p.fstype},
            "boot_time": datetime.fromtimestamp(self._psutil.boot_time()).isoformat(),
        }
    
    async def _get_disk_usage(self, path: str = "/") -> Dict:
        usage = self._psutil.disk_usage(path)
        return dict(usage._asdict())
    
    async def _get_network_stats(self) -> Dict:
        io = self._psutil.net_io_counters()
        return dict(io._asdict())


class NetworkToolsPlugin(PluginBase):
    """Network utilities."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="network_tools",
            version="1.0.0",
            description="Network utilities and diagnostics",
            author="ActiveAssistant",
            tags=["network", "dns", "ping", "port", "http"],
        )
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "ping":
            return await self._ping(**kwargs)
        elif action == "dns_lookup":
            return await self._dns_lookup(**kwargs)
        elif action == "port_scan":
            return await self._port_scan(**kwargs)
        elif action == "http_request":
            return await self._http_request(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _ping(self, host: str, count: int = 4) -> Dict:
        import subprocess
        import platform
        
        param = "-n" if platform.system().lower() == "windows" else "-c"
        cmd = ["ping", param, str(count), host]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "host": host,
                "success": result.returncode == 0,
                "output": result.stdout,
            }
        except Exception as e:
            return {"host": host, "success": False, "error": str(e)}
    
    async def _dns_lookup(self, domain: str, record_type: str = "A") -> Dict:
        import socket
        try:
            if record_type == "A":
                ips = socket.gethostbyname_ex(domain)[2]
                return {"domain": domain, "type": "A", "records": ips}
            else:
                # For other types, would need dnspython
                return {"domain": domain, "type": record_type, "error": "Requires dnspython"}
        except Exception as e:
            return {"domain": domain, "error": str(e)}
    
    async def _port_scan(self, host: str, ports: List[int] = None, timeout: float = 1.0) -> Dict:
        import socket
        
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 3306, 5432, 8080]
        
        open_ports = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    open_ports.append(port)
            except Exception:
                pass
        
        return {"host": host, "open_ports": open_ports, "scanned": len(ports)}
    
    async def _http_request(self, url: str, method: str = "GET", **kwargs) -> Dict:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as resp:
                    text = await resp.text()
                    return {
                        "url": url,
                        "status": resp.status,
                        "headers": dict(resp.headers),
                        "content": text[:5000],
                    }
        except Exception as e:
            return {"url": url, "error": str(e)}


class ArchiveManagerPlugin(PluginBase):
    """Handle archive files."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="archive_manager",
            version="1.0.0",
            description="Create and extract archives",
            author="ActiveAssistant",
            tags=["archive", "zip", "tar", "compression"],
        )
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "extract":
            return await self._extract(**kwargs)
        elif action == "create":
            return await self._create(**kwargs)
        elif action == "list":
            return await self._list(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _extract(self, archive_path: str, output_dir: str = "") -> str:
        import shutil
        path = Path(archive_path).expanduser().resolve()
        
        if not output_dir:
            output_dir = str(path.parent / path.stem)
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(path), output_dir)
        return output_dir
    
    async def _create(self, source_dir: str, archive_path: str, format: str = "zip") -> str:
        import shutil
        source = Path(source_dir).expanduser().resolve()
        output = Path(archive_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.make_archive(str(output.with_suffix('')), format, source)
        return str(output)
    
    async def _list(self, archive_path: str) -> List[str]:
        import zipfile
        import tarfile
        
        path = Path(archive_path).expanduser().resolve()
        files = []
        
        if path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path, 'r') as zf:
                files = zf.namelist()
        elif path.suffix.lower() in ['.tar', '.gz', '.tgz']:
            with tarfile.open(path, 'r:*') as tf:
                files = tf.getnames()
        
        return files


class DatabaseToolsPlugin(PluginBase):
    """Database utilities."""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="database_tools",
            version="1.0.0",
            description="Database query and management tools",
            author="ActiveAssistant",
            tags=["database", "sql", "sqlite", "postgres"],
        )
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def shutdown(self):
        pass
    
    async def execute(self, action: str, **kwargs) -> Any:
        if action == "query_sqlite":
            return await self._query_sqlite(**kwargs)
        elif action == "list_tables":
            return await self._list_tables(**kwargs)
        elif action == "describe_table":
            return await self._describe_table(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _query_sqlite(self, db_path: str, query: str, params: tuple = ()) -> List[Dict]:
        import sqlite3
        path = Path(db_path).expanduser().resolve()
        
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    async def _list_tables(self, db_path: str) -> List[str]:
        return await self._query_sqlite(db_path, "SELECT name FROM sqlite_master WHERE type='table'")
    
    async def _describe_table(self, db_path: str, table: str) -> List[Dict]:
        return await self._query_sqlite(db_path, f"PRAGMA table_info({table})")


# ============================================================
# Plugin Manager
# ============================================================

class PluginManager:
    """Manages plugin discovery, loading, and execution."""
    
    def __init__(self):
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._sandbox = PluginSandbox()
        self._builtin_plugins: Dict[str, Type[PluginBase]] = {
            "document_handler": DocumentHandlerPlugin,
            "code_analyzer": CodeAnalyzerPlugin,
            "media_processor": MediaProcessorPlugin,
            "system_monitor": SystemMonitorPlugin,
            "network_tools": NetworkToolsPlugin,
            "archive_manager": ArchiveManagerPlugin,
            "database_tools": DatabaseToolsPlugin,
        }
        self._plugin_configs: Dict[str, Dict] = {}
        self._load_order: List[str] = []
    
    async def initialize(self, config_path: str | None = None):
        """Initialize plugin system."""
        cfg = get_config()
        
        if not cfg.plugins.enabled:
            logger.info("Plugins disabled in configuration")
            return
        
        # Load built-in plugins
        for name in cfg.plugins.builtin_plugins:
            if name in self._builtin_plugins:
                await self._load_builtin(name)
        
        # Load custom plugins from directories
        for plugin_dir in cfg.plugins.plugin_dirs:
            await self._discover_plugins(plugin_dir)
        
        logger.info(f"Plugin manager initialized with {len(self._plugins)} plugins")
    
    async def _load_builtin(self, name: str):
        """Load a built-in plugin."""
        try:
            plugin_class = self._builtin_plugins[name]
            plugin = plugin_class(self._plugin_configs.get(name, {}))
            
            if await plugin.initialize():
                self._plugins[name] = plugin
                self._plugin_info[name] = plugin.info
                self._load_order.append(name)
                logger.info(f"Loaded built-in plugin: {name}")
            else:
                logger.warning(f"Built-in plugin failed to initialize: {name}")
        except Exception as e:
            logger.error(f"Failed to load built-in plugin {name}: {e}")
    
    async def _discover_plugins(self, directory: str):
        """Discover and load plugins from directory."""
        plugin_dir = Path(directory).expanduser()
        if not plugin_dir.exists():
            return
        
        for plugin_path in plugin_dir.iterdir():
            if plugin_path.is_dir() and (plugin_path / "__init__.py").exists():
                await self._load_plugin_from_path(plugin_path)
            elif plugin_path.suffix == '.py' and plugin_path.name != '__init__.py':
                await self._load_plugin_from_path(plugin_path)
    
    async def _load_plugin_from_path(self, path: Path):
        """Load a plugin from a file or directory."""
        name = path.stem if path.suffix == '.py' else path.name
        
        try:
            # Load module
            spec = importlib.util.spec_from_file_location(name, path / "__init__.py" if path.is_dir() else path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            
            # Find plugin class
            plugin_class = None
            for obj_name in dir(module):
                obj = getattr(module, obj_name)
                if (inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                logger.warning(f"No PluginBase subclass found in {path}")
                return
            
            plugin = plugin_class(self._plugin_configs.get(name, {}))
            if await plugin.initialize():
                self._plugins[name] = plugin
                self._plugin_info[name] = plugin.info
                self._load_order.append(name)
                logger.info(f"Loaded plugin: {name}")
            else:
                logger.warning(f"Plugin failed to initialize: {name}")
                
        except Exception as e:
            logger.error(f"Failed to load plugin from {path}: {e}")
            logger.debug(traceback.format_exc())
    
    async def execute(self, plugin_name: str, action: str, **kwargs) -> Any:
        """Execute a plugin action."""
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin not found: {plugin_name}")
        
        # Check sandbox
        if get_config().plugins.sandbox:
            return await self._sandbox.execute_with_timeout(plugin.execute, action, **kwargs)
        else:
            return await plugin.execute(action, **kwargs)
    
    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins."""
        return list(self._plugin_info.values())
    
    def get_actions(self, plugin_name: str) -> List[PluginAction]:
        """Get actions for a plugin."""
        plugin = self._plugins.get(plugin_name)
        if plugin:
            return plugin.get_actions()
        return []
    
    async def shutdown(self):
        """Shutdown all plugins."""
        for name in reversed(self._load_order):
            plugin = self._plugins.get(name)
            if plugin:
                try:
                    await plugin.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down plugin {name}: {e}")
        self._plugins.clear()
        self._plugin_info.clear()


# Global plugin manager
plugin_manager = PluginManager()


async def initialize_plugins(config_path: str | None = None):
    """Initialize plugin system."""
    await plugin_manager.initialize(config_path)


async def execute_plugin(plugin_name: str, action: str, **kwargs) -> Any:
    """Execute a plugin action."""
    return await plugin_manager.execute(plugin_name, action, **kwargs)


def get_plugin(name: str) -> Optional[PluginBase]:
    """Get a plugin by name."""
    return plugin_manager.get_plugin(name)


def list_plugins() -> List[PluginInfo]:
    """List all plugins."""
    return plugin_manager.list_plugins()