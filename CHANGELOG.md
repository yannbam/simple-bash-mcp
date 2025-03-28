# Changelog

## [Unreleased]
### Fixed
- Proper process cleanup in `execute_command` to prevent crashes with long-running commands
  - Added `process.kill()` and `await process.wait()` to ensure processes are terminated
  - Added cleanup for both timeout and error cases
  - Prevents zombie processes from accumulating

### Improved
- Enhanced error messages now include information about what is allowed
  - Command restriction errors now list all allowed commands
  - Directory restriction errors now list all allowed directories
  - Injection detection errors now list all disallowed characters

## [0.1.0] - Initial Release
- Basic MCP server implementation
- Secure bash command execution with whitelists
- Auto-reloading configuration