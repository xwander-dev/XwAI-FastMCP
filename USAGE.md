# XwAI-FastMCP Usage Guide

This guide explains how to use the XwAI-FastMCP system with its various components.

## Prerequisites

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your API keys:
   ```
   CLAUDE_API_KEY=your_claude_api_key
   SLITE_API_KEY=your_slite_api_key
   ```

## Server Management

The `run.sh` script provides easy server management:

```bash
# Start the server
./run.sh start

# Check server status
./run.sh status

# List available tools
./run.sh tools

# Stop the server
./run.sh stop

# Clean up orphaned server processes
./run.sh cleanup
```

## Interactive CLI

The interactive CLI provides a user-friendly interface for working with XwAI:

```bash
# Start the interactive CLI
python xwai.py

# Start with specific options
python xwai.py --show-reasoning --verbose
```

### CLI Commands

- `help` - Display help information
- `exit` or `quit` - Exit the CLI
- `clear` - Clear the terminal screen
- `tools` - List available tools
- `status` - Check server status
- `config` - Display current configuration

### Knowledge Queries

Use special prefixes for knowledge queries:

- `?query` - Execute a knowledge query (auto-detects whether to use knowledge base)
- `!query` - Force a knowledge query (always uses knowledge base)

Examples:
```
?what is joni's phone number
!what is the FOTA url
```

### Tool Execution

Execute specific tools with parameters:

```
tool_name param=value
tool_name param1=value1 param2=value2
```

Example:
```
ask_claude query="What is FastMCP?"
search_slite query="documentation" limit=5
```

## Direct API Usage

### Claude with Knowledge

Use the `direct_claude_slite.py` script for direct knowledge queries:

```bash
# Ask a question
python tools/direct_claude_slite.py "What is Joni Kautto's phone number?"

# Force knowledge tool usage
python tools/direct_claude_slite.py "What is the FOTA url?" --force

# Show Claude's reasoning
python tools/direct_claude_slite.py "What is the office Wi-Fi password?" --show-reasoning
```

### Client Usage

For programmatic usage, you can use the `XwAIClient` class:

```python
from client import XwAIClient
import asyncio

async def main():
    # Create client
    client = XwAIClient("http://localhost:9001/sse")
    
    # Call tool
    result = await client.call_tool("ask_claude", query="What is FastMCP?")
    print(result)

asyncio.run(main())
```

## Environment Variables

The following environment variables can be used to configure XwAI:

- `CLAUDE_API_KEY` - Claude API key
- `SLITE_API_KEY` - Slite API key
- `XWAI_HOST` - Server host (default: 0.0.0.0)
- `XWAI_PORT` - Server port (default: 9001)
- `XWAI_LOG_LEVEL` - Log level (default: INFO)
- `XWAI_AUTO_KNOWLEDGE` - Auto-detect knowledge queries (default: True)
- `XWAI_HISTORY_FILE` - History file path (default: ~/.xwai_history)

## Troubleshooting

### Server Issues

If the server fails to start or respond:

1. Check for orphaned processes: `./run.sh cleanup`
2. Check if the port is already in use: `lsof -i :9001`
3. Check server logs: `cat server.log`

### Claude API Issues

If Claude API calls fail:

1. Verify your API key in the `.env` file
2. Check your API usage and limits
3. Try a different model or fewer tokens

### Slite Integration Issues

If Slite integration fails:

1. Verify your Slite API key
2. Check if the Slite-MCP server is running
3. Try the direct HTTP client: `python tools/slite.py`