"""
Tool system for Active Assistant.
Provides a unified interface for all assistant capabilities with confirmations.
"""
from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import shlex
import shutil
import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
from contextlib import asynccontextmanager

import aiofiles
from loguru import logger
from pydantic import BaseModel, Field

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus


# ============================================================
# Tool Models
# ============================================================

class ToolCategory(Enum):
    FILE = "file"
    SYSTEM = "system"
    WEB = "web"
    AI = "ai"
    MEDIA = "media"
    PLUGIN = "plugin"
    CUSTOM = "custom"


class ConfirmationLevel(Enum):
    NONE = "none"           # No confirmation needed
    NOTIFY = "notify"       # Show notification but proceed
    CONFIRM = "confirm"     # Require user confirmation
    ADMIN = "admin"         # Require admin confirmation


@dataclass
class ToolParameter:
    """Tool parameter definition."""
    name: str
    type: str  # string, integer, boolean, array, object
    description: str
    required: bool = True
    default: Any = None
    enum: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Tool execution result."""
    success: bool
    output: Any = None
    error: str = ""
    metadata: Dict = field(default_factory=dict)
    execution_time: float = 0
    tool_name: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class Tool(BaseModel):
    """Tool definition."""
    name: str
    description: str
    category: ToolCategory = ToolCategory.CUSTOM
    parameters: List[ToolParameter] = Field(default_factory=list)
    returns: str = "Any"
    confirmation: ConfirmationLevel = ConfirmationLevel.NONE
    requires_permission: str = ""
    examples: List[Dict] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    author: str = "ActiveAssistant"
    
    def to_openai_format(self) -> Dict:
        """Convert to OpenAI function calling format."""
        props = {}
        required = []
        for param in self.parameters:
            props[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                props[param.name]["enum"] = param.enum
            if param.default is not None:
                props[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }


# ============================================================
# Tool Executor Base
# ============================================================

class ToolExecutor(ABC):
    """Base class for tool executors."""
    
    def __init__(self, tool: Tool):
        self.tool = tool
        self._confirmation_callback: Optional[Callable] = None
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool."""
        pass
    
    def set_confirmation_callback(self, callback: Callable):
        """Set callback for confirmation dialogs."""
        self._confirmation_callback = callback
    
    async def _request_confirmation(self, message: str, warning: bool = False) -> bool:
        """Request user confirmation."""
        if self.tool.confirmation == ConfirmationLevel.NONE:
            return True
        
        if self.tool.confirmation == ConfirmationLevel.NOTIFY:
            state.add_notification(self.tool.name, message, "info")
            return True
        
        # For CONFIRM and ADMIN, use the callback or event system
        confirmation_id = str(uuid.uuid4())[:8]
        
        if self._confirmation_callback:
            return await self._confirmation_callback(
                title=f"Confirm: {self.tool.name}",
                message=message,
                warning=warning or self.tool.confirmation == ConfirmationLevel.ADMIN
            )
        
        # Use event-based confirmation
        future = asyncio.Future()
        
        def handle_resolution(event: Event):
            if event.payload.get("id") == confirmation_id:
                future.set_result(event.payload.get("approved", False))
        
        unsubscribe = event_bus.subscribe("confirmation_resolved", handle_resolution)
        
        state.add_confirmation(confirmation_id, {
            "tool": self.tool.name,
            "message": message,
            "warning": warning or self.tool.confirmation == ConfirmationLevel.ADMIN,
        })
        
        try:
            result = await asyncio.wait_for(future, timeout=60.0)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Confirmation timeout for {self.tool.name}")
            return False
        finally:
            unsubscribe()


# ============================================================
# File Tools
# ============================================================

class ListDirectoryTool(ToolExecutor):
    """List directory contents."""
    
    def __init__(self):
        tool = Tool(
            name="list_directory",
            description="List files and folders in a directory",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter("path", "string", "Directory path to list", default="."),
                ToolParameter("show_hidden", "boolean", "Include hidden files", default=False),
                ToolParameter("max_items", "integer", "Maximum items to return", default=100),
            ],
            returns="string",
        )
        super().__init__(tool)
    
    async def execute(self, path: str = ".", show_hidden: bool = False, max_items: int = 100) -> ToolResult:
        start = datetime.now()
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(False, error=f"Path '{target}' does not exist", tool_name=self.tool.name)
            
            items = []
            for item in target.iterdir():
                if not show_hidden and item.name.startswith('.'):
                    continue
                prefix = "[DIR] " if item.is_dir() else "[FILE]"
                size = item.stat().st_size if item.is_file() else 0
                items.append(f"{prefix} {item.name} ({size} bytes)")
                if len(items) >= max_items:
                    break
            
            output = "\n".join(items) if items else "Directory is empty"
            return ToolResult(True, output=output, tool_name=self.tool.name, 
                            execution_time=(datetime.now() - start).total_seconds())
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class ReadFileTool(ToolExecutor):
    """Read file contents."""
    
    def __init__(self):
        tool = Tool(
            name="read_file",
            description="Read contents of a file",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter("path", "string", "Path of the file to read"),
                ToolParameter("max_chars", "integer", "Maximum characters to read", default=4000),
                ToolParameter("encoding", "string", "File encoding", default="utf-8"),
            ],
            returns="string",
        )
        super().__init__(tool)
    
    async def execute(self, path: str, max_chars: int = 4000, encoding: str = "utf-8") -> ToolResult:
        start = datetime.now()
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists() or not target.is_file():
                return ToolResult(False, error=f"File '{target}' not found", tool_name=self.tool.name)
            
            async with aiofiles.open(target, 'r', encoding=encoding, errors='ignore') as f:
                content = await f.read(max_chars)
            
            return ToolResult(True, output=content, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"size": target.stat().st_size, "truncated": len(content) >= max_chars})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class WriteFileTool(ToolExecutor):
    """Write file contents with backup."""
    
    def __init__(self):
        tool = Tool(
            name="write_file",
            description="Write content to a file (creates backup if exists)",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter("path", "string", "Path of the file to write"),
                ToolParameter("content", "string", "Content to write"),
                ToolParameter("create_dirs", "boolean", "Create parent directories", default=True),
                ToolParameter("backup", "boolean", "Create backup of existing file", default=True),
            ],
            returns="string",
            confirmation=ConfirmationLevel.CONFIRM,
            requires_permission="write_files",
        )
        super().__init__(tool)
    
    async def execute(self, path: str, content: str, create_dirs: bool = True, backup: bool = True) -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.write_files:
                return ToolResult(False, error="Write permission denied by configuration", tool_name=self.tool.name)
            
            target = Path(path).expanduser().resolve()
            preview = content[:250] + ("..." if len(content) > 250 else "")
            
            confirmed = await self._request_confirmation(
                f"Write to file: {target}\n\nPreview:\n{preview}",
                warning=True
            )
            
            if not confirmed:
                return ToolResult(False, error="User denied write permission", tool_name=self.tool.name)
            
            if create_dirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            
            backup_path = None
            if backup and target.exists():
                backup_path = target.with_suffix(f"{target.suffix}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                shutil.copy2(target, backup_path)
            
            async with aiofiles.open(target, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            output = f"Successfully wrote {len(content)} characters to {target}"
            if backup_path:
                output += f"\nBackup created: {backup_path}"
            
            state.increment_metric("tools_executed")
            return ToolResult(True, output=output, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"bytes": len(content), "backup": str(backup_path) if backup_path else None})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class SearchFilesTool(ToolExecutor):
    """Search for files by pattern."""
    
    def __init__(self):
        tool = Tool(
            name="search_files",
            description="Search for files matching a pattern",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter("pattern", "string", "Glob pattern to match (e.g., '*.py')"),
                ToolParameter("root_path", "string", "Root directory to search", default="."),
                ToolParameter("max_results", "integer", "Maximum results", default=30),
                ToolParameter("recursive", "boolean", "Search recursively", default=True),
            ],
            returns="string",
        )
        super().__init__(tool)
    
    async def execute(self, pattern: str, root_path: str = ".", max_results: int = 30, recursive: bool = True) -> ToolResult:
        start = datetime.now()
        try:
            target = Path(root_path).expanduser().resolve()
            if not target.exists():
                return ToolResult(False, error=f"Path '{target}' does not exist", tool_name=self.tool.name)
            
            if recursive:
                matches = list(target.rglob(pattern))[:max_results]
            else:
                matches = list(target.glob(pattern))[:max_results]
            
            output = "\n".join(str(p) for p in matches) if matches else "No matches found."
            return ToolResult(True, output=output, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"count": len(matches)})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class DeleteFileTool(ToolExecutor):
    """Delete a file or directory."""
    
    def __init__(self):
        tool = Tool(
            name="delete_file",
            description="Delete a file or directory",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter("path", "string", "Path to delete"),
                ToolParameter("recursive", "boolean", "Delete directories recursively", default=False),
                ToolParameter("trash", "boolean", "Move to trash instead of permanent delete", default=True),
            ],
            returns="string",
            confirmation=ConfirmationLevel.ADMIN,
            requires_permission="delete_files",
        )
        super().__init__(tool)
    
    async def execute(self, path: str, recursive: bool = False, trash: bool = True) -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.delete_files:
                return ToolResult(False, error="Delete permission denied by configuration", tool_name=self.tool.name)
            
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(False, error=f"Path '{target}' does not exist", tool_name=self.tool.name)
            
            confirmed = await self._request_confirmation(
                f"Delete {'directory' if target.is_dir() else 'file'}: {target}\n"
                f"{'Recursive' if recursive else 'Single item'}",
                warning=True
            )
            
            if not confirmed:
                return ToolResult(False, error="User denied delete permission", tool_name=self.tool.name)
            
            if target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                else:
                    target.rmdir()
            else:
                if trash:
                    # Move to trash (platform specific)
                    import send2trash
                    send2trash.send2trash(str(target))
                else:
                    target.unlink()
            
            return ToolResult(True, output=f"Deleted: {target}", tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# System Tools
# ============================================================

class ExecuteCommandTool(ToolExecutor):
    """Execute shell commands."""
    
    def __init__(self):
        tool = Tool(
            name="execute_command",
            description="Execute a shell command",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter("command", "string", "Command to execute"),
                ToolParameter("cwd", "string", "Working directory", default="."),
                ToolParameter("timeout", "integer", "Timeout in seconds", default=30),
                ToolParameter("shell", "boolean", "Use shell", default=False),
            ],
            returns="string",
            confirmation=ConfirmationLevel.CONFIRM,
            requires_permission="execute_commands",
        )
        super().__init__(tool)
    
    async def execute(self, command: str, cwd: str = ".", timeout: int = 30, shell: bool = False) -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.execute_commands:
                return ToolResult(False, error="Execute permission denied by configuration", tool_name=self.tool.name)
            
            work_dir = Path(cwd).expanduser().resolve()
            
            confirmed = await self._request_confirmation(
                f"Execute command: {command}\nWorking directory: {work_dir}",
                warning=True
            )
            
            if not confirmed:
                return ToolResult(False, error="User denied execution permission", tool_name=self.tool.name)
            
            if shell:
                args = command
            else:
                args = shlex.split(command)
            
            if shell:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=str(work_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *args,
                    cwd=str(work_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(False, error=f"Command timed out after {timeout} seconds", tool_name=self.tool.name)
            
            output = stdout.decode('utf-8', errors='ignore')
            if stderr:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                output += f"\nSTDERR:\n{stderr_text}"
            
            state.increment_metric("tools_executed")
            return ToolResult(True, output=output.strip() or "Command completed with no output", 
                            tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"returncode": process.returncode})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class SystemInfoTool(ToolExecutor):
    """Get system information."""
    
    def __init__(self):
        tool = Tool(
            name="system_info",
            description="Get system information",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter("detail", "string", "Detail level: basic, hardware, network, all", default="basic"),
            ],
            returns="object",
        )
        super().__init__(tool)
    
    async def execute(self, detail: str = "basic") -> ToolResult:
        start = datetime.now()
        try:
            import psutil
            import platform
            
            info = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
            }
            
            if detail in ("hardware", "all"):
                info.update({
                    "cpu_count": psutil.cpu_count(),
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                    "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                    "disk_usage": {p.mountpoint: round(psutil.disk_usage(p.mountpoint).free / (1024**3), 2) 
                                  for p in psutil.disk_partitions() if p.fstype},
                })
            
            if detail in ("network", "all"):
                info["network"] = {}
                for name, addrs in psutil.net_if_addrs().items():
                    info["network"][name] = [{"family": str(a.family), "address": a.address} for a in addrs]
            
            import json
            output = json.dumps(info, indent=2)
            return ToolResult(True, output=output, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# Web Tools
# ============================================================

class WebSearchTool(ToolExecutor):
    """Search the web using Brave API."""
    
    def __init__(self):
        tool = Tool(
            name="web_search",
            description="Search the web using Brave Search API",
            category=ToolCategory.WEB,
            parameters=[
                ToolParameter("query", "string", "Search query"),
                ToolParameter("max_results", "integer", "Maximum results", default=10),
                ToolParameter("safe_search", "boolean", "Enable safe search", default=True),
                ToolParameter("region", "string", "Search region", default="US"),
            ],
            returns="string",
            requires_permission="web_search",
        )
        super().__init__(tool)
    
    async def execute(self, query: str, max_results: int = 10, safe_search: bool = True, region: str = "US") -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.web_search:
                return ToolResult(False, error="Web search permission denied", tool_name=self.tool.name)
            
            if not cfg.web.brave_api_key:
                return ToolResult(False, error="Brave API key not configured", tool_name=self.tool.name)
            
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": cfg.web.brave_api_key,
            }
            
            params = {
                "q": query,
                "count": min(max_results, 20),
                "safesearch": "moderate" if safe_search else "off",
                "search_lang": "en",
                "country": region.lower(),
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers=headers,
                    params=params,
                ) as resp:
                    if resp.status != 200:
                        return ToolResult(False, error=f"Search API error: {resp.status}", tool_name=self.tool.name)
                    data = await resp.json()
            
            results = data.get("web", {}).get("results", [])
            output = ""
            for i, r in enumerate(results[:max_results], 1):
                output += f"{i}. {r.get('title', '')}\n   {r.get('url', '')}\n   {r.get('description', '')}\n\n"
            
            state.increment_metric("api_calls")
            return ToolResult(True, output=output.strip() or "No results found", tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"results": len(results)})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class WebCrawlTool(ToolExecutor):
    """Crawl web pages."""
    
    def __init__(self):
        tool = Tool(
            name="web_crawl",
            description="Crawl and extract content from web pages",
            category=ToolCategory.WEB,
            parameters=[
                ToolParameter("urls", "array", "Array of URLs to crawl"),
                ToolParameter("max_depth", "integer", "Maximum crawl depth", default=2),
                ToolParameter("max_pages", "integer", "Maximum pages to crawl", default=5),
            ],
            returns="string",
            requires_permission="web_crawl",
        )
        super().__init__(tool)
    
    async def execute(self, urls: List[str], max_depth: int = 2, max_pages: int = 5) -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.web_crawl:
                return ToolResult(False, error="Web crawl permission denied", tool_name=self.tool.name)
            
            from bs4 import BeautifulSoup
            import aiohttp
            
            visited = set()
            results = []
            
            async def crawl(url: str, depth: int):
                if depth > max_depth or len(visited) >= max_pages or url in visited:
                    return
                
                visited.add(url)
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=30) as resp:
                            if resp.status != 200:
                                return
                            html = await resp.text()
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract text content
                    for script in soup(["script", "style"]):
                        script.decompose()
                    text = soup.get_text(separator='\n', strip=True)
                    
                    results.append({
                        "url": url,
                        "title": soup.title.string if soup.title else "",
                        "content": text[:5000],
                    })
                    
                    # Find links for next depth
                    if depth < max_depth:
                        links = [a.get('href') for a in soup.find_all('a', href=True)]
                        for link in links[:5]:  # Limit links per page
                            if link.startswith('http'):
                                await crawl(link, depth + 1)
                                
                except Exception as e:
                    logger.warning(f"Crawl error for {url}: {e}")
            
            for url in urls:
                await crawl(url, 0)
            
            output = ""
            for r in results:
                output += f"URL: {r['url']}\nTitle: {r['title']}\nContent:\n{r['content']}\n\n{'='*50}\n\n"
            
            state.increment_metric("api_calls")
            return ToolResult(True, output=output.strip() or "No content extracted", tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"pages": len(results)})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# Media Search Tools (CLIP-based)
# ============================================================

class MediaSearchTool(ToolExecutor):
    """Search images/videos by content using CLIP."""
    
    def __init__(self):
        tool = Tool(
            name="search_media",
            description="Search for images/videos by visual/content description",
            category=ToolCategory.MEDIA,
            parameters=[
                ToolParameter("query", "string", "Description of what to search for"),
                ToolParameter("media_type", "string", "Type: images, videos, audio, all", default="all"),
                ToolParameter("directory", "string", "Directory to search", default="~/Pictures"),
                ToolParameter("max_results", "integer", "Maximum results", default=20),
                ToolParameter("similarity_threshold", "number", "Similarity threshold 0-1", default=0.75),
            ],
            returns="string",
        )
        super().__init__(tool)
    
    async def execute(
        self, 
        query: str, 
        media_type: str = "all", 
        directory: str = "~/Pictures", 
        max_results: int = 20,
        similarity_threshold: float = 0.75
    ) -> ToolResult:
        start = datetime.now()
        try:
            # This would use CLIP embeddings - placeholder implementation
            # Full implementation requires CLIP model and FAISS index
            target_dir = Path(directory).expanduser()
            if not target_dir.exists():
                return ToolResult(False, error=f"Directory '{target_dir}' not found", tool_name=self.tool.name)
            
            # Placeholder - in reality, this would:
            # 1. Load CLIP model
            # 2. Embed the query text
            # 3. Search FAISS index of pre-computed media embeddings
            # 4. Return matching files with similarity scores
            
            output = f"Media search for: '{query}'\n"
            output += f"Type: {media_type}\n"
            output += f"Directory: {target_dir}\n"
            output += f"Note: Requires CLIP index to be built. Run 'build_media_index' first.\n"
            
            return ToolResult(True, output=output, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


class BuildMediaIndexTool(ToolExecutor):
    """Build CLIP index for media files."""
    
    def __init__(self):
        tool = Tool(
            name="build_media_index",
            description="Build CLIP embeddings index for media files",
            category=ToolCategory.MEDIA,
            parameters=[
                ToolParameter("directory", "string", "Directory to index", default="~/Pictures"),
                ToolParameter("media_types", "array", "Types to index", default=["images", "videos"]),
                ToolParameter("recursive", "boolean", "Recursive search", default=True),
            ],
            returns="string",
        )
        super().__init__(tool)
    
    async def execute(self, directory: str = "~/Pictures", media_types: List[str] = None, recursive: bool = True) -> ToolResult:
        start = datetime.now()
        try:
            if media_types is None:
                media_types = ["images", "videos"]
            
            target_dir = Path(directory).expanduser()
            if not target_dir.exists():
                return ToolResult(False, error=f"Directory '{target_dir}' not found", tool_name=self.tool.name)
            
            # This would build the actual index
            # Placeholder implementation
            output = f"Building media index for: {target_dir}\n"
            output += f"Media types: {', '.join(media_types)}\n"
            output += f"Recursive: {recursive}\n"
            output += "Note: Full implementation requires CLIP + FAISS setup.\n"
            
            return ToolResult(True, output=output, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# AI Tools
# ============================================================

class AnalyzeImageTool(ToolExecutor):
    """Analyze image with vision model."""
    
    def __init__(self):
        tool = Tool(
            name="analyze_image",
            description="Analyze an image using vision model",
            category=ToolCategory.AI,
            parameters=[
                ToolParameter("image_path", "string", "Path to image file"),
                ToolParameter("prompt", "string", "Analysis prompt", default="Describe this image in detail"),
                ToolParameter("model", "string", "Vision model to use", default=""),
            ],
            returns="string",
            requires_permission="use_vision",
        )
        super().__init__(tool)
    
    async def execute(self, image_path: str, prompt: str = "Describe this image in detail", model: str = "") -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.use_vision:
                return ToolResult(False, error="Vision permission denied", tool_name=self.tool.name)
            
            target = Path(image_path).expanduser().resolve()
            if not target.exists():
                return ToolResult(False, error=f"Image not found: {target}", tool_name=self.tool.name)
            
            # Read and encode image
            async with aiofiles.open(target, 'rb') as f:
                image_data = await f.read()
            b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(target))
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = 'image/jpeg'
            
            # Use provider manager
            from active_assistant.core.providers import chat_completion, ModelType, Message
            
            messages = [
                Message(role="user", content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
                ])
            ]
            
            model_name = model or provider_manager.get_model(ModelType.VISION)
            response = await chat_completion(messages, ModelType.VISION, model=model_name)
            
            state.increment_metric("api_calls")
            return ToolResult(True, output=response.content, tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"model": model_name, "image": str(target)})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# Plugin Tools
# ============================================================

class RunPluginTool(ToolExecutor):
    """Execute a plugin."""
    
    def __init__(self):
        tool = Tool(
            name="run_plugin",
            description="Execute a plugin by name",
            category=ToolCategory.PLUGIN,
            parameters=[
                ToolParameter("plugin_name", "string", "Name of plugin to run"),
                ToolParameter("action", "string", "Plugin action to execute"),
                ToolParameter("params", "object", "Parameters for the plugin", default={}),
            ],
            returns="string",
            requires_permission="plugin_execution",
        )
        super().__init__(tool)
    
    async def execute(self, plugin_name: str, action: str, params: Dict = None) -> ToolResult:
        start = datetime.now()
        try:
            cfg = get_config()
            if not cfg.rules.permissions.plugin_execution:
                return ToolResult(False, error="Plugin execution permission denied", tool_name=self.tool.name)
            
            # Import plugin manager
            from active_assistant.plugins.manager import plugin_manager
            
            if params is None:
                params = {}
            
            result = await plugin_manager.execute(plugin_name, action, **params)
            
            return ToolResult(True, output=str(result), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds(),
                            metadata={"plugin": plugin_name, "action": action})
        except Exception as e:
            return ToolResult(False, error=str(e), tool_name=self.tool.name,
                            execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# Tool Registry
# ============================================================

class ToolRegistry:
    """Registry for all available tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolExecutor] = {}
        self._categories: Dict[ToolCategory, List[str]] = {}
        self._permission_map: Dict[str, str] = {}
    
    def register(self, executor: ToolExecutor) -> None:
        """Register a tool executor."""
        self._tools[executor.tool.name] = executor
        if executor.tool.category not in self._categories:
            self._categories[executor.tool.category] = []
        self._categories[executor.tool.category].append(executor.tool.name)
        
        if executor.tool.requires_permission:
            self._permission_map[executor.tool.name] = executor.tool.requires_permission
        
        logger.debug(f"Registered tool: {executor.tool.name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            tool = self._tools.pop(name)
            if tool.tool.category in self._categories:
                self._categories[tool.tool.category].remove(name)
            if name in self._permission_map:
                del self._permission_map[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[ToolExecutor]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_all(self) -> Dict[str, ToolExecutor]:
        """Get all tools."""
        return self._tools.copy()
    
    def get_by_category(self, category: ToolCategory) -> List[ToolExecutor]:
        """Get tools by category."""
        names = self._categories.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]
    
    def get_openai_tools(self, category: ToolCategory | None = None) -> List[Dict]:
        """Get tools in OpenAI function calling format."""
        tools = self.get_by_category(category) if category else self._tools.values()
        return [t.tool.to_openai_format() for t in tools]
    
    def check_permission(self, tool_name: str) -> bool:
        """Check if tool is allowed by current permissions."""
        perm = self._permission_map.get(tool_name)
        if not perm:
            return True
        cfg = get_config()
        return getattr(cfg.rules.permissions, perm, False)
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        executor = self._tools.get(name)
        if not executor:
            return ToolResult(False, error=f"Tool not found: {name}", tool_name=name)
        
        if not self.check_permission(name):
            return ToolResult(False, error=f"Permission denied for tool: {name}", tool_name=name)
        
        return await executor.execute(**kwargs)


# Global registry
tool_registry = ToolRegistry()


# ============================================================
# Built-in Tool Registration
# ============================================================

def register_builtin_tools():
    """Register all built-in tools."""
    tools = [
        ListDirectoryTool(),
        ReadFileTool(),
        WriteFileTool(),
        SearchFilesTool(),
        DeleteFileTool(),
        ExecuteCommandTool(),
        SystemInfoTool(),
        WebSearchTool(),
        WebCrawlTool(),
        MediaSearchTool(),
        BuildMediaIndexTool(),
        AnalyzeImageTool(),
        RunPluginTool(),
    ]
    
    for tool in tools:
        tool_registry.register(tool)
    
    logger.info(f"Registered {len(tools)} built-in tools")


# Initialize on import
register_builtin_tools()