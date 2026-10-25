"""
MCP (Model Context Protocol) Server for Active Assistant.

Exposes all assistant capabilities as MCP resources, tools, and prompts.
Remote AI assistants can connect to this server to access tools,
read screenshots, read files, run commands, and more over stdio or SSE transport.
"""

from __future__ import annotations

import asyncio
import asyncio.subprocess
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus
from active_assistant.tools.base import tool_registry
from active_assistant.core.monitor import screen_monitor
from active_assistant.core.monitor import screen_capture, compute_dhash, image_to_base64

logger = logging.getLogger("active_assistant.mcp.server")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.sse import SseServerTransport
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
        TextResourceContents,
        CallToolRequest,
        CallToolResult,
        ListResourcesRequest,
        ListResourcesResult,
        ListToolsRequest,
        ListToolsResult,
        CallToolResult,
    )
except Exception as e:
    logger.warning(f"MCP dependencies not available: {e}")
    Server = None
    stdio_server = None
    SseServerTransport = None
    Tool = TextContent = Resource = TextResourceContents = None
    CallToolRequest = CallToolResult = None
    ListResourcesRequest = ListResourcesResult = None
    ListToolsRequest = ListToolsResult = None


class MCPServer:
    """MCP server that exposes Active Assistant capabilities."""

    def __init__(self, host: str = "127.0.0.1", port: int = 49215):
        self.host = host
        self.port = port
        self.server: Optional[Server] = None
        self._sse_transport: Optional[SseServerTransport] = None
        self._initialized = False

    def is_available(self) -> bool:
        return Server is not None and self._initialized

    async def initialize(self) -> bool:
        """Initialize the MCP server with all tools and resources."""
        if not Server:
            logger.warning("MCP server dependencies not installed. Install 'mcp' package.")
            return False

        try:
            self.server = Server("active-assistant")
            self._register_handlers()
            self._initialized = True
            logger.info("MCP server initialized with %d tools", len(self._get_tools()))
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {e}")
            return False

    def _get_tools(self) -> List[Tool]:
        """Convert Active Assistant tools to MCP Tool format."""
        tools = []
        for name, executor in tool_registry.get_all().items():
            tools.append(
                Tool(
                    name=name,
                    description=executor.tool.description or "",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                )
            )
        return tools

    def _register_handlers(self) -> None:
        """Register MCP request handlers."""
        if not self.server:
            return

        @self.server.list_tools()
        async def list_tools() -> ListToolsResult:
            return ListToolsResult(tools=self._get_tools())

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            return await self._handle_tool_call(name, arguments)

        @self.server.list_resources()
        async def list_resources() -> ListResourcesResult:
            resources = [
                Resource(
                    uri="active-assistant://screen",
                    name="Current Screen",
                    description="Current foreground window screenshot",
                    mimeType="image/jpeg",
                ),
                Resource(
                    uri="active-assistant://window",
                    name="Active Window Info",
                    description="Current foreground window title and process",
                    mimeType="application/json",
                ),
                Resource(
                    url="active-assistant://metrics",
                    name="System Metrics",
                    description="Current assistant metrics (captures, issues, tools)",
                    mimeType="application/json",
                ),
            ]
            return ListResourcesResult(resources=resources)

        @self.server.read_resource()
        async def read_resource(uri: str) -> List[TextResourceContents]:
            return await self._read_resource(uri)

    async def _handle_tool_call(self, name: str, args: Dict[str, Any]) -> List[TextContent]:
        """Execute a tool call via the tool registry."""
        try:
            executor = tool_registry.get(name)
            if not executor:
                return [TextContent(type="text", text=f"Tool '{name}' not found.")]

            result = await executor.execute(**args)
            return [TextContent(type="text", text=str(result.output or result.error))]

        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    async def _read_resource(self, uri: str) -> List[TextResourceContents]:
        """Read a resource (screen capture, window info, metrics)."""
        try:
            if uri == "active-assistant://screen":
                img = screen_capture.capture_region(0, 0, 1920, 1080)
                if img:
                    b64 = image_to_base64(img)
                    return [TextResourceContents(
                        uri=uri,
                        mimeType="image/jpeg",
                        text=b64,
                    )]
                return [TextResourceContents(uri=uri, mimeType="image/jpeg", text="")]

            elif uri == "active-assistant://window":
                import win32gui
                import win32process
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                import json
                return [TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=json.dumps({"title": title, "pid": pid, "hwnd": hwnd}),
                )]

            elif uri == "active-assistant://metrics":
                import json
                metrics = state.metrics
                data = {
                    "screens_captured": metrics.screens_captured,
                    "issues_detected": metrics.issues_detected,
                    "tools_executed": metrics.tools_executed,
                    "uptime_seconds": metrics.uptime_seconds,
                }
                return [TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=json.dumps(data),
                )]

            return [TextResourceContents(uri=uri, mimeType="text/plain", text="")]

        except Exception as e:
            logger.error(f"Resource read error for {uri}: {e}")
            return [TextResourceContents(uri=uri, mimeType="text/plain", text=str(e))]

    async def run_stdio(self) -> None:
        """Run the MCP server over stdio transport."""
        if not self.server:
            raise RuntimeError("Server not initialized")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

    async def run_sse(self, host: str = None, port: int = None) -> None:
        """Run the MCP server over SSE transport."""
        if not self.server:
            raise RuntimeError("Server not initialized")

        host = host or self.host
        port = port or self.port

        from starlette.applications import Starlette
        from starlette.routing import Mount
        from sse_starlette import EventSourceResponse

        async def handle_sse(request):
            async def event_generator():
                async for event in self._sse_event_stream():
                    yield event

            return EventSourceResponse(event_generator())

        app = Starlette(
            routes=[
                Mount("/messages", self._sse_handler),
                get("/sse", handle_sse),
            ]
        )

        import uvicorn
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    async def _sse_handler(self, scope, receive, send):
        """Handle SSE connection for MCP."""
        async with self._sse_context(receive, send) as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

    async def _sse_context(self, receive, send):
        """Create an SSE context for the connection."""
        # This is a simplified version - in production you'd use proper SSE transport
        async def receive_wrapper():
            return await receive()

        async def send_wrapper(message):
            await send(message)

        # This is a simplified wrapper - actual SSE transport needs more work
        yield receive_wrapper, send_wrapper

    async def start(self) -> None:
        """Start the MCP server."""
        if not self._initialized:
            await self.initialize()

        if self._initialized:
            await self.run_sse()