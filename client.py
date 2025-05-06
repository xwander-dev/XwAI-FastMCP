#!/usr/bin/env python3
"""
XwAI FastMCP 2.2.7 Client

A clean, minimal implementation of a FastMCP client for interacting
with the XwAI server.
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

# FastMCP 2.2.7 imports
from fastmcp import FastMCP, Client, content_to_text

# Local imports
from tools.utils import load_env_file

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("xwai-client")

class XwAIClient:
    """XwAI FastMCP Client implementation"""
    
    def __init__(self, server_url="http://localhost:9001/sse", env_file=None):
        """Initialize the XwAI FastMCP client"""
        # Load environment variables
        load_env_file(env_file)
        
        self.server_url = server_url
        self.client = Client(self.server_url)
        self.client.server_url = self.server_url  # Store for completer
        
        logger.info(f"XwAI FastMCP 2.2.7 Client initialized with server URL: {server_url}")
    
    async def connect(self):
        """Connect to the FastMCP server"""
        try:
            # Connect to server and get the MCP instance
            mcp = FastMCP.from_client(self.client)
            
            # Check connection by fetching available tools
            tools = await mcp.list_tools()
            logger.info(f"Connected to server with {len(tools)} tools available")
            
            return mcp, tools
        except Exception as e:
            logger.error(f"Failed to connect to FastMCP server: {str(e)}")
            return None, []
    
    async def call_tool(self, tool_name, **params):
        """Call a tool on the FastMCP server"""
        try:
            # Connect to server
            mcp, tools = await self.connect()
            if not mcp:
                return {"error": "Failed to connect to server"}
            
            # Check if tool exists
            tool_exists = any(t.name == tool_name for t in tools)
            if not tool_exists:
                return {"error": f"Tool '{tool_name}' not found on server"}
            
            # Call the tool
            logger.info(f"Calling tool '{tool_name}' with params: {params}")
            result = await mcp.tools.execute(tool_name, **params)
            
            # Process the result
            text_result = content_to_text(result)
            
            try:
                # Try to parse JSON result
                if text_result and (text_result.startswith("{") or text_result.startswith("[")):
                    return json.loads(text_result)
                else:
                    return {"result": text_result}
            except json.JSONDecodeError:
                # Return raw text if not valid JSON
                return {"result": text_result}
            
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {str(e)}")
            return {"error": str(e)}

async def main():
    """Main entry point for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='XwAI FastMCP Client')
    parser.add_argument('--url', type=str, default="http://localhost:9001/sse",
                        help='FastMCP server URL (default: http://localhost:9001/sse)')
    parser.add_argument('--env', type=str, default=None,
                        help='Path to .env file (default: None)')
    parser.add_argument('--tool', type=str, required=True,
                        help='Tool name to call')
    parser.add_argument('--params', type=str, default="{}",
                        help='JSON string of parameters to pass to the tool')
    
    args = parser.parse_args()
    
    # Create client
    client = XwAIClient(args.url, args.env)
    
    # Parse parameters
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON parameters: {args.params}")
        sys.exit(1)
    
    # Call tool
    result = await client.call_tool(args.tool, **params)
    
    # Print result
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())