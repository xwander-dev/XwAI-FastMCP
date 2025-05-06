"""
Slite knowledge base integration for XwAI FastMCP.

This module provides integration with the Slite knowledge base via the Slite-MCP
server, including proper FastMCP tool registration and method translation.
"""

import os
import json
import httpx
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urljoin

from fastmcp import FastMCP, Context
from fastmcp.client import Client
from fastmcp.client.transports import SseClientTransport
from fastmcp.schemas import JsonRPCRequest

from config import get_config

# Get configuration
config = get_config()
slite_config = config.get_slite_config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("slite")

class SliteMCPClient:
    """Client for interacting with the Slite-MCP server via HTTP."""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8001", 
        endpoint: str = "/mcp", 
        timeout: int = 30,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Slite-MCP client.
        
        Args:
            base_url: Base URL of the Slite-MCP server
            endpoint: API endpoint
            timeout: Request timeout in seconds
            api_key: Slite API key (falls back to environment variable)
        """
        self.base_url = base_url
        self.endpoint = endpoint
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("SLITE_API_KEY", "")
        
        # Headers with API key if available
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self.client = httpx.AsyncClient(timeout=timeout, headers=headers)
        self.api_url = urljoin(base_url, endpoint)
        logger.info(f"Initialized Slite-MCP client with URL: {self.api_url}")
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the Slite-MCP server.
        
        Returns:
            Health status
        """
        try:
            health_url = urljoin(self.base_url, "/health")
            response = await self.client.get(health_url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def call_method(self, method: str, params: Dict[str, Any], request_id: str = "xwai") -> Dict[str, Any]:
        """
        Call a method on the Slite-MCP server.
        
        Args:
            method: Method name
            params: Method parameters
            request_id: Request ID
            
        Returns:
            Response data
            
        Raises:
            ValueError: If the request fails
        """
        # Prepare the JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        try:
            # Send the request
            logger.debug(f"Sending request to Slite-MCP: {json.dumps(request)}")
            response = await self.client.post(
                self.api_url,
                json=request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            logger.debug(f"Received response from Slite-MCP: {json.dumps(result)}")
            
            # Check for errors
            if "error" in result:
                error = result["error"]
                error_msg = error.get("message", "Unknown error")
                logger.error(f"Slite-MCP error: {error_msg}")
                raise ValueError(f"Slite-MCP error: {error_msg}")
            
            return result
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Slite-MCP: {str(e)}")
            raise ValueError(f"HTTP error: {str(e)}")
        except ValueError:
            # Re-raise ValueError errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Slite-MCP: {str(e)}")
            raise ValueError(f"Unexpected error: {str(e)}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools on the Slite-MCP server.
        
        Returns:
            Available tools
        """
        try:
            result = await self.call_method("tools/list", {})
            return result.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            return []
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize connection to the Slite-MCP server.
        
        Returns:
            Initialization result
        """
        params = {
            "protocolVersion": "2025-03-26",
            "clientInfo": {
                "name": "XwAI FastMCP",
                "version": "0.1.0"
            },
            "capabilities": {
                "tools": {
                    "execute": True
                }
            }
        }
        
        try:
            result = await self.call_method("initialize", params)
            return result.get("result", {})
        except Exception as e:
            logger.error(f"Error initializing Slite-MCP client: {str(e)}")
            return {"error": str(e)}
    
    async def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the Slite-MCP server.
        
        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            
        Returns:
            Tool result
        """
        # The Slite-MCP server expects a specific format for tool calls
        params = {
            "name": tool_name,
            "arguments": tool_args
        }
        
        try:
            # Send the request using the correct method (tools/call for Slite-MCP)
            result = await self.call_method("tools/call", params)
            return result.get("result", {})
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {str(e)}")
            return {"error": str(e)}
    
    async def search_notes(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search for notes in Slite.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            Search results
        """
        return await self.call_tool("search-notes", {"query": query, "limit": limit})
    
    async def ask_slite(self, question: str) -> Dict[str, Any]:
        """
        Ask a question to Slite.
        
        Args:
            question: Question to ask
            
        Returns:
            Answer with sources
        """
        return await self.call_tool("ask-slite", {"question": question})
    
    async def get_note(self, note_id: str) -> Dict[str, Any]:
        """
        Get a note by ID.
        
        Args:
            note_id: Note ID
            
        Returns:
            Note details
        """
        return await self.call_tool("get-note", {"noteId": note_id})


class SliteMethodTranslator:
    """
    Translator for converting between standard MCP method format and Slite's format.
    
    Slite-MCP uses 'tools/call' with 'arguments' parameter while standard MCP uses
    'tools/execute' with 'input' parameter.
    """
    
    def __init__(self):
        """Initialize the translator with statistics tracking."""
        self.translations_count = 0
        self.errors_count = 0
        self.last_error = None
    
    async def __call__(self, request: Union[Dict[str, Any], JsonRPCRequest]) -> Dict[str, Any]:
        """
        Translate standard MCP request format to Slite format.
        
        Args:
            request: The request to translate
            
        Returns:
            Translated request
        """
        try:
            # Handle both Dict and JsonRPCRequest objects
            if hasattr(request, 'method'):
                # JsonRPCRequest object
                method = request.method
                request_id = request.id
                params = request.params
            elif isinstance(request, dict):
                # Dictionary
                method = request.get('method')
                request_id = request.get('id')
                params = request.get('params')
            else:
                # Invalid request type
                self.errors_count += 1
                self.last_error = f"Invalid request type: {type(request)}"
                return request  # Return unchanged to avoid breaking the flow
            
            # Validate request has necessary fields
            if not method or not params:
                self.errors_count += 1
                self.last_error = "Request missing method or params"
                return request
            
            # Convert tools/execute to tools/call with appropriate parameter structure
            if method == "tools/execute":
                # Extract tool name and input parameters
                tool_name = params.get('name')
                tool_input = params.get('input')
                
                if not tool_name:
                    self.errors_count += 1
                    self.last_error = "tools/execute request missing 'name' in params"
                    return request
                
                logger.debug(f"Translating tools/execute to tools/call for tool: {tool_name}")
                
                # Create translated request
                self.translations_count += 1
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": tool_input or {}  # Handle None case
                    }
                }
            
            # Pass through other methods unchanged
            return request
            
        except Exception as e:
            self.errors_count += 1
            self.last_error = f"Error translating request: {str(e)}"
            logger.error(self.last_error)
            return request  # Return unchanged in case of error


class SliteIntegration:
    """Integration with Slite-MCP for XwAI FastMCP Server."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Slite integration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or slite_config
        self.enabled = self.config.get("enabled", False)
        self.proxy = None
        
        if self.enabled:
            host = self.config.get("host", "localhost")
            port = self.config.get("port", 8001)
            endpoint = self.config.get("endpoint", "/mcp")
            timeout = self.config.get("timeout", 30)
            api_key = self.config.get("api_key", "")
            
            self.base_url = f"http://{host}:{port}"
            self.sse_url = f"{self.base_url}/sse"
            self.client = SliteMCPClient(
                base_url=self.base_url,
                endpoint=endpoint,
                timeout=timeout,
                api_key=api_key
            )
            logger.info(f"Slite integration enabled with base URL: {self.base_url}")
        else:
            logger.info("Slite integration disabled")
    
    async def create_proxy(self) -> Optional[FastMCP]:
        """
        Create a FastMCP proxy for the Slite-MCP server.
        
        Returns:
            FastMCP proxy
        """
        if not self.enabled:
            logger.info("Slite integration disabled, skipping proxy creation")
            return None
        
        # Check server availability
        try:
            health = await self.client.check_health()
            if health.get("status") != "ok":
                logger.error(f"Slite-MCP health check failed: {health}")
                return None
        except Exception as e:
            logger.error(f"Error checking Slite-MCP server health: {str(e)}")
            return None
        
        try:
            # Create SSE transport for the Slite-MCP server
            transport = SseClientTransport(url=self.sse_url)
            client = Client(transport=transport)
            
            # Add method translator
            translator = SliteMethodTranslator()
            client.add_request_interceptor(translator)
            
            # Create FastMCP proxy
            self.proxy = await FastMCP.from_client(
                client,
                name="Slite Knowledge Base"
            )
            
            logger.info("Created FastMCP proxy for Slite-MCP server")
            return self.proxy
        except Exception as e:
            logger.error(f"Error creating Slite-MCP proxy: {str(e)}")
            return None
    
    async def initialize(self) -> bool:
        """
        Initialize the Slite integration.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if not self.enabled:
            logger.info("Slite integration disabled, skipping initialization")
            return False
        
        try:
            # Initialize direct client
            await self.client.initialize()
            
            # Create proxy
            proxy = await self.create_proxy()
            if not proxy:
                logger.error("Failed to create Slite-MCP proxy")
                return False
            
            # Test tool listing
            tools = await self.client.list_tools()
            logger.info(f"Available Slite tools: {[t.get('name') for t in tools]}")
            
            return True
        except Exception as e:
            logger.error(f"Error initializing Slite integration: {str(e)}")
            return False
    
    def register_fastmcp_tools(self, mcp: FastMCP):
        """
        Register Slite tools with FastMCP.
        
        Args:
            mcp: FastMCP server instance
        """
        if not self.enabled:
            logger.info("Slite integration disabled, skipping tool registration")
            return
        
        @mcp.tool()
        async def search_slite(query: str, limit: int = 5, ctx: Optional[Context] = None) -> Dict[str, Any]:
            """
            Search for notes in the Slite knowledge base.
            
            Args:
                query: Search query
                limit: Maximum number of results
                ctx: Optional context
                
            Returns:
                Search results
            """
            if ctx:
                await ctx.info(f"Searching Slite: {query}")
            
            try:
                result = await self.client.search_notes(query, limit)
                return result
            except Exception as e:
                error_msg = f"Error searching Slite: {str(e)}"
                logger.error(error_msg)
                if ctx:
                    await ctx.error(error_msg)
                return {"error": error_msg}
        
        @mcp.tool()
        async def slite_ask(question: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
            """
            Ask a question to the Slite knowledge base.
            
            Args:
                question: Question to ask
                ctx: Optional context
                
            Returns:
                Answer with sources
            """
            if ctx:
                await ctx.info(f"Asking Slite: {question}")
            
            try:
                result = await self.client.ask_slite(question)
                return result
            except Exception as e:
                error_msg = f"Error asking Slite: {str(e)}"
                logger.error(error_msg)
                if ctx:
                    await ctx.error(error_msg)
                return {"error": error_msg}
        
        @mcp.tool()
        async def get_slite_note(note_id: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
            """
            Get a note from Slite by ID.
            
            Args:
                note_id: Note ID
                ctx: Optional context
                
            Returns:
                Note details
            """
            if ctx:
                await ctx.info(f"Getting Slite note: {note_id}")
            
            try:
                result = await self.client.get_note(note_id)
                return result
            except Exception as e:
                error_msg = f"Error getting Slite note: {str(e)}"
                logger.error(error_msg)
                if ctx:
                    await ctx.error(error_msg)
                return {"error": error_msg}
        
        @mcp.tool()
        async def get_slite_status() -> Dict[str, Any]:
            """
            Get status of the Slite integration.
            
            Returns:
                Slite integration status
            """
            try:
                health = await self.client.check_health()
                return {
                    "enabled": self.enabled,
                    "connected": health.get("status") == "ok",
                    "url": self.base_url,
                    "tools": [t.get("name") for t in await self.client.list_tools()]
                }
            except Exception as e:
                logger.error(f"Error getting Slite status: {str(e)}")
                return {
                    "enabled": self.enabled,
                    "connected": False,
                    "error": str(e)
                }
        
        logger.info("Registered Slite tools with FastMCP")


# Direct function for external use
async def slite_ask(question: str) -> Dict[str, Any]:
    """
    Ask a question to the Slite knowledge base.
    
    Args:
        question: Question to ask
        
    Returns:
        Answer with sources
    """
    # Create client
    client = SliteMCPClient(
        base_url=f"http://{slite_config['host']}:{slite_config['port']}",
        endpoint=slite_config['endpoint'],
        timeout=slite_config['timeout'],
        api_key=slite_config['api_key']
    )
    
    # Initialize
    try:
        await client.initialize()
    except Exception as e:
        logger.error(f"Error initializing Slite client: {str(e)}")
        return {"error": str(e)}
    
    # Ask question
    try:
        result = await client.ask_slite(question)
        return result
    except Exception as e:
        logger.error(f"Error asking Slite: {str(e)}")
        return {"error": str(e)}


# Register tools with FastMCP
def register_slite_tools(mcp: FastMCP):
    """
    Register Slite tools with FastMCP.
    
    Args:
        mcp: FastMCP server instance
    """
    # Create integration
    integration = SliteIntegration()
    
    # Register tools
    integration.register_fastmcp_tools(mcp)


# Direct test function
async def test_slite():
    """Test Slite integration directly."""
    question = input("Enter your question for Slite: ")
    
    result = await slite_ask(question)
    print(f"\nSlite result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(test_slite())