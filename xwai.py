#!/usr/bin/env python3
"""
XwAI Interactive CLI

A command-line interface for interacting with the XwAI FastMCP server
with features like conversation history, auto-completion, and Claude integration.
"""

import os
import sys
import json
import logging
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style
except ImportError:
    raise ImportError(
        "Interactive CLI requires prompt_toolkit. "
        "Install it with: pip install prompt_toolkit"
    )

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.syntax import Syntax
except ImportError:
    raise ImportError(
        "Interactive CLI requires rich for formatting. "
        "Install it with: pip install rich"
    )

# Import XwAI components
from config import config, get_config
from result_processor import ResultProcessor
from client import XwAIClient
from tools.utils import load_env_file
from tools.direct_claude_slite import get_claude_response

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("xwai-cli")

# Rich console for formatted output
console = Console()

class XwAIInteractiveCLI:
    """Interactive CLI for XwAI FastMCP."""
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        history_file: Optional[str] = None,
        auto_knowledge: bool = True,
        show_reasoning: bool = False,
        verbose: bool = False
    ):
        """
        Initialize the interactive CLI.
        
        Args:
            server_url: Optional server URL
            history_file: Optional history file path
            auto_knowledge: Whether to automatically detect knowledge queries
            show_reasoning: Whether to show Claude's reasoning
            verbose: Whether to show verbose output
        """
        # Load environment variables
        load_env_file()
        
        # Configuration
        self.server_url = server_url or f"http://{config.host}:{config.port}/sse"
        self.history_file = history_file or config.history_file
        self.auto_knowledge = auto_knowledge
        self.show_reasoning = show_reasoning
        self.verbose = verbose
        
        # Create client
        self.client = XwAIClient(self.server_url)
        # Also store server_url in the client object for the completer
        self.client.server_url = self.server_url
        
        # Create result processor
        self.result_processor = ResultProcessor()
        
        # Create prompt session with history
        history_path = Path(self.history_file).expanduser()
        history_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.command_completer = WordCompleter([
            # Basic commands
            "help", "exit", "quit", "clear", "tools", "status", "config",
            # Knowledge commands
            "?", "!",
            # Special prefixes
            "/", "@"
        ], ignore_case=True)
        
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.command_completer,
            style=Style.from_dict({
                "prompt": "ansiblue bold",
                "query": "ansiyellow"
            })
        )
        
        # Display welcome message
        console.print(f"[bold cyan]XwAI Interactive CLI[/bold cyan]")
        console.print(f"[dim]Server: {self.server_url}[/dim]")
        console.print(f"[dim]Type 'help' for available commands[/dim]")
    
    async def update_completer(self):
        """Update command completer with available tools."""
        try:
            # Connect to server
            mcp, tools = await self.client.connect()
            if not mcp:
                logger.error("Failed to connect to server")
                return
            
            # Extract tool names
            tool_names = [t.name for t in tools]
            logger.info(f"Found {len(tool_names)} tools: {', '.join(tool_names)}")
            
            # Create new completer
            self.command_completer = WordCompleter(
                [
                    # Basic commands
                    "help", "exit", "quit", "clear", "tools", "status", "config",
                    # Knowledge commands
                    "?", "!",
                    # Special prefixes
                    "/", "@",
                    # Tool names
                    *tool_names
                ],
                ignore_case=True
            )
            
            # Update session completer
            self.session.completer = self.command_completer
            
        except Exception as e:
            logger.error(f"Error updating completer: {str(e)}")
    
    async def execute_command(self, command: str) -> bool:
        """
        Execute a command.
        
        Args:
            command: Command to execute
            
        Returns:
            True if should continue, False if should exit
        """
        if not command.strip():
            return True
        
        # Handle exit commands
        if command.lower() in ["exit", "quit"]:
            return False
        
        # Handle help command
        if command.lower() == "help":
            self.display_help()
            return True
        
        # Handle clear command
        if command.lower() == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            return True
        
        # Handle tools command
        if command.lower() == "tools":
            await self.list_tools()
            return True
        
        # Handle status command
        if command.lower() == "status":
            await self.check_status()
            return True
        
        # Handle config command
        if command.lower() == "config":
            self.display_config()
            return True
        
        # Handle knowledge query (prefixed with ?)
        if command.startswith("?"):
            query = command[1:].strip()
            if query:
                await self.execute_knowledge_query(query)
            return True
        
        # Handle forced knowledge query (prefixed with !)
        if command.startswith("!"):
            query = command[1:].strip()
            if query:
                await self.execute_knowledge_query(query, force=True)
            return True
        
        # Handle regular tool execution or conversation
        await self.process_input(command)
        return True
    
    async def list_tools(self):
        """List available tools on the server."""
        try:
            # Connect to server
            mcp, tools = await self.client.connect()
            if not mcp:
                console.print("[bold red]Failed to connect to server[/bold red]")
                return
            
            # Display tools
            console.print("[bold cyan]Available Tools:[/bold cyan]")
            for tool in tools:
                console.print(f"[bold]{tool.name}[/bold]: {tool.description}")
            
        except Exception as e:
            console.print(f"[bold red]Error listing tools: {str(e)}[/bold red]")
    
    async def check_status(self):
        """Check server status."""
        try:
            # Connect to server
            mcp, tools = await self.client.connect()
            if not mcp:
                console.print("[bold red]Failed to connect to server[/bold red]")
                return
            
            # Call server_info tool
            result = await self.client.call_tool("get_server_info")
            processed = self.result_processor.process(result)
            
            # Check for error
            if self.result_processor.is_error(processed):
                console.print(f"[bold red]Error: {processed.get('error')}[/bold red]")
                return
            
            # Display status
            console.print("[bold cyan]Server Status:[/bold cyan]")
            server_info = processed.get("result", {})
            if isinstance(server_info, dict):
                for key, value in server_info.items():
                    if isinstance(value, list):
                        console.print(f"[bold]{key}[/bold]: {', '.join(value)}")
                    else:
                        console.print(f"[bold]{key}[/bold]: {value}")
            else:
                console.print(str(server_info))
            
        except Exception as e:
            console.print(f"[bold red]Error checking status: {str(e)}[/bold red]")
    
    def display_config(self):
        """Display current configuration."""
        console.print("[bold cyan]Configuration:[/bold cyan]")
        console.print(f"[bold]Server URL[/bold]: {self.server_url}")
        console.print(f"[bold]History File[/bold]: {self.history_file}")
        console.print(f"[bold]Auto Knowledge[/bold]: {self.auto_knowledge}")
        console.print(f"[bold]Show Reasoning[/bold]: {self.show_reasoning}")
        console.print(f"[bold]Verbose Mode[/bold]: {self.verbose}")
        console.print(f"[bold]Claude Model[/bold]: {config.claude_model}")
        console.print(f"[bold]Claude Max Tokens[/bold]: {config.claude_max_tokens}")
    
    def display_help(self):
        """Display help information."""
        help_text = """
# XwAI Interactive CLI Help

## Basic Commands
- `help`: Display this help message
- `exit` or `quit`: Exit the CLI
- `clear`: Clear the terminal screen
- `tools`: List available tools
- `status`: Check server status
- `config`: Display current configuration

## Special Queries
- `?query`: Execute a knowledge query (auto-detects whether to use knowledge base)
- `!query`: Force a knowledge query (always uses knowledge base)

## Tool Execution
- `tool_name param=value`: Execute a specific tool with parameters
- For multiple parameters, use spaces: `tool_name param1=value1 param2=value2`

## Examples
- `?what is joni's phone number`: Query Slite knowledge base
- `!what is the FOTA url`: Force knowledge base query
- `ask_claude query="What is FastMCP?"`: Execute Claude tool directly
- """
        
        # Display as markdown with rich
        md = Markdown(help_text)
        console.print(md)
    
    async def execute_knowledge_query(self, query: str, force: bool = False):
        """
        Execute a knowledge query.
        
        Args:
            query: Query to execute
            force: Whether to force knowledge tool usage
        """
        console.print(f"[dim]Executing {'forced ' if force else ''}knowledge query: {query}[/dim]")
        
        try:
            # Get response from Claude with knowledge tool
            result = await get_claude_response(
                query=query,
                model=config.claude_model,
                max_tokens=config.claude_max_tokens,
                temperature=config.claude_temperature,
                force_tool_use=force,
                show_reasoning=self.show_reasoning
            )
            
            # Check for error
            if "error" in result:
                console.print(f"[bold red]Error: {result['error']}[/bold red]")
                return
            
            # Display meta
            if self.verbose:
                console.print(f"[dim]Model: {result.get('model')}[/dim]")
                console.print(f"[dim]Tool Used: {result.get('tool_used')}[/dim]")
                
                if result.get('tool_used') and result.get('knowledge_query'):
                    console.print(f"[dim]Knowledge Query: {result.get('knowledge_query')}[/dim]")
            
            # Display reasoning if requested
            if self.show_reasoning and "reasoning" in result:
                console.print(Panel(
                    result["reasoning"],
                    title="Claude's Reasoning",
                    border_style="yellow"
                ))
                
                if "knowledge_result" in result:
                    console.print(Panel(
                        result["knowledge_result"],
                        title="Knowledge Result",
                        border_style="green"
                    ))
            
            # Display response
            console.print("\n" + result["response"] + "\n")
            
        except Exception as e:
            console.print(f"[bold red]Error executing knowledge query: {str(e)}[/bold red]")
    
    async def process_input(self, input_text: str):
        """
        Process user input.
        
        Args:
            input_text: User input
        """
        # Check if input looks like a command
        if " " in input_text and "=" in input_text:
            # Try to parse as tool execution
            parts = input_text.split(" ", 1)
            tool_name = parts[0]
            param_text = parts[1]
            
            # Parse parameters
            params = {}
            param_items = param_text.split(" ")
            for item in param_items:
                if "=" in item:
                    key, value = item.split("=", 1)
                    # Try to parse value as JSON
                    try:
                        params[key] = json.loads(value)
                    except:
                        params[key] = value
            
            # Execute tool
            await self.execute_tool(tool_name, params)
        elif self.auto_knowledge:
            # Try as a conversation/knowledge query
            await self.execute_knowledge_query(input_text)
        else:
            # Try to send to Claude directly
            await self.execute_tool("ask_claude", {"query": input_text})
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any]):
        """
        Execute a specific tool.
        
        Args:
            tool_name: Tool name
            params: Tool parameters
        """
        try:
            console.print(f"[dim]Executing tool: {tool_name} with params: {params}[/dim]")
            
            # Call tool
            result = await self.client.call_tool(tool_name, **params)
            processed = self.result_processor.process(result)
            
            # Check for error
            if self.result_processor.is_error(processed):
                console.print(f"[bold red]Error: {processed.get('error')}[/bold red]")
                return
            
            # Display result
            if "response" in processed:
                # Claude/conversation response
                console.print("\n" + processed["response"] + "\n")
            elif "result" in processed:
                result = processed["result"]
                
                # Handle different result types
                if isinstance(result, str) and result.startswith("{") and result.endswith("}"):
                    # Try to parse JSON
                    try:
                        json_result = json.loads(result)
                        console.print(json.dumps(json_result, indent=2))
                    except:
                        console.print(result)
                elif isinstance(result, dict) or isinstance(result, list):
                    # Pretty print JSON
                    console.print(json.dumps(result, indent=2))
                else:
                    # Plain text
                    console.print(result)
            else:
                # Generic result
                console.print(processed)
            
        except Exception as e:
            console.print(f"[bold red]Error executing tool: {str(e)}[/bold red]")
    
    async def run(self):
        """Run the interactive CLI."""
        # Try to connect and update completer
        await self.update_completer()
        
        # Main loop
        while True:
            try:
                # Get input
                command = await self.session.prompt_async(HTML("<ansiblue>XwAI></ansiblue> "))
                
                # Execute command
                should_continue = await self.execute_command(command)
                if not should_continue:
                    break
                
            except KeyboardInterrupt:
                console.print("\n[bold yellow]KeyboardInterrupt: Use 'exit' to quit[/bold yellow]")
            except EOFError:
                console.print("\n[bold yellow]EOF: Exiting[/bold yellow]")
                break
            except Exception as e:
                console.print(f"[bold red]Error: {str(e)}[/bold red]")

async def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="XwAI Interactive CLI")
    parser.add_argument("--server", help="Server URL (default: from config)")
    parser.add_argument("--history", help="History file path (default: from config)")
    parser.add_argument("--auto-knowledge", action="store_true", default=True, help="Auto-detect knowledge queries")
    parser.add_argument("--no-auto-knowledge", action="store_false", dest="auto_knowledge", help="Disable auto-detect knowledge queries")
    parser.add_argument("--show-reasoning", action="store_true", help="Show Claude's reasoning")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    parser.add_argument("--env", help="Path to .env file")
    
    args = parser.parse_args()
    
    # Load environment variables if specified
    if args.env:
        load_env_file(args.env)
    
    # Create and run CLI
    cli = XwAIInteractiveCLI(
        server_url=args.server,
        history_file=args.history,
        auto_knowledge=args.auto_knowledge,
        show_reasoning=args.show_reasoning,
        verbose=args.verbose
    )
    
    await cli.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        console.print("\n[bold yellow]KeyboardInterrupt: Exiting[/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Fatal error: {str(e)}[/bold red]")
        sys.exit(1)