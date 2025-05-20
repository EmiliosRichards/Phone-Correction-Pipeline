#!/usr/bin/env python3
"""
Utility script to clean up files generated during tests.
"""
import shutil
import argparse
from pathlib import Path

def cleanup(dry_run=False):
    """
    Clean up files generated during tests.
    
    Args:
        dry_run: If True, only print what would be removed without actually removing
    """
    # Define patterns for test-generated files
    test_patterns = [
        # Timestamp directories in results
        {"path": "data/results", "pattern": lambda p: p.is_dir() and p.name.startswith("202")},
        # Timestamp directories in processed
        {"path": "data/processed", "pattern": lambda p: p.is_dir() and p.name.startswith("202")},
        # Temporary directories in processed
        {"path": "data/processed", "pattern": lambda p: p.is_dir() and p.name.startswith("tmp")},
        # Log files from tests
        {"path": "logs", "pattern": lambda p: p.is_file() and p.suffix == '.log' and 'test' in p.name}
    ]
    
    # Process each pattern
    for pattern in test_patterns:
        base_path = Path(pattern["path"])
        if not base_path.exists():
            continue
            
        for item in base_path.iterdir():
            if pattern["pattern"](item):
                if dry_run:
                    print(f"Would remove: {item}")
                else:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    print(f"Removed: {item}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Clean up test-generated files.')
    parser.add_argument('--dry-run', action='store_true', help='Only print what would be removed without actually removing')
    args = parser.parse_args()
    
    cleanup(args.dry_run)

if __name__ == "__main__":
    main()