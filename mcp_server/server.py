"""
Core MCP server for Find Evil! agent.

Exposes SIFT forensic tools as typed, safe MCP functions with:
- Input validation
- Error handling
- Read-only enforcement
- Server health checks
- HTTP endpoints for tool access
"""

import asyncio
import json
import logging
import sys
import uuid
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.types import TextContent, Tool

from agent.logger import StructuredLogger
from mcp_server.tools import (
    analyze_processes,
    check_injections,
    extract_timeline,
    get_amcache,
    get_mft,
    get_network_connections,
    get_prefetch,
    get_registry_hives,
    get_shimcache,
    parse_evtx,
)

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Initialize logger with session ID
_session_id = str(uuid.uuid4())[:8]
logger = StructuredLogger("mcp-server", session_id=_session_id)

# Tool definitions for MCP protocol
DISK_TOOLS = [
    {
        "name": "get_mft",
        "description": "Extract and analyze the Master File Table from a disk image",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to disk image file (read-only)",
                },
                "partition": {
                    "type": "string",
                    "description": "Partition number (default: 0)",
                    "default": "0",
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "get_amcache",
        "description": "Extract application execution cache from Registry",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to disk image file (read-only)",
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "get_prefetch",
        "description": "Extract prefetch files for program execution analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to disk image file (read-only)",
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "get_shimcache",
        "description": "Extract Shimcache (Application Compatibility Cache) data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to disk image file (read-only)",
                },
            },
            "required": ["image_path"],
        },
    },
]

MEMORY_TOOLS = [
    {
        "name": "analyze_processes",
        "description": "Extract and analyze running processes from memory dump",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_path": {
                    "type": "string",
                    "description": "Path to memory dump file (read-only)",
                },
            },
            "required": ["memory_path"],
        },
    },
    {
        "name": "check_injections",
        "description": "Detect code injection and suspicious memory patterns",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_path": {
                    "type": "string",
                    "description": "Path to memory dump file (read-only)",
                },
            },
            "required": ["memory_path"],
        },
    },
    {
        "name": "get_network_connections",
        "description": "Extract network connections from memory dump",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_path": {
                    "type": "string",
                    "description": "Path to memory dump file (read-only)",
                },
            },
            "required": ["memory_path"],
        },
    },
]

LOG_TOOLS = [
    {
        "name": "parse_evtx",
        "description": "Parse Windows Event Log files for forensic evidence",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_path": {
                    "type": "string",
                    "description": "Path to .evtx file (read-only)",
                },
            },
            "required": ["log_path"],
        },
    },
    {
        "name": "extract_timeline",
        "description": "Extract unified timeline from disk image using Plaso",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to disk image (read-only)",
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "get_registry_hives",
        "description": "Extract and parse Registry hives from disk image",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to disk image (read-only)",
                },
            },
            "required": ["image_path"],
        },
    },
]

ALL_TOOLS = DISK_TOOLS + MEMORY_TOOLS + LOG_TOOLS


class FindEvilMCPServer:
    """MCP Server for Find Evil! incident response agent."""

    def __init__(self):
        """Initialize the MCP server."""
        self.server = Server("find-evil")
        self._register_handlers()
        self.logger = logger

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"],
                )
                for tool in ALL_TOOLS
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
            """Execute a tool by name."""
            try:
                # Validate tool name
                if not any(t["name"] == name for t in ALL_TOOLS):
                    raise ValueError(f"Unknown tool: {name}")

                # Call appropriate tool (wrapped with asyncio.to_thread to prevent event loop blocking)
                if name == "get_mft":
                    result = await asyncio.to_thread(
                        get_mft,
                        arguments["image_path"],
                        arguments.get("partition", "0"),
                    )
                elif name == "get_amcache":
                    result = await asyncio.to_thread(
                        get_amcache,
                        arguments["image_path"],
                    )
                elif name == "get_prefetch":
                    result = await asyncio.to_thread(
                        get_prefetch,
                        arguments["image_path"],
                    )
                elif name == "get_shimcache":
                    result = await asyncio.to_thread(
                        get_shimcache,
                        arguments["image_path"],
                    )
                elif name == "analyze_processes":
                    result = await asyncio.to_thread(
                        analyze_processes,
                        arguments["memory_path"],
                    )
                elif name == "check_injections":
                    result = await asyncio.to_thread(
                        check_injections,
                        arguments["memory_path"],
                    )
                elif name == "get_network_connections":
                    result = await asyncio.to_thread(
                        get_network_connections,
                        arguments["memory_path"],
                    )
                elif name == "parse_evtx":
                    result = await asyncio.to_thread(
                        parse_evtx,
                        arguments["log_path"],
                    )
                elif name == "extract_timeline":
                    result = await asyncio.to_thread(
                        extract_timeline,
                        arguments["image_path"],
                    )
                elif name == "get_registry_hives":
                    result = await asyncio.to_thread(
                        get_registry_hives,
                        arguments["image_path"],
                    )
                else:
                    raise ValueError(f"Tool {name} not implemented")

                # Log tool call
                self.logger.log_tool_call(
                    tool_name=name,
                    input_params=arguments,
                    output=result,
                    token_count=0,
                    confidence_score=1.0 if result.get("status") == "success" else 0.0,
                    error=result.get("error"),
                )

                # Return result as JSON string
                return [TextContent(type="text", text=json.dumps(result, default=str))]

            except Exception as e:
                error_msg = f"Error calling tool {name}: {str(e)}"
                self.logger.logger.error(error_msg)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "status": "error",
                                "error": error_msg,
                            },
                            default=str,
                        ),
                    )
                ]

    async def run(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """
        Run the MCP server.

        Args:
            host: Server host (default: 127.0.0.1)
            port: Server port (default: 8765)
        """
        if not AIOHTTP_AVAILABLE:
            self.logger.logger.warning("aiohttp not available, running without HTTP wrapper")
            try:
                async with self.server:
                    self.logger.logger.info("MCP server running (MCP protocol only)")
                    await asyncio.Event().wait()
            except KeyboardInterrupt:
                self.logger.logger.info("MCP server shutting down...")
            return

        # Start both MCP and HTTP servers
        await self._start_with_http(host, port)

    async def _start_with_http(self, host: str, port: int) -> None:
        """
        Start MCP server with aiohttp HTTP wrapper.

        Args:
            host: Server host
            port: Server port
        """
        # Create aiohttp app
        app = web.Application()

        # Add HTTP routes
        app.router.add_get("/health", self._http_health_handler)
        app.router.add_get("/tools", self._http_tools_handler)
        app.router.add_post("/tool/{tool_name}", self._http_tool_handler)

        # Start HTTP server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        self.logger.logger.info(f"HTTP server started on http://{host}:{port}")

        try:
            # Start MCP server alongside HTTP server
            async with self.server:
                self.logger.logger.info(f"Find Evil! MCP server ready on {host}:{port}")
                # Keep server running
                await asyncio.Event().wait()
        except KeyboardInterrupt:
            self.logger.logger.info("Server shutting down...")
        finally:
            await runner.cleanup()

    async def _http_health_handler(self, request: "web.Request") -> "web.Response":
        """
        HTTP GET /health endpoint.

        Returns:
            JSON health status
        """
        health = await self.health_check()
        return web.json_response(health)

    async def _http_tools_handler(self, request: "web.Request") -> "web.Response":
        """
        HTTP GET /tools endpoint.

        Returns:
            JSON list of available tools with signatures
        """
        tools_info = []
        for tool in ALL_TOOLS:
            tools_info.append({
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            })
        return web.json_response({"tools": tools_info, "count": len(tools_info)})

    async def _http_tool_handler(self, request: "web.Request") -> "web.Response":
        """
        HTTP POST /tool/{tool_name} endpoint.

        Request body: JSON with tool parameters
        Response: JSON with tool output

        Args:
            request: aiohttp request

        Returns:
            JSON response with tool output
        """
        tool_name = request.match_info["tool_name"]

        try:
            # Get JSON parameters from request body
            params = await request.json()

            # Validate tool exists
            if not any(t["name"] == tool_name for t in ALL_TOOLS):
                return web.json_response(
                    {"status": "error", "error": f"Unknown tool: {tool_name}"},
                    status=404,
                )

            # Call tool
            result = await self._call_tool_by_name(tool_name, params)

            return web.json_response(result)

        except json.JSONDecodeError:
            return web.json_response(
                {"status": "error", "error": "Invalid JSON in request body"},
                status=400,
            )
        except Exception as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
            )

    async def _call_tool_by_name(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool by name with parameters.

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            Tool output dict
        """
        try:
            # Wrap all tool calls with asyncio.to_thread to prevent event loop blocking
            if tool_name == "get_mft":
                result = await asyncio.to_thread(
                    get_mft,
                    params["image_path"],
                    params.get("partition", "0"),
                )
            elif tool_name == "get_amcache":
                result = await asyncio.to_thread(
                    get_amcache,
                    params["image_path"],
                )
            elif tool_name == "get_prefetch":
                result = await asyncio.to_thread(
                    get_prefetch,
                    params["image_path"],
                )
            elif tool_name == "get_shimcache":
                result = await asyncio.to_thread(
                    get_shimcache,
                    params["image_path"],
                )
            elif tool_name == "analyze_processes":
                result = await asyncio.to_thread(
                    analyze_processes,
                    params["memory_path"],
                )
            elif tool_name == "check_injections":
                result = await asyncio.to_thread(
                    check_injections,
                    params["memory_path"],
                )
            elif tool_name == "get_network_connections":
                result = await asyncio.to_thread(
                    get_network_connections,
                    params["memory_path"],
                )
            elif tool_name == "parse_evtx":
                result = await asyncio.to_thread(
                    parse_evtx,
                    params["log_path"],
                )
            elif tool_name == "extract_timeline":
                result = await asyncio.to_thread(
                    extract_timeline,
                    params["image_path"],
                )
            elif tool_name == "get_registry_hives":
                result = await asyncio.to_thread(
                    get_registry_hives,
                    params["image_path"],
                )
            else:
                return {"status": "error", "error": f"Tool {tool_name} not implemented"}

            return result

        except KeyError as e:
            return {"status": "error", "error": f"Missing required parameter: {e}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def start(self) -> None:
        """
        Start the server (async entry point).

        Used by agent to start server in background.
        """
        from config import MCP_SERVER_HOST, MCP_SERVER_PORT
        await self.run(host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)

    async def health_check(self) -> Dict[str, Any]:
        """
        Check server health.

        Returns:
            Health status dict
        """
        return {
            "status": "healthy",
            "tools_available": len(ALL_TOOLS),
            "disk_tools": len(DISK_TOOLS),
            "memory_tools": len(MEMORY_TOOLS),
            "log_tools": len(LOG_TOOLS),
        }


def create_server() -> FindEvilMCPServer:
    """Create and return a Find Evil MCP server instance."""
    return FindEvilMCPServer()


if __name__ == "__main__":
    # Run server
    server = create_server()
    asyncio.run(server.run())
