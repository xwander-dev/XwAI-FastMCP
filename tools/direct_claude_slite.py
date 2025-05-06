#!/usr/bin/env python3
"""
Direct Claude Tool Use with Slite Integration.

This standalone module demonstrates the proper use of Claude's Tool Use capability
with Slite knowledge base integration, serving as both a reference implementation
and a usable utility.
"""

import os
import json
import asyncio
import logging
import argparse
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

# Local imports (utils and slite)
try:
    from tools.utils import load_env_file
    from tools.slite import slite_ask
except ImportError:
    # Fallback for standalone usage
    from utils import load_env_file
    
    # Dummy slite_ask for standalone usage
    async def slite_ask(question: str) -> Dict[str, Any]:
        """
        Dummy function for standalone usage.
        In a real implementation, this would query the Slite knowledge base.
        """
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Mock answer for question: {question}\n\nThis is a placeholder response since Slite integration is not available."
                }
            ]
        }

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("claude-slite")

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

async def query_knowledge_base(query: str) -> str:
    """
    Query the Slite knowledge base.
    
    Args:
        query: The search query
        
    Returns:
        Formatted knowledge base response as a string
    """
    logger.info(f"Querying knowledge base: {query}")
    
    try:
        # Call Slite
        result = await slite_ask(query)
        logger.info(f"Slite result: {json.dumps(result)[:200]}...")
        
        # Extract the content from Slite's response
        content = None
        if isinstance(result, dict) and "content" in result:
            content_list = result["content"]
            if isinstance(content_list, list):
                for item in content_list:
                    if isinstance(item, dict) and "text" in item:
                        content = item["text"]
                        break
        
        if content:
            logger.info(f"Found content: {content[:100]}...")
            return content
        else:
            logger.warning("No content found in Slite response")
            # Implement proper Error handling by returning a string
            return json.dumps(result)
            
    except Exception as e:
        logger.error(f"Error querying knowledge base: {str(e)}")
        # Return error as string (CRITICAL: must be a string)
        return f"Error retrieving knowledge: {str(e)}"

async def get_claude_response(
    query: str,
    model: str = "claude-3-7-sonnet-20250219",
    max_tokens: int = 4000,
    temperature: float = 0.0,
    force_tool_use: bool = False,
    api_key: Optional[str] = None,
    show_reasoning: bool = False
) -> Dict[str, Any]:
    """
    Get a response from Claude using the Tool Use pattern with Slite knowledge base.
    
    Args:
        query: The user's question
        model: Claude model to use
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        force_tool_use: Whether to force Claude to use the knowledge tool
        api_key: Claude API key (falls back to environment variable)
        show_reasoning: Whether to include Claude's reasoning in the response
        
    Returns:
        Claude's response with metadata
    """
    # Load environment variables
    load_env_file()
    
    # Get API key
    api_key = api_key or os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("Claude API key not found in environment variables")
        return {"error": "Claude API key not found"}
    
    # Test query
    logger.info(f"Processing query: '{query}'")
    
    try:
        # Create Claude client
        client = Anthropic(api_key=api_key)
        
        # Prepare parameters for API call
        params = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tools": [KNOWLEDGE_TOOL],
            "messages": [
                {"role": "user", "content": query}
            ]
        }
        
        # Add tool_choice if forcing tool use
        if force_tool_use:
            params["tool_choice"] = {
                "type": "tool",
                "name": "company_knowledge"
            }
            logger.info("Forcing knowledge tool usage")
        
        # Step 1: First message with Claude (asking for tool use)
        logger.info("Sending initial request to Claude")
        response = client.messages.create(**params)
        
        logger.info(f"Initial response stop reason: {response.stop_reason}")
        
        # Process tool request if Claude wants to use the tool
        if response.stop_reason == "tool_use":
            # Find the tool use request
            tool_use = None
            tool_use_id = None
            
            for content in response.content:
                if content.type == "tool_use":
                    tool_use = content
                    tool_use_id = content.id
                    break
            
            if tool_use and tool_use.name == "company_knowledge":
                # Extract the query Claude wants to use
                kb_query = tool_use.input.get("query", query)
                logger.info(f"Claude requested knowledge for: '{kb_query}'")
                
                # Get the information from Slite
                kb_result = await query_knowledge_base(kb_query)
                logger.info(f"Knowledge result: {kb_result[:200] if isinstance(kb_result, str) else str(kb_result)[:200]}...")
                
                # Make sure kb_result is a string (CRITICAL FIX)
                if not isinstance(kb_result, str):
                    kb_result = str(kb_result)
                
                # Step 2: Send tool result back to Claude
                tool_result: ToolResultBlockParam = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": kb_result  # Must be a string
                }
                
                logger.info("Sending tool result back to Claude")
                followup = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=[KNOWLEDGE_TOOL],
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
                
                logger.info(f"Claude's final response: {final_response[:200]}...")
                
                result = {
                    "response": final_response,
                    "model": model,
                    "tool_used": True,
                    "knowledge_query": kb_query
                }
                
                # Include reasoning if requested
                if show_reasoning:
                    # Extract Claude's reasoning from the first response
                    reasoning = ""
                    for content in response.content:
                        if content.type == "text":
                            reasoning += content.text
                    
                    result["reasoning"] = reasoning
                    result["knowledge_result"] = kb_result
                
                return result
            else:
                # Claude requested a different tool or none at all
                logger.warning(f"Claude requested unknown tool: {tool_use.name if tool_use else 'None'}")
                error_msg = f"Unsupported tool requested: {tool_use.name if tool_use else 'None'}"
                return {"error": error_msg}
        else:
            # Claude didn't request to use a tool
            text_response = ""
            for content in response.content:
                if content.type == "text":
                    text_response += content.text
            
            logger.info(f"Claude responded without tool use: {text_response[:200]}...")
            
            return {
                "response": text_response,
                "model": model,
                "tool_used": False
            }
    except Exception as e:
        logger.error(f"Error calling Claude API: {str(e)}")
        return {"error": f"Error calling Claude API: {str(e)}"}

async def main():
    """Command-line interface for direct Claude Tool Use with Slite."""
    parser = argparse.ArgumentParser(description="Query Claude with Slite knowledge access")
    parser.add_argument("query", help="Question to ask Claude")
    parser.add_argument("--model", default="claude-3-7-sonnet-20250219", help="Claude model to use")
    parser.add_argument("--max-tokens", type=int, default=4000, help="Maximum tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature for generation")
    parser.add_argument("--force", action="store_true", help="Force Claude to use the knowledge tool")
    parser.add_argument("--show-reasoning", action="store_true", help="Show Claude's reasoning")
    parser.add_argument("--env-file", help="Path to .env file with API keys")
    
    args = parser.parse_args()
    
    if args.env_file:
        load_env_file(args.env_file)
    
    result = await get_claude_response(
        query=args.query,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        force_tool_use=args.force,
        show_reasoning=args.show_reasoning
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1
    
    # Print tool usage information
    if result.get("tool_used"):
        print("\n" + "=" * 80)
        print(f"Knowledge Query: {result.get('knowledge_query')}")
        print("=" * 80 + "\n")
    
    # Print reasoning if requested
    if args.show_reasoning and "reasoning" in result:
        print("\n" + "=" * 80)
        print("Claude's Reasoning:")
        print("=" * 80)
        print(result["reasoning"])
        print("\n" + "=" * 80)
        print("Knowledge Result:")
        print("=" * 80)
        print(result["knowledge_result"])
        print("=" * 80 + "\n")
    
    # Print response
    print("\n" + "=" * 80)
    print("Claude's Response:")
    print("=" * 80)
    print(result["response"])
    print("=" * 80 + "\n")
    
    # Print metadata
    print(f"Model: {result.get('model')}")
    print(f"Tool Used: {result.get('tool_used')}")
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())