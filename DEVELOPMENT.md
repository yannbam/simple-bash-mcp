# Simple-Bash MCP Server Specification

## Overview

Simple-Bash is a lightweight Model Context Protocol (MCP) server written in Python that enables secure execution of bash commands. It provides a controlled environment for executing single bash commands with strict security controls, allowing AI assistants and other MCP clients to run shell commands safely.

## Core Features

1. **Single Command Execution**
   - Execute one-liner bash commands in a secure environment
   - Stateless operation (run command → get output → done)
   - Capture both stdout and stderr from command execution

2. **Security Safeguards**
   - Command whitelist validation (only execute pre-approved commands)
   - Directory whitelist validation (only operate in allowed paths)
   - Optional command timeout enforcement
   - Output size limitation to prevent excessive data return
   - Pattern-based command validation to prevent injection attacks

3. **Configuration System**
   - JSON-based configuration file for all security settings
   - Easy configuration of allowed commands and directories
   - Configurable security parameters

4. **MCP Protocol Integration**
   - Implementation using the MCP Python SDK
   - Single focused tool: `execute_command`

## Security Safeguard System

The security system consists of multiple layers that work together to ensure safe command execution:

### 1. Command Whitelist

- Maintains a list of allowed bash commands (e.g., `ls`, `cat`, `grep`)
- Each command request is validated against this whitelist
- Only the base command is checked (e.g., `ls` in `ls -la /tmp`)
- If the base command isn't in the whitelist, execution is rejected

### 2. Directory Whitelist

- Maintains a list of allowed directories where commands can be executed
- Supports both exact directory matches and subdirectory permissions
- All command working directories are validated before execution
- Commands attempting to run in unauthorized directories are rejected

### 3. Command Pattern Validation

- Optional strict validation to detect potential command injection
- Checks for patterns like `;`, `&&`, `||`, `$()`, backticks, etc.
- Prevents chaining multiple commands or command substitution
- Can be enabled/disabled in configuration

### 4. Execution Controls

- Optional timeout mechanism to prevent long-running commands
- No timeout enforced by default
- Process termination for commands when timeout is specified and exceeded

### 5. Output Controls

- Maximum output size limitation
- Truncation of excessive command output

## Technical Design

### Configuration Management

The configuration file (JSON format) will include:

```json
{
  "allowedCommands": ["ls", "cat", "echo", "pwd", "grep", "find", "head", "tail", "wc"],
  "allowedDirectories": ["/tmp", "/home"],
  "security": {
    "validateCommandsStrictly": true,
    "maxOutputSize": 1048576
  },
  "logging": {
    "level": "info",
    "file": "logs/simple-bash.log"
  }
}
```

### Command Validation Process

1. Extract the base command from the full command string
2. Check if the base command is in the allowed commands list
3. If strict validation is enabled, check for command injection patterns
4. Validate that the working directory is allowed
5. Only proceed with execution if all validation steps pass

### MCP Tool Specification

The server will expose a single MCP tool:

**Tool name:** `execute_command`

**Parameters:**
- `command` (string, required): The bash command to execute
- `cwd` (string, required): Working directory for the command execution
- `timeout` (number, optional): Timeout in seconds (if not provided, no timeout is enforced)

**Return value:**
```json
{
  "success": true|false,
  "output": "command output text",
  "error": "error message if any",
  "exitCode": 0,
  "command": "original command"
}
```

## Implementation Plan

1. **Setup Project Structure**
   - Create a clean, modular Python project
   - Setup proper dependency management

2. **Core Components**
   - Configuration loader and validator
   - Command and directory validation utilities
   - Command execution with optional timeout handling
   - Output limitation logic

3. **MCP Server Implementation**
   - Create server using the MCP Python SDK
   - Define and expose the execute_command tool
   - Integrate with validation and execution components

4. **Testing and Documentation**
   - Write tests for security validation logic
   - Create user documentation for installation and configuration

## Security Best Practices

When implementing and using Simple-Bash MCP:

1. **Maintain strict whitelists:**
   - Only include essential commands in the allowed commands list
   - Keep allowed directories list as restricted as possible
   - Regularly review and update these lists

2. **Enable strict validation:**
   - Keep the strict command validation enabled to prevent command injection
   - Be aware that this will prevent using pipes and redirections

3. **Set reasonable limits:**
   - Use timeouts only when necessary for specific commands
   - Set output size limits to prevent memory issues

4. **Monitor logs:**
   - Review logs regularly for attempted security violations
   - Look for patterns of unauthorized access attempts

This specification provides all necessary information to implement a secure, lightweight MCP server for bash command execution that maintains strong security controls while remaining simple and focused.