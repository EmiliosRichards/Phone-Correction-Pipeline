"""Common logging utilities."""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    format_str: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    use_rotation: bool = False,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3,
    env_level: Optional[str] = None,
    to_console: bool = True
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.
    
    Args:
        name: Name of the logger
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        format_str: Log message format string
        use_rotation: Whether to use rotating file handler (default: False)
        max_bytes: Maximum bytes per log file when rotation is enabled (default: 5MB)
        backup_count: Number of backup files to keep when rotation is enabled (default: 3)
        env_level: Optional environment variable name to override log level (e.g., "DEBUG")
        to_console: Whether to output logs to console (default: True)
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    
    # Set level from environment variable if specified
    if env_level:
        level = getattr(logging, env_level.upper(), logging.INFO)
    
    logger.setLevel(level)
    
    # Only add handlers if none exist
    if not logger.handlers:
        # Create formatter
        formatter = logging.Formatter(format_str)
        
        # Add console handler if enabled
        if to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # Add file handler if log_file is specified
        if log_file:
            # Create log directory if it doesn't exist
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            if use_rotation:
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
            else:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str, env_level: Optional[str] = None, to_console: bool = True) -> logging.Logger:
    """
    Get a pre-configured logger with sensible defaults.
    This is a convenience function for quick logger setup in modules.
    
    Args:
        name: Name of the logger (typically __name__ of the module)
        env_level: Optional environment variable name to override log level
        to_console: Whether to output logs to console (default: True)
        
    Returns:
        Configured logger instance with console output only
    """
    return setup_logger(
        name=name,
        level=logging.INFO,
        log_file=None,  # No file output by default
        format_str='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        env_level=env_level,
        to_console=to_console
    )

# Example usage:
if __name__ == "__main__":
    # Example 1: Full setup with rotation and environment-based level
    logger = setup_logger(
        "example",
        log_file=Path("logs/example.log"),
        use_rotation=True,  # Enable log rotation
        max_bytes=1024 * 1024,  # 1MB for demo
        backup_count=3,
        env_level="DEBUG"  # Will use DEBUG level if valid, falls back to INFO
    )
    
    # Example 2: Quick setup using get_logger
    simple_logger = get_logger(__name__)
    
    # Log some messages to demonstrate different levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Log with the simple logger
    simple_logger.info("This is from the simple logger")
    
    # Example 3: Server mode (no console output)
    server_logger = setup_logger(
        "server",
        log_file=Path("logs/server.log"),
        to_console=False
    )
    server_logger.info("This message only goes to the log file") 