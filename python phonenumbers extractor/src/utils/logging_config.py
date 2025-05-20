"""
Centralized logging configuration for the Phone Extraction project.
This module provides a consistent logging setup that can be used across all modules.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Default log directory
DEFAULT_LOG_DIR = "logs"

# Create logs directory if it doesn't exist
def ensure_log_directory(log_dir: str = DEFAULT_LOG_DIR) -> None:
    """
    Ensure the log directory exists.
    
    Args:
        log_dir: Path to the log directory
    """
    Path(log_dir).mkdir(exist_ok=True, parents=True)

def get_log_level() -> int:
    """
    Get the log level from environment variables or use default.
    
    Returns:
        The logging level as an integer
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, log_level_name, logging.INFO)

def configure_logging(
    name: Optional[str] = None,
    log_file: Optional[str] = None,
    log_level: Optional[int] = None,
    log_format: Optional[str] = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    extra_handlers: Optional[list] = None
) -> logging.Logger:
    """
    Configure logging with consistent settings.
    
    Args:
        name: Logger name (usually __name__)
        log_file: Path to the log file (if None, uses <name>.log)
        log_level: Logging level (if None, uses environment variable LOG_LEVEL or INFO)
        log_format: Log message format (if None, uses default format)
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file
        extra_handlers: Additional logging handlers to add
        
    Returns:
        Configured logger instance
    """
    # Use provided values or defaults
    logger_name = name or "phone_extraction"
    level = log_level or get_log_level()
    
    # Default format includes timestamp, level, logger name, and message
    fmt = log_format or "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s"
    formatter = logging.Formatter(fmt)
    
    # Get or create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates when reconfiguring
    if logger.hasHandlers():
        logger.handlers.clear()
    
    handlers = []
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # Add file handler if requested
    if log_to_file:
        ensure_log_directory()
        log_file_path = log_file or os.path.join(DEFAULT_LOG_DIR, f"{logger_name.split('.')[-1]}.log")
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Add any extra handlers
    if extra_handlers:
        handlers.extend(extra_handlers)
    
    # Add all handlers to logger
    for handler in handlers:
        logger.addHandler(handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the default configuration.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return configure_logging(name=name)