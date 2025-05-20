import logging
import sys
from typing import Optional
from logging.handlers import RotatingFileHandler

def setup_logging(
    file_log_level=logging.INFO,
    console_log_level=logging.WARNING,
    log_file_path: Optional[str] = None
):
    """
    Set up logging configuration for both console and optional file output.

    Args:
        file_log_level: The logging level for the file handler.
        console_log_level: The logging level for the console handler.
        log_file_path (Optional[str]): Path to the log file. If None, file logging is disabled.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    # Set root logger level to the lowest of the handlers to allow all messages through to handlers
    effective_root_level = min(file_log_level, console_log_level)
    root_logger.setLevel(effective_root_level)

    # Clear existing handlers to avoid duplicate logs if this function is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create a formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (if path is provided)
    if log_file_path:
        try:
            # Use RotatingFileHandler instead of FileHandler
            max_bytes = 10 * 1024 * 1024  # 10 MB per log file
            backup_count = 5  # Keep 5 backup log files (e.g., log.1, log.2, ..., log.5)
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                mode='a',
                encoding='utf-8' # Explicitly set encoding
            )
            file_handler.setLevel(file_log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logging.info(f"File logging enabled. Log file: {log_file_path}, Level: {logging.getLevelName(file_log_level)}")
        except Exception as e:
            logging.error(f"Failed to set up file logging to {log_file_path}: {e}", exc_info=True)
            # Continue with console logging

# TODO: [FutureEnhancement] The __main__ block below demonstrates example usage of the setup_logging function.
# Commented out as it's not intended for execution during normal library use.
# It can be uncommented to test logging configuration independently.
# if __name__ == '__main__':
#     # Example usage:
#     setup_logging(logging.DEBUG)
#     logging.debug("This is a debug message.")
#     logging.info("This is an info message.")
#     logging.warning("This is a warning message.")
#     logging.error("This is an error message.")
#     logging.critical("This is a critical message.")