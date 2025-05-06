# XwAI-FastMCP

A clean, minimal implementation of FastMCP 2.2.7 with Claude 3.7 Tool Use integration for Slite knowledge access.

## Overview

XwAI-FastMCP provides a robust server implementation of the Model Context Protocol (FastMCP) version 2.2.7, with a focus on clean architecture and extensibility. This implementation features:

- FastMCP 2.2.7 server with SSE transport
- Claude 3.7 API integration with proper Tool Use pattern
- Slite knowledge base integration
- Interactive command-line interface
- Comprehensive configuration management
- Server process management utilities

## Getting Started

### Prerequisites

- Python 3.10+
- FastMCP 2.2.7+
- Anthropic API key (for Claude integration)
- Slite API key (for knowledge base access)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/xwander-dev/XwAI-FastMCP.git
   cd XwAI-FastMCP
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your API keys:
   ```
   CLAUDE_API_KEY=your_claude_api_key
   SLITE_API_KEY=your_slite_api_key
   ```

### Usage

#### Server Management

```bash
# Start the server
./run.sh start

# Stop the server
./run.sh stop

# Check server status
./run.sh status

# List available tools
./run.sh tools
```

#### Direct Tool Execution

```bash
# Ask Claude a question
./run.sh ask "What is FastMCP?"

# Search Slite knowledge base
./run.sh slite "system architecture"
```

#### Interactive CLI

```bash
# Start the interactive CLI
python xwai.py
```

## Architecture

XwAI-FastMCP follows a modular architecture:

- `server.py` - FastMCP 2.2.7 server implementation
- `client.py` - FastMCP client for tool execution
- `run.sh` - Server and tool management script
- `xwai.py` - Interactive command-line interface
- `config.py` - Pydantic-based configuration management
- `result_processor.py` - Response processing utilities
- `tools/` - Tool implementations (Claude, Slite, etc.)

## Features

### FastMCP 2.2.7 Server

- SSE transport for reliable streaming
- Modular tool registration
- Comprehensive error handling
- Process management with orphaned server detection

### Claude 3.7 Integration

- Proper Tool Use pattern implementation
- Two-step flow for function calling
- Comprehensive tool descriptions
- Reliable error handling

### Slite Knowledge Access

- Robust knowledge base search
- Comprehensive error handling
- Result formatting for readability
- Integration with Claude Tool Use

### Interactive CLI

- Command history and auto-completion
- Tool discovery and execution
- Conversation context management
- Rich text formatting

## License

MIT

## Acknowledgments

- [FastMCP](https://github.com/slite-tech/fastmcp) - Model Context Protocol
- [Anthropic](https://www.anthropic.com/) - Claude API
- [Slite](https://slite.com/) - Knowledge base platform