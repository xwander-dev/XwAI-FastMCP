"""
Result processor for FastMCP 2.2.7 responses.

This module provides utilities for processing and extracting information
from FastMCP 2.2.7 responses, which can come in various formats.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union

# Setup logging
logger = logging.getLogger("result-processor")

class ResultProcessor:
    """Process results from FastMCP 2.2.7."""
    
    @staticmethod
    def extract_text(result: Any) -> Optional[str]:
        """
        Extract text from FastMCP 2.2.7 content objects.
        
        Args:
            result: FastMCP result, which could be in various formats
            
        Returns:
            Extracted text or None if no text could be extracted
        """
        if result is None:
            return None
        
        # Handle string directly
        if isinstance(result, str):
            return result
        
        # Handle dictionary
        if isinstance(result, dict):
            # Check for 'content' key with list of items
            if "content" in result and isinstance(result["content"], list):
                text_parts = []
                for item in result["content"]:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                if text_parts:
                    return "".join(text_parts)
            
            # Check for 'content' key with string value
            if "content" in result and isinstance(result["content"], str):
                return result["content"]
            
            # Check for 'result' key
            if "result" in result:
                return ResultProcessor.extract_text(result["result"])
            
            # Check for 'text' key
            if "text" in result:
                return result["text"]
            
            # Fallback to JSON string representation
            return json.dumps(result)
        
        # Handle list
        if isinstance(result, list):
            # Check if list has dictionary items with 'type' and 'text' keys
            if all(isinstance(item, dict) and "type" in item for item in result):
                text_parts = []
                for item in result:
                    if item.get("type") == "text" and "text" in item:
                        text_parts.append(item["text"])
                if text_parts:
                    return "".join(text_parts)
            
            # Fallback to JSON string representation
            return json.dumps(result)
        
        # Fallback to string conversion
        return str(result)
    
    @staticmethod
    def to_dict(result: Any) -> Dict[str, Any]:
        """
        Convert result to a Python dictionary.
        
        Args:
            result: FastMCP result
            
        Returns:
            Dictionary representation of the result
        """
        if result is None:
            return {"error": "No result returned"}
        
        # Already a dictionary
        if isinstance(result, dict):
            return result
        
        # String that might be JSON
        if isinstance(result, str):
            try:
                # Try to parse as JSON
                return json.loads(result)
            except json.JSONDecodeError:
                # Plain string
                return {"result": result}
        
        # List
        if isinstance(result, list):
            # List of items with type and text
            if all(isinstance(item, dict) and "type" in item for item in result):
                text_parts = []
                for item in result:
                    if item.get("type") == "text" and "text" in item:
                        text_parts.append(item["text"])
                if text_parts:
                    return {"result": "".join(text_parts)}
            
            # Regular list
            return {"result": result}
        
        # Fallback
        return {"result": str(result)}
    
    @staticmethod
    def with_metadata(result: Any, **metadata) -> Dict[str, Any]:
        """
        Add metadata to result.
        
        Args:
            result: FastMCP result
            **metadata: Additional metadata to include
            
        Returns:
            Dictionary with result and metadata
        """
        result_dict = ResultProcessor.to_dict(result)
        result_dict["metadata"] = metadata
        return result_dict
    
    @staticmethod
    def process(result: Any) -> Dict[str, Any]:
        """
        Process result from FastMCP, handling various formats.
        
        Args:
            result: FastMCP result
            
        Returns:
            Processed result as a dictionary
        """
        try:
            # Handle null result
            if result is None:
                return {"error": "No result returned"}
            
            # Handle string result
            if isinstance(result, str):
                try:
                    # Try to parse as JSON
                    return json.loads(result)
                except json.JSONDecodeError:
                    # Plain string
                    return {"result": result}
            
            # Handle dictionary result
            if isinstance(result, dict):
                # Return a copy to avoid modifying the original
                return dict(result)
            
            # Handle list result
            if isinstance(result, list):
                # Check for content objects
                if all(isinstance(item, dict) and "type" in item for item in result):
                    text_parts = []
                    for item in result:
                        if item.get("type") == "text" and "text" in item:
                            text_parts.append(item["text"])
                    if text_parts:
                        return {"result": "".join(text_parts)}
                
                # Regular list
                return {"result": result}
            
            # Fallback
            return {"result": str(result)}
        
        except Exception as e:
            logger.error(f"Error processing result: {str(e)}")
            return {"error": f"Error processing result: {str(e)}"}
    
    @staticmethod
    def is_error(result: Any) -> bool:
        """
        Check if result indicates an error.
        
        Args:
            result: Processed result
            
        Returns:
            True if result indicates an error, False otherwise
        """
        if isinstance(result, dict):
            return "error" in result
        return False
    
    @staticmethod
    def get_error(result: Any) -> Optional[str]:
        """
        Get error message from result.
        
        Args:
            result: Processed result
            
        Returns:
            Error message or None if no error
        """
        if ResultProcessor.is_error(result):
            return result.get("error")
        return None