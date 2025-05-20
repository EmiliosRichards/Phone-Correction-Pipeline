#!/usr/bin/env python3
"""
Script to initialize the project directory structure.
"""
import os
import sys
import argparse
from pathlib import Path
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_directory(path):
    """Create a directory if it doesn't exist."""
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True)
        logger.info(f"Created directory: {path}")
    else:
        logger.info(f"Directory already exists: {path}")

def create_data_structure(base_dir="."):
    """Create the data directory structure."""
    base_dir = Path(base_dir)
    
    # Create data directories
    create_directory(base_dir / "data" / "raw")
    create_directory(base_dir / "data" / "processed")
    create_directory(base_dir / "data" / "results")
    
    # Create logs directory
    create_directory(base_dir / "logs")
    
    # Create example scraping directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    example_dir = base_dir / "data" / "raw" / timestamp
    create_directory(example_dir)
    create_directory(example_dir / "pages" / "example_com")
    
    # Create example text file
    example_text_file = example_dir / "pages" / "example_com" / "text.txt"
    with open(example_text_file, 'w', encoding='utf-8') as f:
        f.write("""
Example website content for testing.

Contact Information:
Phone: +1 (234) 567-8900
Email: info@example.com
Address: 123 Main St, Anytown, USA
        """)
    logger.info(f"Created example text file: {example_text_file}")
    
    # Create example summary file
    summary_file = example_dir / "summary.json"
    summary_data = {
        "timestamp": timestamp,
        "websites_scraped": 1,
        "successful": 1,
        "failed": 0
    }
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2)
    logger.info(f"Created example summary file: {summary_file}")
    
    # Create example session log
    session_log_file = example_dir / "session.log"
    with open(session_log_file, 'w', encoding='utf-8') as f:
        f.write(f"""
[{timestamp}] INFO: Starting scraping session
[{timestamp}] INFO: Scraping example.com
[{timestamp}] INFO: Successfully scraped example.com
[{timestamp}] INFO: Scraping session completed
        """)
    logger.info(f"Created example session log: {session_log_file}")
    
    # Create example processed directory structure
    processed_dir = base_dir / "data" / "processed" / timestamp
    create_directory(processed_dir)
    create_directory(processed_dir / "pages" / "example_com")
    
    # Create example processed text file
    processed_text_file = processed_dir / "pages" / "example_com" / "text.txt"
    with open(processed_text_file, 'w', encoding='utf-8') as f:
        f.write("""
Example website content for testing (normalized).

Contact Information:
Phone: +1 234 567 8900
Email: info@example.com
Address: 123 Main St, Anytown, USA
        """)
    logger.info(f"Created example processed text file: {processed_text_file}")
    
    # Create example results directory
    results_dir = base_dir / "data" / "results" / timestamp
    create_directory(results_dir)
    
    logger.info("Project directory structure initialized successfully.")

def main():
    """Main function to initialize the project directory structure."""
    parser = argparse.ArgumentParser(description='Initialize the project directory structure.')
    parser.add_argument('--dir', type=str, default=".", help='Base directory for the project')
    
    args = parser.parse_args()
    
    try:
        create_data_structure(args.dir)
        return 0
    except Exception as e:
        logger.error(f"Error initializing project: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())