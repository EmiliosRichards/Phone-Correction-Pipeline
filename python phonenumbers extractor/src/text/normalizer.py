"""
Text normalization module for the Phone Extraction project.
This module processes text files and writes normalized versions to a processed directory
without modifying the original files.
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from src.text.utils import normalize_and_clean
from src.utils.logging_config import get_logger

# Get logger for this module
log = get_logger(__name__)

def process_scraped_texts(base_dir: str, output_dir: str = None) -> dict:
    """
    Process all text.txt files in the scraped data directory and normalize them.
    Writes normalized files to the processed directory WITHOUT modifying original files.
    Original files in the raw directory remain untouched.
    
    Args:
        base_dir: Base directory containing the scraped data
        output_dir: Optional output directory (if None, default directory will be used)
        
    Returns:
        Dictionary containing processing statistics
    """
    stats = {
        "total_files": 0,
        "processed_files": 0,
        "failed_files": [],
        "start_time": datetime.now().isoformat()
    }
    
    # Create timestamp for processed directory
    timestamp = Path(base_dir).name
    
    # Use custom output directory or default
    base_processed_dir = output_dir or os.environ.get('PROCESSED_DIR', "data/processed")
    
    # Create processed directory
    processed_dir = Path(f"{base_processed_dir}/{timestamp}")
    
    # Walk through all website directories
    for website_dir in Path(base_dir).glob("**/pages/*"):
        if not website_dir.is_dir():
            continue
            
        text_file = website_dir / "text.txt"
        if not text_file.exists():
            continue
            
        stats["total_files"] += 1
        
        try:
            log.debug(f"Processing text file: {text_file}")
            # Read the original text file
            with open(text_file, 'rb') as f:
                original_text = f.read()
            
            # Create a backup of the original file
            backup_file = text_file.with_suffix('.txt.bak')
            with open(backup_file, 'wb') as f:
                f.write(original_text)
            log.debug(f"Created backup file: {backup_file}")
            
            # Normalize and clean the text
            normalized_text = normalize_and_clean(original_text)
            
            # Create corresponding directory in processed folder
            website_name = website_dir.name
            processed_website_dir = processed_dir / "pages" / website_name
            processed_website_dir.mkdir(parents=True, exist_ok=True)
            
            # Write the normalized text to the processed directory
            processed_text_file = processed_website_dir / "text.txt"
            with open(processed_text_file, 'w', encoding='utf-8') as f:
                f.write(normalized_text)
            log.debug(f"Wrote normalized text to: {processed_text_file}")
                
            # Original files are preserved - no modification to source files
            
            stats["processed_files"] += 1
            log.info(f"Successfully processed file: {text_file}")
            
        except Exception as e:
            log.error(f"Failed to process file {text_file}: {e}", exc_info=True)
            stats["failed_files"].append({
                "file": str(text_file),
                "error": str(e)
            })
    
    stats["end_time"] = datetime.now().isoformat()
    return stats

def get_latest_scraping_dir() -> Path:
    """
    Get the most recent scraping directory.
    
    Returns:
        Path to the most recent scraping directory
    """
    data_dir = Path("data/raw")
    if not data_dir.exists():
        raise FileNotFoundError("No data/raw directory found!")
        
    # Find the most recent scraping directory
    scraping_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()],
                         key=lambda x: x.name,
                         reverse=True)
    
    if not scraping_dirs:
        raise FileNotFoundError("No scraping directories found in data/raw!")
        
    return scraping_dirs[0]

def normalize_latest_data(output_dir: str = None) -> dict:
    """
    Normalize the text data in the most recent scraping directory.
    
    Args:
        output_dir: Optional output directory (if None, default directory will be used)
        
    Returns:
        Dictionary containing processing statistics
    """
    latest_dir = get_latest_scraping_dir()
    log.info(f"Processing files in: {latest_dir}")
    
    # Process the files
    stats = process_scraped_texts(str(latest_dir), output_dir)
    
    # Create timestamp for processed directory
    timestamp = latest_dir.name
    base_processed_dir = output_dir or os.environ.get('PROCESSED_DIR', "data/processed")
    processed_dir = Path(f"{base_processed_dir}/{timestamp}")
    
    # Create processed directory if it doesn't exist
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Save processing statistics
    stats_file = processed_dir / "text_normalization_stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    # Print summary
    log.info("\nProcessing Summary:")
    log.info(f"Total files found: {stats['total_files']}")
    log.info(f"Successfully processed: {stats['processed_files']}")
    log.info(f"Failed files: {len(stats['failed_files'])}")
    if stats['failed_files']:
        log.warning("\nFailed files:")
        for failed in stats['failed_files']:
            log.warning(f"- {failed['file']}: {failed['error']}")
    
    return stats