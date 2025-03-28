# Feature Implementation Checklist

## Enhance error messages with information about what is allowed

- [x] Modify `validate_command` function to include allowed commands in error messages
- [x] Modify `validate_directory` function to include allowed directories in error messages
- [x] Ensure error messages are properly formatted and informative
- [x] Test the implementation with various commands and directories
- [x] Update documentation if necessary

## Implementation Notes

- We need to modify the error messages in the `validate_command` and `validate_directory` functions
- The error messages should clearly indicate what went wrong and provide guidance on what is allowed
- For commands, we should list all allowed commands
- For directories, we should list all allowed directories
- The messages should be formatted for readability (especially for long lists)
