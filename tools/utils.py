"""
Utilities for XwAI FastMCP.

This module provides shared utility functions for the XwAI FastMCP implementation.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

logger = logging.getLogger("xwai-utils")

def load_env_file(env_file: Optional[str] = None) -> bool:
    """
    Load environment variables from .env file.
    
    Args:
        env_file: Path to .env file. If not provided, looks for standard locations.
        
    Returns:
        bool: True if environment variables were loaded, False otherwise.
    """
    # Priority for env files:
    # 1. Explicitly provided path
    # 2. /var/www/.env (global)
    # 3. .env (local)
    
    if not env_file and os.path.exists("/var/www/.env"):
        env_file = "/var/www/.env"
    
    if not env_file and os.path.exists(".env"):
        env_file = ".env"
        
    if env_file and os.path.exists(env_file):
        logger.info(f"Loading environment variables from {env_file}")
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                    
                try:
                    key, value = line.split("=", 1)
                    os.environ[key] = value
                except ValueError:
                    logger.warning(f"Invalid line in .env file: {line}")
                
        return True
    
    return False

def process_result(result: Any) -> Dict[str, Any]:
    """
    Process result from FastMCP 2.2.7, handling various formats.
    
    Args:
        result: Result from FastMCP call
        
    Returns:
        Dict with processed result
    """
    # Handle None result
    if result is None:
        return {"error": "No result returned"}
    
    # Extract text from FastMCP 2.2.7 content objects
    text_result = extract_text(result)
    
    # Try to parse as JSON
    if text_result and (text_result.startswith("{") or text_result.startswith("[")):
        try:
            return json.loads(text_result)
        except json.JSONDecodeError:
            # Not valid JSON, return as text
            return {"result": text_result}
    else:
        return {"result": text_result}

def extract_text(result: Any) -> Optional[str]:
    """
    Extract text from FastMCP 2.2.7 content objects.
    
    Args:
        result: Result from FastMCP call
        
    Returns:
        Extracted text or None
    """
    # Handle various FastMCP 2.2.7 response formats
    if result is None:
        return None
        
    # Use FastMCP's content_to_text if available
    try:
        from fastmcp import content_to_text
        return content_to_text(result)
    except ImportError:
        pass
    
    # Manual extraction
    if isinstance(result, str):
        return result
    elif isinstance(result, dict):
        # Handle dict with content field
        if "content" in result:
            return extract_text(result["content"])
        # Handle dict with text field
        elif "text" in result:
            return result["text"]
        # Handle dict with result field
        elif "result" in result:
            return extract_text(result["result"])
        else:
            # Return as JSON string
            return json.dumps(result)
    elif isinstance(result, list):
        # Handle list of content objects
        if all(isinstance(item, dict) and "type" in item and item.get("type") == "text" for item in result):
            return "".join(item.get("text", "") for item in result)
        # Handle list as array
        return json.dumps(result)
    else:
        # Convert to string as fallback
        return str(result)

def to_dict(result: Any) -> Dict[str, Any]:
    """
    Convert result to a Python dictionary.
    
    Args:
        result: Result from FastMCP call
        
    Returns:
        Dict with result
    """
    if result is None:
        return {"error": "No result returned"}
        
    if isinstance(result, dict):
        return result
    elif isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"result": result}
    elif isinstance(result, list):
        return {"result": result}
    else:
        return {"result": str(result)}