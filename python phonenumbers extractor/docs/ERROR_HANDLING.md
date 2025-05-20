# Error Handling and Logging

This document describes the error handling and logging approach used in the Regex-Phone-Extraction project.

## Logging Configuration

The project uses a centralized logging configuration defined in `src/utils/logging_config.py`. This ensures consistent logging behavior across all modules.

### Log Levels

The following log levels are available, in order of increasing severity:

- **DEBUG**: Detailed information, typically useful only for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened, or may happen in the future
- **ERROR**: Due to a more serious problem, the software has not been able to perform a function
- **CRITICAL**: A serious error indicating that the program itself may be unable to continue running

### Configuration

The log level can be configured via the `LOG_LEVEL` environment variable in the `.env` file:

```
LOG_LEVEL=INFO
```

### Usage in Code

To use the centralized logging configuration in a module:

```python
from src.utils.logging_config import get_logger

# Get logger for this module
log = get_logger(__name__)

# Use the logger
log.debug("Debug message")
log.info("Info message")
log.warning("Warning message")
log.error("Error message")
log.critical("Critical message")

# Log exceptions with traceback
try:
    # Some code that might raise an exception
    result = 1 / 0
except Exception as e:
    log.error(f"An error occurred: {e}", exc_info=True)
```

## Error Handling Approach

The project follows these error handling principles:

1. **Catch Specific Exceptions**: Catch specific exceptions rather than using bare `except` clauses
2. **Log Exceptions with Context**: Include relevant context information when logging exceptions
3. **Include Tracebacks**: Use `exc_info=True` to include tracebacks in error logs
4. **Graceful Degradation**: When possible, degrade gracefully rather than failing completely
5. **Consistent Error Reporting**: Use consistent error reporting across all modules

### Example Error Handling Pattern

```python
def process_data(data):
    try:
        # Process the data
        result = perform_operation(data)
        return result
    except ValueError as e:
        # Handle specific exception
        log.warning(f"Invalid data format: {e}")
        return None
    except IOError as e:
        # Handle another specific exception
        log.error(f"I/O error while processing data: {e}", exc_info=True)
        return None
    except Exception as e:
        # Catch-all for unexpected exceptions
        log.error(f"Unexpected error while processing data: {e}", exc_info=True)
        return None
```

## Log File Locations

By default, log files are stored in the `logs` directory at the root of the project. Each module creates its own log file named after the module (e.g., `extractor.log`, `validator.log`).

## Viewing Logs

You can view logs using standard text editors or command-line tools:

```bash
# View the last 50 lines of the extractor log
tail -n 50 logs/extractor.log

# Search for error messages in all logs
grep "ERROR" logs/*.log