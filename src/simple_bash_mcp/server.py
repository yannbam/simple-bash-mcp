import asyncio
import json
import os
import subprocess
import shlex
from pathlib import Path
import sys
import time
import threading

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

from mcp.server.lowlevel import NotificationOptions

# Configuration file path
CONFIG_FILE = Path(__file__).parent / "config.json"

# Configuration and tracking variables
config = {}
config_last_modified = 0
config_lock = threading.RLock()

# Load configuration initially
def load_config():
    global config, config_last_modified
    with config_lock:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        config_last_modified = os.path.getmtime(CONFIG_FILE)
        print(f"Configuration loaded at {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
        return config

# Check for configuration changes
def check_config_updates():
    global config_last_modified
    try:
        current_mtime = os.path.getmtime(CONFIG_FILE)
        if current_mtime > config_last_modified:
            print(f"Configuration file changed, reloading...", file=sys.stderr)
            load_config()
            return True
        return False
    except Exception as e:
        print(f"Error checking configuration updates: {str(e)}", file=sys.stderr)
        return False

# Initialize configuration
load_config()

server = Server("simple-bash-mcp")

def validate_command(command_str):
    """Validate that the command is allowed to execute."""
    # Check for configuration updates
    check_config_updates()
    
    with config_lock:
        # Extract the base command (first word before any spaces)
        base_command = command_str.strip().split()[0]
        
        # Check if base command is in allowed list
        if base_command not in config["allowedCommands"]:
            return False, f"Command '{base_command}' is not in the allowed commands list"
        
        # Optional: Check for command injection patterns if strict validation is enabled
        if config.get("validateCommandsStrictly", True):
            injection_patterns = [";", "&&", "||", "`", "$(",  ">", "<", "|", "#"]
            for pattern in injection_patterns:
                if pattern in command_str:
                    return False, f"Potential command injection detected: '{pattern}'"
        
        return True, ""

def validate_directory(directory):
    """Validate that the directory is allowed for command execution."""
    # Check for configuration updates
    check_config_updates()
    
    with config_lock:
        directory_path = Path(directory).resolve()
        
        # Check if directory is in allowed list or is a subdirectory of an allowed directory
        for allowed_dir in config["allowedDirectories"]:
            allowed_path = Path(allowed_dir).resolve()
            if directory_path == allowed_path or allowed_path in directory_path.parents:
                return True, ""
        
        return False, f"Directory '{directory}' is not in the allowed directories list"

async def execute_command(command, cwd, timeout=None):
    """Execute a command and return its result."""
    # Validate command and directory
    cmd_valid, cmd_error = validate_command(command)
    if not cmd_valid:
        return {
            "success": False,
            "error": cmd_error,
            "output": "",
            "exitCode": 1,
            "command": command
        }
    
    dir_valid, dir_error = validate_directory(cwd)
    if not dir_valid:
        return {
            "success": False,
            "error": dir_error,
            "output": "",
            "exitCode": 1,
            "command": command
        }
    
    # Execute the command
    try:
        # Use timeout if specified
        timeout_sec = timeout if timeout else None
        
        # Prepare environment by explicitly using bash with proper environment
        # Use a login shell (-l) to ensure profile/bashrc is loaded
        full_command = f"/bin/bash -l -c '{command}'"
        
        # Execute the command with subprocess
        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=os.environ.copy()  # Use current environment
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout_sec
            )
            
            # Decode stdout and stderr
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')
            
            # Combine output and limit size if needed
            output = stdout_str
            if stderr_str:
                output += f"\nSTDERR:\n{stderr_str}"
                
            # Check for configuration updates before applying the settings
            check_config_updates()
            
            with config_lock:
                max_size = config.get("maxOutputSize", 1048576)  # Default 1MB
            if len(output) > max_size:
                output = output[:max_size] + "\n... [OUTPUT TRUNCATED]"
            
            return {
                "success": process.returncode == 0,
                "output": output,
                "error": stderr_str if process.returncode != 0 else "",
                "exitCode": process.returncode,
                "command": command
            }
            
        except asyncio.TimeoutError:
            # Kill the process if it times out
            process.kill()
            return {
                "success": False,
                "output": "",
                "error": f"Command execution timed out after {timeout_sec} seconds",
                "exitCode": -1,
                "command": command
            }
            
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Error executing command: {str(e)}",
            "exitCode": -1,
            "command": command
        }

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="execute_command",
            description="Execute a bash command in a secure environment",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"},
                    "cwd": {"type": "string", "description": "Working directory for the command"},
                    "timeout": {"type": "number", "description": "Optional timeout in seconds"}
                },
                "required": ["command", "cwd"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if name != "execute_command":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments:
        raise ValueError("Missing arguments")

    command = arguments.get("command")
    cwd = arguments.get("cwd")
    timeout = arguments.get("timeout")

    if not command or not cwd:
        raise ValueError("Missing required command or cwd parameter")

    result = await execute_command(command, cwd, timeout)
    
    # Format output as text content
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )
    ]

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """Return an empty list of resources."""
    return []

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """Return an empty list of prompts."""
    return []

# Create a periodic task to check for configuration file changes
async def config_monitor():
    """Periodically check for changes to the config file."""
    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        if check_config_updates():
            print(f"Configuration updated at {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)

async def main():
    # Print a simple startup message to stderr
    print("Simple-Bash MCP Server starting...", file=sys.stderr)
    
    # Start the configuration monitor task
    monitor_task = asyncio.create_task(config_monitor())
    

    # my_notification_options = NotificationOptions(
    #     tools_changed=True,  # Set to True if you plan to send notifications
    #     resources_changed=True,
    #     prompts_changed=True
    # )

    # capabilities = server.get_capabilities(
    #     notification_options=my_notification_options,
    #     experimental_capabilities={},
    # )

    # print(f"Server capabilities: {capabilities}", file=sys.stderr)
    # # Or try to access attributes
    # print(f"Tools capability: {getattr(capabilities, 'tools', None)}", file=sys.stderr)
    # print(f"Resources capability: {getattr(capabilities, 'resources', None)}", file=sys.stderr)
    # print(f"Prompts capability: {getattr(capabilities, 'prompts', None)}", file=sys.stderr)




    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="simple-bash-mcp",
                server_version="0.1.0",
                capabilities={
                  # Only declare the tools capability - don't include resources or prompts
                    "tools": {
                    "listChanged": True
            },
        },
            ),
        )

                # capabilities=server.get_capabilities(
                #     # notification_options=NotificationOptions(),
                #     notification_options=my_notification_options,                    
                #     experimental_capabilities={},



# This ensures the main() function is called when the script is run directly
if __name__ == "__main__":
    asyncio.run(main())
