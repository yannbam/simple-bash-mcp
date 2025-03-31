import asyncio
import json
import os
import subprocess
import shlex
import signal
import tempfile
import uuid
import glob
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

# Helper function to safely clean up temp files
def self_cleanup_tempfiles(*files):
    """Helper function to safely clean up temporary files."""
    for file in files:
        if file:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except Exception:
                pass
    try:
        current_time = time.time()
        temp_pattern = os.path.join(tempfile.gettempdir(), "mcp_cmd_*")
        for temp_file in glob.glob(temp_pattern):
            try:
                file_age = current_time - os.path.getctime(temp_file)
                if file_age > 1800:
                    os.unlink(temp_file)
            except Exception:
                pass
    except Exception:
        pass


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
            # Format allowed commands into a readable list
            allowed_cmds = ", ".join(sorted(config["allowedCommands"]))
            return False, f"Command '{base_command}' is not in the allowed commands list.\n\nAllowed commands are: {allowed_cmds}"
        
        # Optional: Check for command injection patterns if strict validation is enabled
        if config.get("validateCommandsStrictly", True):
            injection_patterns = [";", "&&", "||", "`", "$(",  ">", "<", "|", "#"]
            for pattern in injection_patterns:
                if pattern in command_str:
                    # Also include list of injection patterns that should be avoided
                    patterns_str = ", ".join([f"'{p}'" for p in injection_patterns])
                    return False, f"Potential command injection detected: '{pattern}'\n\nThe following characters are not allowed when strict validation is enabled: {patterns_str}"
        
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
        
        # Format allowed directories into a readable list
        allowed_dirs = "\n- ".join(config["allowedDirectories"])
        return False, f"Directory '{directory}' is not in the allowed directories list.\n\nAllowed directories are:\n- {allowed_dirs}\n\nNote: Subdirectories of these allowed directories are also permitted."

async def execute_command(command, cwd, timeout=None):
    """Execute a command and return its result.
    
    Implements a secure subprocess execution that isolates MCP stdio transport
    from subprocess I/O to prevent interference with client-server communication.
    """
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
        
        output_file_handle = None
        error_file_handle = None
        
        try:
            output_file_handle = tempfile.NamedTemporaryFile(delete=False, prefix=f"mcp_cmd_output_{uuid.uuid4()}_", suffix=".txt")
            error_file_handle = tempfile.NamedTemporaryFile(delete=False, prefix=f"mcp_cmd_error_{uuid.uuid4()}_", suffix=".txt")
            script_file_handle = tempfile.NamedTemporaryFile(delete=False, prefix=f"mcp_cmd_script_{uuid.uuid4()}_", suffix=".sh")
            output_file = output_file_handle.name
            error_file = error_file_handle.name
            script_file = script_file_handle.name
            with open(script_file, "w") as f:
                f.write(f"source ~/.bashrc\ncd {shlex.quote(cwd)}\n{command}\n")
            output_file_handle.close()
            error_file_handle.close()
            script_file_handle.close()
            bash_script = f"""TERM=dumb script -q -c '/bin/bash -l -i < {shlex.quote(script_file)}' /dev/null > {shlex.quote(output_file)} 2> {shlex.quote(error_file)}"""
        except Exception as e:
            for handle in (output_file_handle, error_file_handle, script_file_handle):
                if handle and os.path.exists(handle.name):
                    try:
                        os.unlink(handle.name)
                    except:
                        pass
            raise
        
        try:
            # Run process in a completely separate process group to avoid terminal interference
            process = subprocess.Popen(
                bash_script,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )

            
            # Create asyncio task to wait for process completion with timeout
            async def wait_for_process():
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, process.wait)
            
            try:
                exit_code = await asyncio.wait_for(wait_for_process(), timeout=timeout_sec)
                
                # Read output from temp files
                stdout_str = ""
                stderr_str = ""
                try:
                    if os.path.exists(output_file):
                        with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                            stdout_str = f.read()
                    if os.path.exists(error_file):
                        with open(error_file, 'r', encoding='utf-8', errors='replace') as f:
                            stderr_str = f.read()
                except Exception as e:
                    pass
                finally:
                    # Always clean up temp files
                    self_cleanup_tempfiles(output_file, error_file, script_file)

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
                    "success": exit_code == 0,
                    "output": output,
                    "error": stderr_str if exit_code != 0 else "",
                    "exitCode": exit_code,
                    "command": command
                }
                
            except asyncio.TimeoutError:
                # Kill the process if it times out
                try:
                    # Kill entire process group
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    # Give it a second to terminate gracefully
                    await asyncio.sleep(1)
                    # Force kill if still running
                    if process.poll() is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    pass
                    
                # Always clean up temp files
                self_cleanup_tempfiles(output_file, error_file, script_file)

                return {
                    "success": False,
                    "output": "",
                    "error": f"Command execution timed out after {timeout_sec} seconds",
                    "exitCode": -1,
                    "command": command
                }
        except Exception as e:
            # Clean up process if needed
            try:
                process.kill()
            except:
                pass
                
            # Always clean up temp files
            self_cleanup_tempfiles(output_file, error_file, script_file)
                            
            return {
                "success": False,
                "output": "",
                "error": f"Error executing command: {str(e)}",
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
    try:
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
    except Exception as e:
        print(f"Error in handle_list_tools: {str(e)}", file=sys.stderr)
        return []

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
    try:
        return []
    except Exception as e:
        print(f"Error in handle_list_resources: {str(e)}", file=sys.stderr)
        return []

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """Return an empty list of prompts."""
    try:
        return []
    except Exception as e:
        print(f"Error in handle_list_prompts: {str(e)}", file=sys.stderr)
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
    
    # Add proper exception handling around the core server loop
    try:
        # Run the server using stdin/stdout streams
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            print("MCP server starting stdio server", file=sys.stderr)
            try:
                await server.run(
                    read_stream,
                    write_stream,
            InitializationOptions(
                server_name="simple-bash-mcp",
                server_version="0.1.0",
                capabilities={
                    # Declare all capabilities implemented by this server
                    "tools": {
                        "listChanged": True
                    },
                    "resources": {
                        "listChanged": True
                    },
                    "prompts": {
                        "listChanged": True
                    }
                },
            ),
        )

            except Exception as e:
                print(f"Error in server.run: {str(e)}", file=sys.stderr)
                print(f"Error type: {type(e).__name__}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
    except Exception as e:
        print(f"Fatal error in main loop: {str(e)}", file=sys.stderr)



# This ensures the main() function is called when the script is run directly
if __name__ == "__main__":
    asyncio.run(main())
