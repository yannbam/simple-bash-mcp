# Simple-Bash MCP Development Guide

## Build & Run
- Install dependencies: `uv sync`
- Run server: `uv run simple-bash-mcp`
- Build package: `uv build`
- Publish: `uv publish`

## Testing
- No formal tests yet - test via MCP Inspector
- Debug with: `npx @modelcontextprotocol/inspector uv --directory /home/jan/ai/claude/claude_fs/simple-bash-mcp run simple-bash-mcp`

## Code Style
- Python 3.10+ syntax
- Type hints for all function signatures
- 4-space indentation
- snake_case for variables/functions
- PascalCase for classes
- Docstrings for all public methods
- Thread-safe operations for config changes
- Async/await for I/O operations

## Configuration
- Edit `src/simple_bash_mcp/config.json`
- Changes auto-reload without restart
- Keep allowed commands/dirs minimal

## Security
- Always validate commands/dirs
- Enable strict command validation
- Set reasonable output limits
- Monitor logs for violations