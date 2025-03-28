# Changelog

## [Unreleased]
### Fixed
- Proper process cleanup in `execute_command` to prevent crashes with long-running commands
  - Added `process.kill()` and `await process.wait()` to ensure processes are terminated
  - Added cleanup for both timeout and error cases
  - Prevents zombie processes from accumulating

## [0.1.0] - Initial Release
- Basic MCP server implementation
- Secure bash command execution with whitelists
- Auto-reloading configuration