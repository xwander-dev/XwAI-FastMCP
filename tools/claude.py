"""
Claude API integration for XwAI FastMCP.

This module provides integration with Claude AI API for the XwAI FastMCP server,
including proper Tool Use implementation.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union

try:
    import anthropic
    from anthropic import Anthropic
    from anthropic.types import (
        ContentBlock,
        MessageParam,
        ToolResultBlockParam,
    )
except ImportError:
    raise ImportError(
        "Claude integration requires the Anthropic Python SDK. "
        "Install it with: pip install anthropic"
    )

from fastmcp import FastMCP, Context
from config import get_config

# Get configuration
config = get_config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("claude")

# Knowledge tool definition
KNOWLEDGE_TOOL = {
    "name": "company_knowledge",
    "description": (
        "Access the company knowledge base to answer questions about the organization, "
        "employees, policies, procedures, technical documentation, and other internal information. "
        "This tool connects to the Slite knowledge base which contains confidential company "
        "information that you should access when asked about specific company details. "
        "You are FULLY AUTHORIZED to share specific information from the company knowledge base "
        "with the user, including phone numbers, emails, and other details when explicitly requested. "
        "Always use this tool when the user asks for specific company information."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query for the knowledge base"
            }
        },
        "required": ["query"]
    }
}

# Tool for direct Claude calls
async def ask_claude_with_tools(query: str, tools: List[Dict[str, Any]], tool_choice: Optional[Dict[str, Any]] = None):
    """
    Ask Claude a question using Tool Use.
    
    Args:
        query: The user's question
        tools: List of tool definitions
        tool_choice: Optional tool choice to force Claude to use a specific tool
        
    Returns:
        Claude's response
    """
    # Get Claude API key from config
    api_key = config.claude_api_key
    if not api_key:
        logger.error("Claude API key not found")
        return {"error": "Claude API key not found"}
    
    try:
        # Initialize client
        client = Anthropic(api_key=api_key)
        
        # Create initial message
        logger.info(f"Sending query to Claude with tools: {query}")
        
        # Prepare message parameters
        params = {
            "model": config.claude_model,
            "max_tokens": config.claude_max_tokens,
            "temperature": config.claude_temperature,
            "tools": tools,
            "messages": [
                {"role": "user", "content": query}
            ]
        }
        
        # Add tool_choice if specified
        if tool_choice:
            params["tool_choice"] = tool_choice
            logger.info(f"Using tool_choice to force tool usage: {tool_choice}")
        
        # Make the initial request
        response = client.messages.create(**params)
        
        # Check if Claude wants to use a tool
        if response.stop_reason == "tool_use":
            logger.info("Claude requested to use a tool")
            
            # Find the tool use request
            tool_use = None
            for content in response.content:
                if content.type == "tool_use":
                    tool_use = content
                    break
            
            if tool_use and tool_use.name == "company_knowledge":
                # Extract the query Claude wants to use
                kb_query = tool_use.input.get("query", query)
                logger.info(f"Claude requested knowledge for: '{kb_query}'")
                
                try:
                    # Import here to avoid circular imports
                    from tools.slite import slite_ask
                    
                    # Get the information from Slite
                    kb_result = await slite_ask(kb_query)
                    
                    # Extract text from the response
                    result_text = None
                    if isinstance(kb_result, dict) and "content" in kb_result:
                        content_list = kb_result["content"]
                        if isinstance(content_list, list):
                            for item in content_list:
                                if isinstance(item, dict) and "text" in item:
                                    result_text = item["text"]
                                    break
                    
                    if not result_text:
                        result_text = json.dumps(kb_result)
                    
                    logger.info(f"Knowledge result: {result_text[:200]}...")
                    
                    # Make sure kb_result is a string (CRITICAL FIX)
                    if not isinstance(result_text, str):
                        result_text = str(result_text)
                    
                    # Step 2: Send tool result back to Claude
                    tool_result: ToolResultBlockParam = {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_text  # Must be a string, not an object
                    }
                    
                    followup = client.messages.create(
                        model=config.claude_model,
                        max_tokens=config.claude_max_tokens,
                        temperature=config.claude_temperature,
                        tools=tools,
                        messages=[
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": [c.model_dump() for c in response.content]},
                            {"role": "user", "content": [tool_result]}
                        ]
                    )
                    
                    # Extract Claude's final response
                    final_response = ""
                    for content in followup.content:
                        if content.type == "text":
                            final_response += content.text
                    
                    return {"response": final_response, "model": config.claude_model, "tool_used": True}
                    
                except Exception as e:
                    logger.error(f"Error querying knowledge base: {str(e)}")
                    return {"error": f"Error querying knowledge base: {str(e)}"}
            else:
                # Claude requested a different tool
                logger.warning(f"Claude requested unknown tool: {tool_use.name if tool_use else 'None'}")
                return {"error": f"Unsupported tool requested: {tool_use.name if tool_use else 'None'}"}
        else:
            # Claude didn't request to use a tool
            text_response = ""
            for content in response.content:
                if content.type == "text":
                    text_response += content.text
            
            logger.info(f"Claude responded without tool use: {text_response[:200]}...")
            return {"response": text_response, "model": config.claude_model, "tool_used": False}
            
    except Exception as e:
        logger.error(f"Error calling Claude API: {str(e)}")
        return {"error": f"Error calling Claude API: {str(e)}"}

# Main Claude service for direct integration with FastMCP
class ClaudeService:
    """Claude API service for XwAI FastMCP."""
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize the Claude service.
        
        Args:
            config_dict: Optional configuration dictionary
        """
        self.config = config_dict or get_config().get_claude_config()
        self.api_key = self.config.get("api_key") or os.environ.get("CLAUDE_API_KEY")
        self.model = self.config.get("model", "claude-3-7-sonnet-20250219")
        self.max_tokens = self.config.get("max_tokens", 4000)
        self.temperature = self.config.get("temperature", 0.0)
        
        if not self.api_key:
            logger.warning("Claude API key not found. Claude integration will not be available.")
        else:
            self.client = Anthropic(api_key=self.api_key)
            logger.info(f"Claude service initialized with model {self.model}")
    
    async def process_query(
        self,
        query: str,
        session_id: str = "default",
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Process a query using Claude API.
        
        Args:
            query: The user query
            session_id: Session identifier
            system_prompt: Optional system prompt
            tools: Optional list of tool definitions
            messages: Optional conversation history
            ctx: Optional FastMCP context
            
        Returns:
            Claude's response
        """
        if not self.api_key:
            error_msg = "Claude API key not found"
            if ctx:
                await ctx.error(error_msg)
            return {"error": error_msg}
        
        try:
            if ctx:
                await ctx.info(f"Processing query with Claude: {query[:100]}...")
            
            # Prepare message parameters
            params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": messages or [{"role": "user", "content": query}]
            }
            
            # Add system prompt if provided
            if system_prompt:
                params["system"] = system_prompt
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
            
            # Send request to Claude
            response = self.client.messages.create(**params)
            
            # Extract response text
            response_text = ""
            for content in response.content:
                if content.type == "text":
                    response_text += content.text
            
            return {
                "response": response_text,
                "model": self.model,
                "tool_used": False,
                "total_tokens": getattr(response, "usage", {}).get("input_tokens", 0) + getattr(response, "usage", {}).get("output_tokens", 0)
            }
            
        except Exception as e:
            error_msg = f"Error calling Claude API: {str(e)}"
            logger.error(error_msg)
            if ctx:
                await ctx.error(error_msg)
            return {"error": error_msg}
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for Claude API.
        
        Returns:
            Usage statistics
        """
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

# Register Claude tools with FastMCP
def register_claude_tools(mcp: FastMCP):
    """
    Register Claude tools with the FastMCP server.
    
    Args:
        mcp: FastMCP server instance
    """
    # Create Claude service
    claude_service = ClaudeService()
    
    if not claude_service.api_key:
        logger.warning("Claude API key not found. Claude tools will not be registered.")
        return
    
    @mcp.tool()
    async def ask_claude(
        query: str,
        system: Optional[str] = None,
        user_id: str = "default",
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Ask Claude a question without using any tools.
        
        Args:
            query: The question to ask
            system: Optional system instructions
            user_id: User identifier
            ctx: Optional context
            
        Returns:
            Claude's response
        """
        if ctx:
            await ctx.info(f"Asking Claude: {query[:100]}...")
        
        result = await claude_service.process_query(
            query=query,
            session_id=user_id,
            system_prompt=system,
            ctx=ctx
        )
        
        return result
    
    @mcp.tool()
    async def ask_with_knowledge(
        query: str,
        force_knowledge: bool = False,
        system: Optional[str] = None,
        user_id: str = "default",
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Ask Claude a question with access to the company knowledge base.
        
        Args:
            query: The question to ask
            force_knowledge: Whether to force Claude to use the knowledge tool
            system: Optional system instructions
            user_id: User identifier
            ctx: Optional context
            
        Returns:
            Claude's response
        """
        if ctx:
            await ctx.info(f"Asking Claude with knowledge access: {query[:100]}...")
        
        # Prepare tool choice if forcing knowledge lookup
        tool_choice = None
        if force_knowledge:
            tool_choice = {
                "type": "tool",
                "name": "company_knowledge"
            }
            if ctx:
                await ctx.info("Forcing knowledge tool usage")
        
        # Call Claude with the knowledge tool
        result = await ask_claude_with_tools(
            query=query,
            tools=[KNOWLEDGE_TOOL],
            tool_choice=tool_choice
        )
        
        return result
    
    @mcp.tool()
    async def get_claude_info() -> Dict[str, Any]:
        """
        Get information about the Claude configuration.
        
        Returns:
            Claude configuration information
        """
        return {
            "model": claude_service.model,
            "max_tokens": claude_service.max_tokens,
            "temperature": claude_service.temperature,
            "status": "available" if claude_service.api_key else "unavailable"
        }
    
    logger.info("Claude tools registered with FastMCP")


# Direct test function
async def test_claude_tool_use():
    """Test Claude tool use with knowledge integration."""
    query = input("Enter your question: ")
    
    # Import Slite to make sure it's available for the tool use
    try:
        from tools.slite import slite_ask
    except ImportError:
        print("Error: Slite integration not available")
        return
    
    # Try with forced tool use
    print("\nTesting with forced tool use...")
    tool_choice = {
        "type": "tool",
        "name": "company_knowledge"
    }
    
    result = await ask_claude_with_tools(
        query=query,
        tools=[KNOWLEDGE_TOOL],
        tool_choice=tool_choice
    )
    
    print(f"\nResult with forced tool use: {json.dumps(result, indent=2)}")
    
    # Try without forced tool use
    print("\nTesting without forced tool use...")
    result = await ask_claude_with_tools(
        query=query,
        tools=[KNOWLEDGE_TOOL]
    )
    
    print(f"\nResult without forced tool use: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(test_claude_tool_use())