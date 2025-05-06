"""
Configuration system for XwAI FastMCP.

This module provides a Pydantic-based configuration system for the XwAI FastMCP
implementation, supporting environment variables, .env files, and defaults.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from pydantic import BaseSettings, Field, validator

from tools.utils import load_env_file


class XwAIConfig(BaseSettings):
    """Configuration for XwAI FastMCP system."""
    
    # Server settings
    server_name: str = "XwAI FastMCP Server"
    host: str = "0.0.0.0"
    port: int = 9001
    log_level: str = "INFO"
    
    # API keys
    claude_api_key: str = Field("", env="CLAUDE_API_KEY")
    slite_api_key: str = Field("", env="SLITE_API_KEY")
    
    # Slite MCP settings
    slite_mcp_enabled: bool = Field(True, env="SLITE_MCP_ENABLED")
    slite_mcp_host: str = Field("localhost", env="SLITE_MCP_HOST")
    slite_mcp_port: int = Field(8001, env="SLITE_MCP_PORT")
    slite_mcp_endpoint: str = Field("/mcp", env="SLITE_MCP_ENDPOINT")
    slite_mcp_timeout: int = Field(30, env="SLITE_MCP_TIMEOUT")
    
    # Claude settings
    claude_model: str = Field("claude-3-7-sonnet-20250219", env="CLAUDE_MODEL")
    claude_max_tokens: int = Field(4000, env="CLAUDE_MAX_TOKENS")
    claude_temperature: float = Field(0.0, env="CLAUDE_TEMPERATURE")
    
    # CLI settings
    history_file: str = Field("~/.xwai_history", env="XWAI_HISTORY_FILE")
    auto_knowledge: bool = Field(True, env="XWAI_AUTO_KNOWLEDGE")
    
    # Paths
    data_dir: str = Field("data", env="XWAI_DATA_DIR")
    
    class Config:
        """Pydantic config"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("data_dir")
    def create_data_dir(cls, v):
        """Create data directory if it doesn't exist"""
        path = Path(v).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    
    @validator("history_file")
    def expand_history_file(cls, v):
        """Expand user path in history file"""
        return str(Path(v).expanduser().resolve())
    
    def get_slite_config(self) -> Dict[str, Any]:
        """Get Slite MCP configuration dictionary"""
        return {
            "enabled": self.slite_mcp_enabled,
            "host": self.slite_mcp_host,
            "port": self.slite_mcp_port,
            "endpoint": self.slite_mcp_endpoint,
            "timeout": self.slite_mcp_timeout,
            "api_key": self.slite_api_key
        }
    
    def get_claude_config(self) -> Dict[str, Any]:
        """Get Claude configuration dictionary"""
        return {
            "api_key": self.claude_api_key,
            "model": self.claude_model,
            "max_tokens": self.claude_max_tokens,
            "temperature": self.claude_temperature
        }


# Singleton instance pattern
_config_instance = None

def get_config(env_file: Optional[str] = None) -> XwAIConfig:
    """
    Get the XwAIConfig singleton instance.
    
    Args:
        env_file: Optional path to .env file. If provided, environment
                 variables will be loaded from this file.
    
    Returns:
        XwAIConfig instance
    """
    global _config_instance
    
    # Load environment variables if env_file is provided
    if env_file:
        load_env_file(env_file)
    
    # Create singleton instance if it doesn't exist
    if _config_instance is None:
        _config_instance = XwAIConfig()
    
    return _config_instance


# Export singleton instance for easy import
config = get_config()