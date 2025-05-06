# XwAI-FastMCP Detailed Implementation Plan

This document outlines a comprehensive plan for rebuilding the XwAI-FastMCP solution based on research of previous implementations and best practices.

## Current Status

We have already created a basic repository structure with:
- README.md
- requirements.txt
- tools/utils.py
- server.py
- client.py
- run.sh

## Research Findings

Based on analysis of the previous solution, these are the key components needed:

1. **Core FastMCP Server with SSE Transport**
   - Proper FastMCP 2.2.7 initialization
   - Tool registration pattern
   - SSE transport configuration

2. **Client Implementation**
   - Connection management with retry logic
   - Tool execution with proper response processing
   - CLI interface

3. **Claude Tool Use Integration**
   - Proper two-step flow with tool use
   - String-based tool_result.content (not objects)
   - Tool choice parameter to force Claude to use specific tools
   - Comprehensive tool descriptions

4. **Slite Knowledge Integration**
   - Slite-MCP client for HTTP API
   - Method translation between standard MCP and Slite-MCP
   - Proper error handling and response processing
   - Integration with Claude Tool Use

5. **Configuration and Management**
   - Environment variable loading
   - Server process management
   - Interactive CLI with history and auto-completion

## Required File Structure

```
XwAI-FastMCP/
├── README.md                  # Project overview and documentation
├── requirements.txt           # Project dependencies
├── .gitignore                 # Git ignore rules
├── server.py                  # FastMCP 2.2.7 server implementation
├── client.py                  # FastMCP client implementation
├── config.py                  # Configuration system with Pydantic
├── result_processor.py        # Response processing utilities
├── xwai.py                    # Interactive CLI
├── run.sh                     # Server management script
├── tools/
│   ├── __init__.py            # Package initialization
│   ├── utils.py               # Shared utilities
│   ├── claude.py              # Claude API integration
│   ├── slite.py               # Slite knowledge integration
│   ├── direct_claude_slite.py # Claude Tool Use for Slite
├── tests/                     # Test suite
│   ├── __init__.py            # Package initialization
│   ├── test_server.py         # Server tests
│   ├── test_client.py         # Client tests
│   ├── test_claude.py         # Claude integration tests
│   ├── test_slite.py          # Slite integration tests
```

## Component Implementation Plan

### 1. Configuration System (config.py)

Create a Pydantic-based configuration system to manage settings:
- Server settings (host, port, name, version)
- API keys (Claude, Slite)
- Integration settings (Slite MCP endpoint)
- Environment variable loading with fallbacks

### 2. Result Processor (result_processor.py)

Create a comprehensive utility for processing FastMCP 2.2.7 responses:
- Handle content objects in responses
- Extract text from various response formats
- Convert responses to dictionaries
- Extract metadata from responses

### 3. Claude Tool (tools/claude.py)

Create a Claude API integration with proper Tool Use:
- Register claude_ask tool with FastMCP
- Implement two-step Tool Use flow
- Properly format tool_result.content as string
- Use tool_choice parameter when needed
- Detailed error handling and logging

### 4. Slite Integration (tools/slite.py)

Create a Slite knowledge integration with method translation:
- SliteMCPClient for direct HTTP API calls
- SliteMethodTranslator for FastMCP proxy integration
- Register slite_search, slite_ask tools with FastMCP
- Format responses for consistency

### 5. Direct Claude Slite (tools/direct_claude_slite.py)

Create a direct Claude Tool Use implementation for Slite:
- Comprehensive knowledge tool schema
- Slite query function with proper response processing
- Two-step Claude API call with Tool Use
- Format tool result content as string
- Implement standalone execution mode

### 6. Interactive CLI (xwai.py)

Create an interactive CLI with prompt_toolkit:
- Command history with persistent storage
- Auto-completion for commands and tools
- Conversation tracking
- Tool execution interface
- Auto-knowledge detection
- Configuration options (reasoning display)

### 7. Server Process Management (run.sh)

Enhance server management script with:
- Process detection and cleanup
- Automatic sudo detection
- Tool listing and execution
- Status monitoring
- Direct Claude interface

## Implementation Sequence

1. **Phase 1: Core Components**
   - [x] Update server.py
   - [x] Update client.py
   - [x] Update tools/utils.py
   - [x] Create run.sh

2. **Phase 2: Configuration and Processing**
   - [ ] Implement config.py
   - [ ] Implement result_processor.py
   - [ ] Update server.py and client.py to use new components

3. **Phase 3: Tool Integration**
   - [ ] Implement tools/claude.py
   - [ ] Implement tools/slite.py
   - [ ] Update server.py to register tools properly

4. **Phase 4: Claude Tool Use for Slite**
   - [ ] Implement tools/direct_claude_slite.py
   - [ ] Test Claude Tool Use with Slite integration
   - [ ] Ensure proper formatting of responses

5. **Phase 5: Interactive CLI**
   - [ ] Implement xwai.py with prompt_toolkit
   - [ ] Add command history and auto-completion
   - [ ] Implement conversation tracking
   - [ ] Add configuration options
   - [ ] Test end-to-end functionality

## Specific Implementation Details

### Claude Tool Use Pattern

The key to fixing the previous implementation issues is the correct Tool Use pattern:

```python
# Step 1: Initial request with tool definition
response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=1024,
    tools=[KNOWLEDGE_TOOL],
    messages=[{"role": "user", "content": query}]
)

# If Claude wants to use the tool
if response.stop_reason == "tool_use":
    # Find the tool use request
    tool_use = next((c for c in response.content if c.type == "tool_use"), None)
    
    if tool_use:
        # Get knowledge base result
        kb_result = await query_knowledge_base(tool_use.input.get("query"))
        
        # IMPORTANT: Ensure kb_result is a string, not an object
        if not isinstance(kb_result, str):
            kb_result = str(kb_result)
        
        # Step 2: Send tool result back to Claude
        final_response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=1024,
            tools=[KNOWLEDGE_TOOL],
            messages=[
                {"role": "user", "content": query},
                {"role": "assistant", "content": [c for c in response.content]},
                {"role": "user", "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": kb_result  # Must be a string
                    }
                ]}
            ]
        )
```

### Slite Method Translation

The key to proper FastMCP-Slite integration is the method translation:

```python
# Convert tools/execute to tools/call with appropriate parameter structure
if method == "tools/execute":
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": tool_input  # Rename input to arguments
        }
    }
```

## Testing Strategy

1. **Component Testing**
   - Test each component in isolation
   - Verify Claude API integration
   - Verify Slite MCP integration
   - Test Method Translation

2. **Integration Testing**
   - Test end-to-end functionality
   - Verify Claude Tool Use for Slite
   - Test server and client interaction

3. **Validation Testing**
   - Test with specific problem queries
   - Verify sensitive information access
   - Test error handling

## Conclusion

This implementation plan provides a comprehensive roadmap for rebuilding the XwAI-FastMCP solution with proper FastMCP 2.2.7 support, Claude Tool Use for Slite knowledge access, and interactive CLI. By following this plan and incorporating the lessons learned from previous implementations, we can build a robust and reliable solution.