"""Common path utilities for the LLM pipeline."""

import os
import logging
from pathlib import Path
from typing import Union, List, Optional

logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """Get the absolute path to the project root directory.
    
    Returns:
        Path object pointing to the project root.
    """
    # Start from the current file's directory
    current_dir = Path(__file__).parent
    
    # Navigate up to the project root (where llm_pipeline directory is)
    while current_dir.name != "llm_pipeline" and current_dir.parent != current_dir:
        current_dir = current_dir.parent
    
    # Go up one more level to get to the project root
    return current_dir.parent

def get_hostname_from_path(file_path: Union[str, Path]) -> str:
    """
    Extracts a hostname-like string from a file path, typically the filename stem.

    Args:
        file_path: The path to the file (string or Path object).

    Returns:
        A string representing the hostname, usually the file's stem.
    """
    return Path(file_path).stem

def discover_input_files(input_dir: Union[str, Path], pattern: str, limit: Optional[int] = None) -> List[Path]:
    """
    Discovers input files in a directory matching a given pattern.

    Args:
        input_dir: The directory to search in (string or Path object).
        pattern: The glob pattern to match files (e.g., "*.txt").
        limit: Optional maximum number of files to return.

    Returns:
        A list of Path objects for the discovered files.
    """
    input_dir_path = Path(input_dir)
    logger.info(f"Searching for input files in '{input_dir_path}' with pattern '{pattern}'")
    files = list(input_dir_path.glob(pattern))
    if limit is not None and limit > 0:
        files = files[:limit]
    logger.info(f"Found {len(files)} files to process.")
    return files