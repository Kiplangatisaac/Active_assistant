"""MCP (Model Context Protocol) server integration for Active Assistant."""

from .server import MCPServer
from .client import MCPClient

__all__ = ["MCPServer", "MCPClient"]