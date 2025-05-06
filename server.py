#!/usr/bin/env python3
"""
XwAI FastMCP 2.2.7 Server

A clean, minimal implementation of a FastMCP server with SSE transport
and Claude 3.7 integration with proper Tool Use pattern.
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path

# FastMCP 2.2.7 imports
from fastmcp import FastMCP, Context, Tool, ToolDefinition, content_to_text
from fastmcp.transports import SSETransport

# Utils import - will create later
from tools.utils import load_env_file

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("xwai-server")

# Server class
class XwAIServer:
    """XwAI FastMCP 2.2.7 Server implementation"""
    
    def __init__(self, host="0.0.0.0", port=9001, env_file=None):
        """Initialize the XwAI FastMCP server"""
        # Load environment variables
        load_env_file(env_file)
        
        # Server settings
        self.host = host
        self.port = port
        
        # Create FastMCP instance
        self.mcp = FastMCP(name="XwAI FastMCP Server", version="0.1.0")
        
        # Register tools
        self._register_tools()
        logger.info(f"XwAI FastMCP 2.2.7 Server initialized with {len(self.mcp.tools)} tools")
    
    def _register_tools(self):
        """Register FastMCP tools"""
        
        @self.mcp.tool()
        async def echo(message: str) -> Dict[str, Any]:
            """Echo the given message back to the user."""
            return {"result": message}
        
        @self.mcp.tool()
        async def get_time() -> Dict[str, Any]:
            """Get the current server time."""
            return {"result": datetime.now().isoformat()}
        
        @self.mcp.tool()
        async def get_server_info() -> Dict[str, Any]:
            """Get information about the XwAI server."""
            return {
                "name": "XwAI FastMCP Server",
                "version": "0.1.0",
                "tools": [t.name for t in self.mcp.tools],
                "start_time": getattr(self, "start_time", datetime.now().isoformat())
            }

        # Import and register Slite tool if SLITE_API_KEY is set
        if "SLITE_API_KEY" in os.environ:
            try:
                from tools.slite import register_slite_tools
                register_slite_tools(self.mcp)
                logger.info("Slite tools registered successfully")
            except Exception as e:
                logger.error(f"Failed to register Slite tools: {str(e)}")
        else:
            logger.warning("SLITE_API_KEY not found, Slite tools will not be available")
            
        # Import and register Claude tool if CLAUDE_API_KEY is set
        if "CLAUDE_API_KEY" in os.environ:
            try:
                from tools.claude import register_claude_tools
                register_claude_tools(self.mcp)
                logger.info("Claude tools registered successfully")
            except Exception as e:
                logger.error(f"Failed to register Claude tools: {str(e)}")
        else:
            logger.warning("CLAUDE_API_KEY not found, Claude tools will not be available")
    
    async def run(self):
        """Run the XwAI FastMCP Server"""
        # Set start time
        self.start_time = datetime.now().isoformat()
        
        logger.info(f"Starting XwAI FastMCP 2.2.7 Server on {self.host}:{self.port} using SSE transport")
        
        # Run with SSE transport
        await self.mcp.run(transport="sse", host=self.host, port=self.port)

# Main entry point
async def main():
    """Main entry point"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='XwAI FastMCP Server')
    parser.add_argument('--host', type=str, default="0.0.0.0",
                        help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=9001,
                        help='Port to bind to (default: 9001)')
    parser.add_argument('--env', type=str, default=None,
                        help='Path to .env file (default: None)')
    
    args = parser.parse_args()
    
    # Create and run server
    server = XwAIServer(host=args.host, port=args.port, env_file=args.env)
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())