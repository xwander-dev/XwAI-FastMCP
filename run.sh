#!/bin/bash
# XwAI FastMCP Server Management Script

# Configuration
SERVER_PID_FILE=".server.pid"
SERVER_SCRIPT="server.py"
SERVER_LOG="server.log"
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="9001"

# Check for sudo if needed
need_sudo() {
    if [ -f "$SERVER_PID_FILE" ] && ! [ -w "$SERVER_PID_FILE" ]; then
        return 0
    fi
    
    if [ -f "$SERVER_LOG" ] && ! [ -w "$SERVER_LOG" ]; then
        return 0
    fi
    
    return 1
}

# Function to check for orphaned FastMCP servers
cleanup_orphaned_servers() {
    echo "Checking for orphaned FastMCP servers..."
    
    # Find any python server.py processes that don't match our PID file
    orphaned_pids=""
    
    if [ -f "$SERVER_PID_FILE" ]; then
        known_pid=$(cat "$SERVER_PID_FILE")
        # Find all python server.py processes excluding grep and our known PID
        if need_sudo; then
            orphaned_pids=$(sudo ps aux | grep "python.*server.py" | grep -v grep | grep -v "$known_pid" | awk '{print $2}')
        else
            orphaned_pids=$(ps aux | grep "python.*server.py" | grep -v grep | grep -v "$known_pid" | awk '{print $2}')
        fi
    else
        # No PID file, so all server.py processes are orphaned
        if need_sudo; then
            orphaned_pids=$(sudo ps aux | grep "python.*server.py" | grep -v grep | awk '{print $2}')
        else
            orphaned_pids=$(ps aux | grep "python.*server.py" | grep -v grep | awk '{print $2}')
        fi
    fi
    
    # If we found orphaned pids, kill them
    if [ -n "$orphaned_pids" ]; then
        echo "Found orphaned FastMCP servers. Cleaning up..."
        for pid in $orphaned_pids; do
            echo "Killing orphaned process $pid..."
            if need_sudo; then
                sudo kill $pid 2>/dev/null || sudo kill -9 $pid 2>/dev/null
            else
                kill $pid 2>/dev/null || kill -9 $pid 2>/dev/null
            fi
        done
        echo "Cleanup complete."
    else
        echo "No orphaned FastMCP servers found."
    fi
}

# Start the server
start_server() {
    if [ -f "$SERVER_PID_FILE" ]; then
        pid=$(cat "$SERVER_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Server is already running with PID $pid."
            return 1
        else
            echo "Removing stale PID file..."
            if need_sudo; then
                sudo rm -f "$SERVER_PID_FILE"
            else
                rm -f "$SERVER_PID_FILE"
            fi
        fi
    fi
    
    # Cleanup orphaned servers before starting
    cleanup_orphaned_servers
    
    local host=${1:-$DEFAULT_HOST}
    local port=${2:-$DEFAULT_PORT}
    
    echo "Starting XwAI FastMCP server on $host:$port..."
    python "$SERVER_SCRIPT" --host "$host" --port "$port" > /dev/null 2>&1 &
    local pid=$!
    
    # Wait a moment to ensure the server started properly
    sleep 1
    
    if ps -p $pid > /dev/null 2>&1; then
        echo $pid > "$SERVER_PID_FILE"
        echo "Server started with PID $pid."
        echo "Logs are available in $SERVER_LOG."
        return 0
    else
        echo "Failed to start server. Check logs for details."
        return 1
    fi
}

# Stop the server
stop_server() {
    if [ ! -f "$SERVER_PID_FILE" ]; then
        echo "No PID file found. Server may not be running."
        # Still attempt to clean up orphaned servers
        cleanup_orphaned_servers
        return 1
    fi
    
    pid=$(cat "$SERVER_PID_FILE")
    if ps -p $pid > /dev/null 2>&1; then
        echo "Stopping server with PID $pid..."
        if need_sudo; then
            sudo kill $pid
            # Wait a moment
            sleep 2
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo "Server did not stop gracefully. Force killing..."
                sudo kill -9 $pid
            fi
            sudo rm -f "$SERVER_PID_FILE"
        else
            kill $pid
            # Wait a moment
            sleep 2
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo "Server did not stop gracefully. Force killing..."
                kill -9 $pid
            fi
            rm -f "$SERVER_PID_FILE"
        fi
        echo "Server stopped."
        return 0
    else
        echo "Server is not running with PID $pid."
        if need_sudo; then
            sudo rm -f "$SERVER_PID_FILE"
        else
            rm -f "$SERVER_PID_FILE"
        fi
        # Clean up orphaned servers
        cleanup_orphaned_servers
        return 1
    fi
}

# Check server status
check_status() {
    if [ ! -f "$SERVER_PID_FILE" ]; then
        echo "No PID file found. Server is not running."
        return 1
    fi
    
    pid=$(cat "$SERVER_PID_FILE")
    if ps -p $pid > /dev/null 2>&1; then
        echo "Server is running with PID $pid."
        echo "Logs are available in $SERVER_LOG."
        
        # Check for orphaned servers
        local orphaned_count=0
        if need_sudo; then
            orphaned_count=$(sudo ps aux | grep "python.*server.py" | grep -v grep | grep -v "$pid" | wc -l)
        else
            orphaned_count=$(ps aux | grep "python.*server.py" | grep -v grep | grep -v "$pid" | wc -l)
        fi
        
        if [ "$orphaned_count" -gt 0 ]; then
            echo "Warning: Found $orphaned_count orphaned server processes."
            echo "Run './run.sh cleanup' to clean up orphaned processes."
        fi
        
        return 0
    else
        echo "Server is not running with PID $pid. Removing stale PID file."
        if need_sudo; then
            sudo rm -f "$SERVER_PID_FILE"
        else
            rm -f "$SERVER_PID_FILE"
        fi
        return 1
    fi
}

# List available tools
list_tools() {
    if check_status > /dev/null 2>&1; then
        echo "Listing available tools..."
        python client.py --tool get_server_info
    else
        echo "Server is not running. Start the server first."
        return 1
    fi
}

# Execute a specific tool
execute_tool() {
    local tool=$1
    local params=${2:-"{}"}
    
    if check_status > /dev/null 2>&1; then
        echo "Executing tool '$tool' with params: $params"
        python client.py --tool "$tool" --params "$params"
    else
        echo "Server is not running. Start the server first."
        return 1
    fi
}

# Ask Claude a question
ask_claude() {
    local query="$1"
    
    if check_status > /dev/null 2>&1; then
        echo "Asking Claude: $query"
        python client.py --tool ask_claude --params "{\"query\": \"$query\"}"
    else
        echo "Server is not running. Start the server first."
        return 1
    fi
}

# Print usage information
print_usage() {
    echo "Usage: $0 COMMAND [ARGS]"
    echo ""
    echo "Commands:"
    echo "  start [host] [port]     Start the server (default: $DEFAULT_HOST:$DEFAULT_PORT)"
    echo "  stop                    Stop the server"
    echo "  status                  Check server status"
    echo "  cleanup                 Clean up orphaned server processes"
    echo "  restart                 Restart the server"
    echo "  tools                   List available tools"
    echo "  exec TOOL [PARAMS]      Execute a specific tool (PARAMS as JSON string)"
    echo "  ask \"QUERY\"             Ask Claude a question"
    echo "  help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start                Start the server with default settings"
    echo "  $0 start localhost 8000 Start the server on localhost:8000"
    echo "  $0 exec echo '{\"message\": \"Hello\"}'"
    echo "  $0 ask \"What is FastMCP?\""
    echo ""
}

# Main entry point
case "$1" in
    start)
        start_server "$2" "$3"
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        start_server "$2" "$3"
        ;;
    status)
        check_status
        ;;
    cleanup)
        cleanup_orphaned_servers
        ;;
    tools)
        list_tools
        ;;
    exec)
        if [ -z "$2" ]; then
            echo "Error: No tool specified."
            print_usage
            exit 1
        fi
        execute_tool "$2" "$3"
        ;;
    ask)
        if [ -z "$2" ]; then
            echo "Error: No query specified."
            print_usage
            exit 1
        fi
        ask_claude "$2"
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        echo "Error: Unknown command '$1'."
        print_usage
        exit 1
        ;;
esac