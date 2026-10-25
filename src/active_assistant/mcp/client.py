"""
MCP Client for Active Assistant.

Connects to external MCP servers to call their tools and access resources.
Acts as a client-side bridge so Active Assistant can use remote capabilities.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

try:
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    from mcp.types import (
        Tool,
        Tool as ToolType,
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        ListResourcesRequest,
        ListResourcesResult,
        ReadResourceRequest,
        ReadResourceResult,
    )
except Exception:
    stdio_client = None
    sse_client = None
    Tool = ToolType = CallToolRequest = CallToolResult = None
    ListToolsRequest = ListToolsResult = None
    ListResourcesRequest = ListResourcesResult = None
    ReadResourceRequest = ReadResourceResult = None

from loguru import logger


class MCPClient:
    """Client for connecting to remote MCP servers."""

    def __init__(self, name: str = "active-assistant-client"):
        self.name = name
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._initialized = False
        self._tools: dict = {}
        self._resources: dict = {}

    @property
    def is_connected(self) -> bool:
        return self._initialized and self._session is not None

    async def connect_stdio(self, command: str, args: list[str] | None = None) -> bool:
        """Connect to an MCP server via stdio transport."""
        try:
            from mcp.client.stdio import stdio_client

            self._read_stream, self._write_stream = await stdio_client(
                command=command,
                args=args or [],
            )

            from mcp.client.session import ClientSession
            self._session = ClientSession(self._read_stream, self._write_stream)
            await self._session.initialize()

            self._initialized = True
            await self._discover_capabilities()
            logger.info(f"MCP client connected to stdio server: {command}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to stdio server: {e}")
            return False

    async def connect_sse(self, url: str) -> bool:
        """Connect to an MCP server via SSE transport."""
        try:
            from mcp.client.sse import sse_client

            self._read_stream, self._write_stream = await sse_client(url)

            from mcp.client.session import ClientSession
            self._session = ClientSession(self._read_stream, self._write_stream)
            await self._session.initialize()

            self._initialized = True
            await self._discover_capabilities()
            logger.info(f"MCP client connected to SSE server: {url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to SSE server: {e}")
            return False

    async def _discover_capabilities(self) -> None:
        """Discover available tools and resources from the server."""
        if not self._session:
            return

        try:
            # List tools
            tools_result = await self._session.list_tools()
            for tool in tools_result.tools:
                self._tools[tool.name] = tool
                logger.debug(f"Discovered tool: {tool.name}")

            # List resources
            resources_result = await self._session.list_resources()
            for resource in resources_result.resources:
                self._resources[resource.uri] = resource
                logger.debug(f"Discovered resource: {resource.uri}")

        except Exception as e:
            logger.error(f"Failed to discover capabilities: {e}")

    async def list_tools(self) -> list:
        """List available tools from the connected server."""
        if not self._session:
            return []
        result = await self._session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict = None) -> str:
        """Call a tool on the remote server."""
        if not self._session:
            raise RuntimeError("MCP client not connected")

        result = await self._session.call_tool(name, arguments or {})
        if result.content:
            return "\n".join(
                c.text for c in result.content if hasattr(c, "text")
            )
        return ""

    async def list_resources(self) -> list:
        """List available resources from the server."""
        if not self._session:
            return []
        result = await self._session.list_resources()
        return result.resources

    async def read_resource(self, uri: str) -> str:
        """Read a resource from the server."""
        if not self._session:
            raise RuntimeError("MCP client not connected")
        result = await self._session.read_resource(uri)
        if result.contents:
            return "\n".join(
                c.text for c in result.contents if hasattr(c, "text")
            )
        return ""

    async def close(self) -> None:
        """Close the connection."""
        self._initialized = False
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._tools.clear()
        self._resources.clear()
        logger.info("MCP client disconnected")


# Global client instance
mcp_client = MCPClient()