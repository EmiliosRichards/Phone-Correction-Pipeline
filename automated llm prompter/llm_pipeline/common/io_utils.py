"""Common file I/O utilities for the LLM pipeline."""

import json
from pathlib import Path
from typing import Dict, Any

def load_text(path: Path, silent: bool = False) -> str:
    """
    Load text content from a file.
    
    Args:
        path: Path to the text file
        silent: If True, return empty string instead of raising FileNotFoundError
        
    Returns:
        The text content as a string
        
    Raises:
        FileNotFoundError: If the file doesn't exist and silent is False
        Exception: For other I/O errors
        
    Example:
        >>> from pathlib import Path
        >>> content = load_text(Path("data/input.txt"))
        >>> # With silent mode
        >>> content = load_text(Path("missing.txt"), silent=True)  # Returns ""
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        if silent:
            return ""
        raise FileNotFoundError(f"Text file not found at {path}")
    except Exception as e:
        raise Exception(f"Error loading text file: {str(e)}")

def save_text(path: Path, content: str) -> None:
    """
    Save text content to a file.
    
    Args:
        path: Path where to save the text file
        content: String content to save
        
    Raises:
        Exception: For I/O errors
        
    Example:
        >>> from pathlib import Path
        >>> save_text(Path("output/result.txt"), "Hello, World!")
        >>> # Creates directories if needed
        >>> save_text(Path("new/dir/file.txt"), "Content")
    """
    try:
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise Exception(f"Error saving text file: {str(e)}")

def save_json(path: Path, data: Dict[str, Any], add_header_comment: str = None) -> None:
    """
    Save data to a JSON file.
    
    Args:
        path: Path where to save the JSON file
        data: Dictionary to save as JSON
        add_header_comment: Optional comment to add at the start of the file.
            If provided, will be added as a line starting with "//"
        
    Raises:
        Exception: For I/O or JSON serialization errors
        
    Example:
        >>> from pathlib import Path
        >>> data = {"name": "John", "age": 30}
        >>> save_json(Path("output/data.json"), data)
        >>> # With header comment
        >>> save_json(Path("output/config.json"), data, 
        ...          add_header_comment="Generated on 2024-03-20")
    """
    try:
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            # Write comment if provided
            if add_header_comment:
                f.write(f"// {add_header_comment}\n")
            
            # Write JSON content
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise Exception(f"Error saving JSON file: {str(e)}")

def load_json(path: Path, silent: bool = False) -> Dict[str, Any]:
    """
    Load data from a JSON file.
    
    Args:
        path: Path to the JSON file
        silent: If True, return empty dict instead of raising FileNotFoundError
        
    Returns:
        The parsed JSON data as a dictionary
        
    Raises:
        FileNotFoundError: If the file doesn't exist and silent is False
        json.JSONDecodeError: If the file contains invalid JSON
        IOError: For file I/O related errors
        OSError: For operating system related errors
        
    Example:
        >>> from pathlib import Path
        >>> data = load_json(Path("config.json"))
        >>> # With silent mode
        >>> data = load_json(Path("missing.json"), silent=True)  # Returns {}
        >>> # Example JSON file content:
        >>> # {
        >>> #   "name": "John",
        >>> #   "age": 30,
        >>> #   "items": ["a", "b", "c"]
        >>> # }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if silent:
            return {}
        raise FileNotFoundError(f"JSON file not found at {path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in file {path}: {str(e)}", e.doc, e.pos)
    except IOError as e:
        raise IOError(f"Error reading JSON file {path}: {str(e)}")
    except OSError as e:
        raise OSError(f"System error while reading JSON file {path}: {str(e)}") 