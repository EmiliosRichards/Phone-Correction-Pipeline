"""Common utilities for the LLM pipeline."""

from typing import List

# File I/O operations for text and JSON data
from .io_utils import load_text, save_text, save_json, load_json

# Text processing utilities for cleaning, chunking, and extracting information
from .text_utils import (
    clean_text,      # Removes unwanted characters and normalizes text
    deduplicate_lines,  # Removes duplicate lines while preserving order
    chunk_text,      # Splits text into manageable chunks
    extract_phone_numbers  # Extracts phone numbers from text
)

# Logging configuration utility
from .log import setup_logger

__all__: List[str] = [
    # I/O utilities
    'load_json',
    'load_text',
    'save_json',
    'save_text',
    
    # Text utilities
    'chunk_text',
    'clean_text',
    'deduplicate_lines',
    'extract_phone_numbers',
    
    # Logging
    'setup_logger'
] 