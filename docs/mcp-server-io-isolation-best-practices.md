# MCP Server I/O Stream Handling: Best Practices

## TL;DR

1. **Complete I/O Isolation** - Never share stdio streams between MCP communication and subprocesses
2. **Use Files for Redirection** - Redirect subprocess output to temporary files, not pipes
3. **Disable Terminal Features** - Use `TERM=dumb` and separate process groups
4. **Clean Up Properly** - Handle temp files and processes in all scenarios including errors
5. **Assume Interference** - Always assume subprocesses will attempt interactive terminal features

## Why This Matters

MCP servers using stdio transport share the same I/O channels with the parent process. Interactive commands (npm, git, apt) use terminal control sequences that can corrupt the JSON-RPC message framing used by MCP, causing connection failures.

## Key Principles

### 1. Subprocess I/O Isolation

- **Redirect all I/O**: Send subprocess output to files or null devices, never directly to pipes
- **Use separate process groups**: Run subprocesses with `start_new_session=True` (Python) or `detached: true` (TypeScript)
- **Disable terminal features**: Set `TERM=dumb` in the subprocess environment

### 2. Temporary File Management

- Use system temp directories instead of working directories
- Generate unique filenames (UUIDs) to avoid conflicts
- Implement proper cleanup in all code paths including errors
- Add automatic cleanup of stale temp files (older than 30 minutes)

### 3. Error Handling Strategy

- Always use try/finally blocks for resource cleanup
- Handle timeouts by properly terminating the entire process group
- Implement fallbacks if file operations fail

### 4. MCP Transport Considerations

**For stdio transport:**
- Extra caution needed as all I/O shares the same channels
- Any terminal control characters can break protocol message framing

**For HTTP/SSE transport:**
- Safer but still isolate subprocess execution from main server thread
- Implement error boundaries to prevent subprocess issues from crashing the server

## Problem Commands to Test

Test your implementation with commands known to cause problems:
- `npm install` (progress bars, spinners)
- `git clone` (progress reporting)
- `apt update` (terminal manipulation) 
- Any commands with interactive prompts or heavy terminal I/O

## Implementation Summary

**Python:**
- Redirect output to files: `command > output_file 2> error_file`
- Use `subprocess.Popen` with `start_new_session=True`
- Set `stdin/stdout/stderr=subprocess.DEVNULL`

**TypeScript:**
- Use `child_process.spawn` with `stdio: ['ignore', 'ignore', 'ignore']`
- Set `detached: true` and `env: { ...process.env, TERM: 'dumb' }`
- Read output from files after command completes

By following these guidelines, you'll create MCP servers that reliably handle problematic subprocess execution without crashing your MCP communication channels.
