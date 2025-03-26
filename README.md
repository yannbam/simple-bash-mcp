# simple-bash-mcp MCP Server

A simple, secure Bash command execution MCP server.

## Features

- Execute individual bash commands in a secure environment
- Multiple security layers including command and directory whitelists
- Optional timeout and output size limitations
- Simple, stateless design
- Auto-update of configuration when config.json changes without server restart

## Security Controls

- **Command Whitelist**: Only pre-approved commands can be executed
- **Directory Whitelist**: Commands can only run in specified directories
- **Pattern Validation**: Prevents command injection attacks
- **Output Limiting**: Prevents excessive data return
- **Shell Isolation**: Commands run in a controlled bash environment

## Tool Specification

The server provides a single tool:

- **execute_command**: Executes a bash command securely
  - Parameters:
    - `command` (string, required): The bash command to execute
    - `cwd` (string, required): Working directory for command execution
    - `timeout` (number, optional): Timeout in seconds
  - Returns:
    - A JSON object with:
      - `success`: Boolean indicating if command succeeded
      - `output`: Command output (stdout+stderr)
      - `error`: Error message (if any)
      - `exitCode`: The command's exit code
      - `command`: Original command string

## Configuration

The server uses a simple JSON configuration file at `src/simple_bash_mcp/config.json`:

```json
{
  "allowedCommands": ["ls", "cat", "echo", "pwd", "grep", "find", "head", "tail", "wc"],
  "allowedDirectories": ["/tmp", "/home"],
  "validateCommandsStrictly": true,
  "maxOutputSize": 1048576
}
```

- `allowedCommands`: List of executable base commands
- `allowedDirectories`: Where commands can be executed
- `validateCommandsStrictly`: Enable pattern-based injection prevention
- `maxOutputSize`: Maximum output size in bytes (default: 1MB)

The configuration file is monitored for changes and automatically reloaded when modified, allowing you to update settings without restarting the server.

## Quickstart

### Install

#### Claude Desktop

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  
  ```json
  "mcpServers": {
    "simple-bash-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/jan/ai/claude/claude_fs/simple-bash-mcp",
        "run",
        "simple-bash-mcp"
      ]
    }
  }
  ```
</details>

<details>
  <summary>Published Servers Configuration</summary>
  
  ```json
  "mcpServers": {
    "simple-bash-mcp": {
      "command": "uvx",
      "args": [
        "simple-bash-mcp"
      ]
    }
  }
  ```
</details>

## Development

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

3. Publish to PyPI:
```bash
uv publish
```

### Debugging

For debugging, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uv --directory /home/jan/ai/claude/claude_fs/simple-bash-mcp run simple-bash-mcp
```

## Security Best Practices

When using Simple-Bash MCP:

1. **Maintain strict whitelists**
   - Keep the command and directory lists minimal
   - Only include essential commands

2. **Keep strict validation enabled**
   - Prevents command injection and chaining

3. **Use timeouts when needed**
   - Set timeouts for potentially long-running commands

4. **Test commands thoroughly**
   - Verify all security checks function as expected
