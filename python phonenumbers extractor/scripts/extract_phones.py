#!/usr/bin/env python3
"""
Script to extract phone numbers from text files, store them locally,
and update a PostgreSQL database.
"""
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
import json
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.text.utils import normalize_and_clean # Assuming this is still needed for raw text
from src.phone.extractor import extract_phone_numbers
from src.analysis.statistics import generate_statistics as generate_stats_old, save_results, print_statistics
# ^ We might need to adapt generate_statistics or create a new one
from src.db.utils import get_db_connection, insert_raw_phone_number, upsert_cleaned_phone_number, update_scraping_log_error, get_client_id_by_url, get_log_id_by_url, get_page_id_by_url
from src.utils.logging_config import get_logger

# Get logger for this module
log = get_logger(__name__)

# --- Metadata Extraction ---
def get_metadata(text_file_path: Path, db_conn) -> Dict[str, Any]: # Added db_conn
    """
    Extracts metadata for a given text.txt file.
    Searches for client_id, page_id, log_id, url, source_page, scrape_run_timestamp.
    Attempts to fetch client_id from DB via URL in url.txt if not found in JSONs.
    """
    metadata = {
        "client_id": None,
        "page_id": None,
        "log_id": None,
        "url": None,
        "source_page": None,
        "scrape_run_timestamp": None,
        "text_file_path": str(text_file_path)
    }

    # Store data from JSON files temporarily for fallback
    json_client_id: Optional[str] = None
    json_log_id: Optional[Any] = None
    json_page_id: Optional[Any] = None
    page_data_url: Optional[str] = None
    page_data_source_page: Optional[str] = None

    try:
        # --- Part 1: Path Parsing & Initial URL/Source Page from JSON ---
        parts = text_file_path.parts
        log.debug(f"Path parts for metadata: {parts}")
        if len(parts) >= 5 and parts[-3].lower() == "pages" and parts[-5].lower() == "raw":
            metadata["scrape_run_timestamp_str"] = parts[-4]
            metadata["domain"] = parts[-2]
            metadata["source_page"] = metadata["domain"]
            log.info(f"Path parsed: timestamp='{metadata.get('scrape_run_timestamp_str')}', domain='{metadata.get('domain')}' for {text_file_path}")
            try:
                metadata["scrape_run_timestamp"] = datetime.strptime(metadata["scrape_run_timestamp_str"], "%Y%m%d_%H%M%S")
            except ValueError:
                log.warning(f"Could not parse scrape_run_timestamp '{metadata.get('scrape_run_timestamp_str')}' from path for {text_file_path}")
        else:
            log.warning(f"Could not parse standard path structure for metadata: {text_file_path}")

        page_metadata_path_text_json = text_file_path.with_suffix(".json")
        page_metadata_path_metadata_json = text_file_path.parent / "metadata.json"
        page_metadata_path_to_use = None

        if page_metadata_path_text_json.exists():
            page_metadata_path_to_use = page_metadata_path_text_json
        elif page_metadata_path_metadata_json.exists():
            page_metadata_path_to_use = page_metadata_path_metadata_json
        
        if page_metadata_path_to_use:
            log.info(f"Loading page metadata from: {page_metadata_path_to_use}")
            with open(page_metadata_path_to_use, 'r', encoding='utf-8') as f:
                page_data = json.load(f)
                page_data_url = page_data.get("url")
                page_data_source_page = page_data.get("source_page")
                
                json_page_id = page_data.get("page_id")
                json_log_id = page_data.get("log_id")
                json_client_id = page_data.get("client_id")

                if page_data_url:
                    metadata["url"] = page_data_url
                    log.info(f"URL '{metadata['url']}' loaded from {page_metadata_path_to_use.name}.")
                if page_data_source_page:
                    metadata["source_page"] = page_data_source_page
                    log.info(f"Source page '{metadata['source_page']}' loaded from {page_metadata_path_to_use.name}.")
                if json_page_id: log.debug(f"Found page_id '{json_page_id}' in {page_metadata_path_to_use.name} (for fallback).")
                if json_log_id: log.debug(f"Found log_id '{json_log_id}' in {page_metadata_path_to_use.name} (for fallback).")
                if json_client_id: log.debug(f"Found client_id '{json_client_id}' in {page_metadata_path_to_use.name} (for fallback).")
        else:
            log.warning(f"No page metadata file (e.g., text.json, metadata.json) found for {text_file_path}.")

        if not metadata.get("url") and metadata.get("domain"):
            url_txt_path = text_file_path.with_name("url.txt")
            if url_txt_path.exists():
                log.info(f"Attempting to read URL from {url_txt_path}.")
                try:
                    with open(url_txt_path, 'r', encoding='utf-8') as f:
                        url_from_file = f.read().strip()
                    if url_from_file:
                        metadata["url"] = url_from_file
                        log.info(f"URL '{metadata['url']}' loaded from {url_txt_path.name}.")
                    else:
                        log.warning(f"{url_txt_path.name} found but is empty.")
                except Exception as url_e:
                    log.error(f"Error reading or processing {url_txt_path}: {url_e}")
            else:
                log.debug(f"{url_txt_path.name} not found.")
        
        # --- Part 2: Database Lookups (Primary Source for IDs) ---
        if metadata.get("url") and db_conn:
            current_url_val = metadata["url"]
            url_for_db_lookup = None

            if isinstance(current_url_val, dict):
                url_for_db_lookup = current_url_val.get('parsed', current_url_val.get('original'))
                log.debug(f"Extracted string URL for DB lookup: {url_for_db_lookup} from dict {current_url_val}")
            elif isinstance(current_url_val, str):
                url_for_db_lookup = current_url_val
            
            if url_for_db_lookup:
                log.info(f"Attempting DB lookups for URL: {url_for_db_lookup}")
                
                client_id_from_db = get_client_id_by_url(db_conn, url_for_db_lookup)
                if client_id_from_db:
                    metadata["client_id"] = client_id_from_db
                    log.info(f"Sourced client_id '{metadata['client_id']}' from DB for URL '{url_for_db_lookup}'.")
                else:
                    log.info(f"client_id not found in DB for URL '{url_for_db_lookup}'. Will try fallbacks.")

                log_id_from_db = get_log_id_by_url(db_conn, url_for_db_lookup)
                if log_id_from_db:
                    metadata["log_id"] = log_id_from_db
                    log.info(f"Sourced log_id '{metadata['log_id']}' from DB for URL '{url_for_db_lookup}'.")
                else:
                    log.info(f"log_id not found in DB for URL '{url_for_db_lookup}'. Will try fallbacks.")

                page_id_from_db = get_page_id_by_url(db_conn, url_for_db_lookup)
                if page_id_from_db:
                    metadata["page_id"] = page_id_from_db
                    log.info(f"Sourced page_id '{metadata['page_id']}' from DB for URL '{url_for_db_lookup}'.")
                else:
                    log.info(f"page_id not found in DB for URL '{url_for_db_lookup}'. Will try fallbacks.")
            else:
                log.warning(f"URL for DB lookup could not be determined from: {current_url_val}. Skipping DB lookups.")
        else:
            if not metadata.get("url"):
                log.warning(f"URL could not be determined for {text_file_path}. Skipping DB lookups for IDs.")
            if not db_conn:
                log.warning(f"DB connection not available for {text_file_path}. Skipping DB lookups for IDs.")
        
        # --- Part 3: JSON Fallbacks (Secondary Source) ---
        if metadata["client_id"] is None and json_client_id is not None:
            metadata["client_id"] = json_client_id
            log.info(f"Using client_id '{metadata['client_id']}' from page JSON as fallback for {text_file_path}.")
        if metadata["log_id"] is None and json_log_id is not None:
            metadata["log_id"] = json_log_id
            log.info(f"Using log_id '{metadata['log_id']}' from page JSON as fallback for {text_file_path}.")
        if metadata["page_id"] is None and json_page_id is not None:
            metadata["page_id"] = json_page_id
            log.info(f"Using page_id '{metadata['page_id']}' from page JSON as fallback for {text_file_path}.")

        run_summary_path = text_file_path.parent.parent.parent / "summary.json"
        if (metadata["client_id"] is None or metadata["log_id"] is None) and run_summary_path.exists():
            log.info(f"Checking run summary for fallbacks: {run_summary_path}")
            with open(run_summary_path, 'r', encoding='utf-8') as f:
                run_summary_data = json.load(f)
                if metadata["client_id"] is None and run_summary_data.get("client_id") is not None:
                    metadata["client_id"] = run_summary_data.get("client_id")
                    log.info(f"Using client_id '{metadata['client_id']}' from run summary as fallback for {text_file_path}.")
                if metadata["log_id"] is None and run_summary_data.get("log_id") is not None:
                    metadata["log_id"] = run_summary_data.get("log_id")
                    log.info(f"Using log_id '{metadata['log_id']}' from run summary as fallback for {text_file_path}.")
        elif metadata["client_id"] is None or metadata["log_id"] is None:
             log.debug(f"Run summary not found or not needed for fallback: {run_summary_path}")

    except Exception as e:
        log.error(f"Error during metadata extraction for {text_file_path}: {e}", exc_info=True)

    # --- Part 4: Path-based Fallbacks for client_id (Tertiary) ---
    if not metadata["client_id"]:
        log.warning(f"client_id is still None after DB and JSON attempts for {text_file_path}. Attempting path-based fallbacks.")
        try:
            path_str = str(text_file_path)
            import re
            client_pattern = re.search(r'client[_\-]?(\w+)', path_str, re.IGNORECASE)
            if client_pattern:
                metadata["client_id"] = client_pattern.group(1)
                log.info(f"Path Fallback SUCCESS: Extracted client_id '{metadata['client_id']}' from path pattern.")
            elif metadata.get("domain"):
                metadata["client_id"] = f"domain-{metadata['domain']}"
                log.info(f"Path Fallback SUCCESS: Using domain as fallback client_id: {metadata['client_id']}")
            else:
                metadata["client_id"] = "unknown-client"
                log.warning(f"Path Fallback USED: Using default client_id '{metadata['client_id']}' as last resort for {text_file_path}")
        except Exception as path_fallback_e:
            log.error(f"Error during client_id path fallback: {path_fallback_e}")
            if not metadata["client_id"]:
                 metadata["client_id"] = "unknown-client-error"

    # --- Part 5: Final Checks & Logging ---
    if not metadata["url"]:
        log.warning(f"Final URL for {text_file_path} could not be determined.")
    if not metadata["log_id"]:
        log.warning(f"Final log_id for {text_file_path} could not be determined after all attempts.")
    if not metadata["page_id"]:
        log.warning(f"Final page_id for {text_file_path} could not be determined after all attempts.")
    if not metadata["client_id"]:
        log.error(f"CRITICAL: client_id for {text_file_path} is still None after all fallbacks. Setting to 'critical-unknown'.")
        metadata["client_id"] = "critical-unknown"

    log.info(f"Final metadata for {text_file_path}: client_id='{metadata.get('client_id')}', page_id='{metadata.get('page_id')}', log_id='{metadata.get('log_id')}', url='{metadata.get('url')}'")
    return metadata

# --- Website Directory Processing ---
def process_website_directory(website_dir: Path, use_twilio_validation: bool = False) -> Dict[str, Any]:
    """
    Process a website directory to extract phone numbers from its text files.
    
    Args:
        website_dir: Path to the website directory (e.g., data/raw/20250509_214446/pages/example_com)
        use_twilio_validation: Whether to use Twilio API for phone number validation
        
    Returns:
        Dictionary containing extraction results for the website:
        {
            'website': str,  # Website domain name
            'url': str,      # Website URL if available
            'client_id': str, # Client ID if available
            'numbers': List[Dict], # List of extracted phone numbers
            'error': str,    # Error message if any
        }
    """
    result = {
        'website': website_dir.name,
        'url': None,
        'client_id': None,
        'numbers': [],
        'error': None
    }
    
    try:
        # Find the text.txt file in the website directory
        text_file = website_dir / "text.txt"
        
        if not text_file.exists():
            result['error'] = f"Text file not found in {website_dir}"
            log.warning(result['error'])
            return result
            
        # Get database connection
        db_conn = None
        try:
            db_conn = get_db_connection()
        except Exception as e:
            log.warning(f"Failed to connect to database: {e}. Will continue without DB operations.")
            
        # Process the text file
        extracted_data, errors = process_text_file(text_file, db_conn)
        
        if errors:
            result['error'] = f"Errors during extraction: {'; '.join(errors[:3])}" + (
                f" and {len(errors) - 3} more errors" if len(errors) > 3 else ""
            )
            
        # Extract metadata from the first result if available
        if extracted_data:
            result['numbers'] = extracted_data
            # Get client_id and URL from the first extracted data item
            first_item = extracted_data[0]
            result['client_id'] = first_item.get('client_id')
            result['url'] = first_item.get('url')
            
        # Close DB connection if it was opened
        if db_conn:
            db_conn.close()
            
        return result
        
    except Exception as e:
        error_msg = f"Failed to process website directory {website_dir}: {str(e)}"
        log.error(error_msg, exc_info=True)
        result['error'] = error_msg
        return result

# --- File Processing ---
def process_text_file(text_file_path: Path, db_conn) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Processes a single text.txt file: extracts phone numbers, stores them in DB,
    and collects data for local saving.
    """
    extracted_phone_data_for_file: List[Dict[str, Any]] = []
    errors: List[str] = []
    file_metadata = get_metadata(text_file_path, db_conn) # Pass db_conn
    
    # Critical check for client_id
    if not file_metadata.get("client_id"):
        error_msg = f"Skipping DB operations for {text_file_path} due to missing client_id."
        log.error(error_msg)
        errors.append(error_msg)
        # We might still want to extract numbers for local JSON even if DB fails
        # For now, let's return early if client_id is missing for DB-centric flow.
        # return extracted_phone_data_for_file, errors # Option 1: skip entirely
    
    log_id_for_error_reporting = file_metadata.get("log_id")

    try:
        # Try to read from the processed directory first
        # Extract path components more robustly
        parts = Path(text_file_path).parts
        
        # Find the timestamp and domain in the path
        timestamp = None
        domain = None
        
        # Look for 'raw' in the path to locate the timestamp
        for i, part in enumerate(parts):
            if part == 'raw' and i+1 < len(parts):
                timestamp = parts[i+1]
                break
                
        # The domain is typically the directory containing the text.txt file
        if len(parts) >= 2:
            domain = parts[-2]
            
        if not timestamp or not domain:
            log.warning(f"Could not extract timestamp or domain from path: {text_file_path}")
            log.warning("Falling back to raw file with normalization")
            with open(text_file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            # Apply normalization since we're reading from raw file
            text_content = normalize_and_clean(raw_text)
        else:
            base_processed_dir = os.environ.get('PROCESSED_DIR', "data/processed")
            processed_dir = Path(f"{base_processed_dir}/{timestamp}")
            
            # Construct the path to the processed file
            processed_file_path = processed_dir / "pages" / domain / "text.txt"
        
            if processed_file_path.exists():
                with open(processed_file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                log.info(f"Reading normalized text from processed directory: {processed_file_path}")
            else:
                # Fall back to raw file with normalization
                log.warning(f"Processed file not found: {processed_file_path}")
                log.warning(f"Falling back to raw file with normalization: {text_file_path}")
                with open(text_file_path, 'r', encoding='utf-8') as f:
                    raw_text = f.read()
                # Apply normalization since we're reading from raw file
                text_content = normalize_and_clean(raw_text)
        
        # Default region can be a parameter or from config
        phone_numbers = extract_phone_numbers(text_content, default_region='DE') 

        log.info(f"Found {len(phone_numbers)} potential numbers in {text_file_path}.")

        for number_info in phone_numbers:
            # Prepare data for DB and local JSON
            data_to_store = {
                "client_id": file_metadata.get("client_id"),
                "page_id": file_metadata.get("page_id"),
                "log_id": file_metadata.get("log_id"),
                "phone_number": number_info.get("e164"),
                "url": file_metadata.get("url"),
                "source_page": file_metadata.get("source_page"), # e.g., domain or specific page type
                "scrape_run_timestamp": file_metadata.get("scrape_run_timestamp"),
                "notes": f"Original: {number_info.get('original')}", # Example note
                "confidence_score": number_info.get("confidence_score", 0.0),
                "raw_text_file_path": str(text_file_path), # For local record
                "extraction_details": number_info # Full details from extractor
            }
            
            # Ensure required fields for DB are present
            if not data_to_store["client_id"] or not data_to_store["phone_number"]:
                error_msg = f"Skipping DB insert for number {data_to_store['phone_number']} from {text_file_path} due to missing client_id or phone_number."
                log.error(error_msg)
                errors.append(error_msg)
                extracted_phone_data_for_file.append(data_to_store) # Still save locally
                continue

            try:
                raw_phone_id = insert_raw_phone_number(db_conn, data_to_store)
                # Pass data_to_store which has all necessary fields for upsert
                upsert_cleaned_phone_number(db_conn, data_to_store) 
                log.info(f"Successfully processed and stored number: {data_to_store['phone_number']} from {text_file_path}")
            except Exception as db_e:
                error_msg = f"DB error for {data_to_store['phone_number']} from {text_file_path}: {db_e}"
                log.error(error_msg, exc_info=True)
                errors.append(error_msg)
                if log_id_for_error_reporting:
                    try:
                        update_scraping_log_error(db_conn, log_id_for_error_reporting, f"Phone extraction DB error: {db_e}")
                    except Exception as log_update_e:
                        log.error(f"Failed to update scraping_log with error: {log_update_e}")
            
            extracted_phone_data_for_file.append(data_to_store)

    except Exception as e:
        error_msg = f"Failed to process file {text_file_path}: {e}"
        log.error(error_msg, exc_info=True)
        errors.append(error_msg)
        if log_id_for_error_reporting:
            try:
                update_scraping_log_error(db_conn, log_id_for_error_reporting, f"Phone extraction file processing error: {e}")
            except Exception as log_update_e:
                log.error(f"Failed to update scraping_log with error: {log_update_e}")
                
    return extracted_phone_data_for_file, errors

# --- Statistics Generation (New/Adapted) ---
def generate_run_statistics(all_phone_data: List[Dict[str, Any]], file_processing_errors: Dict[str, List[str]]) -> Dict[str, Any]:
    """Generates statistics for the entire extraction run."""
    total_files_processed = len(set(item['raw_text_file_path'] for item in all_phone_data)) + len(file_processing_errors)
    # Note: total_files_processed might double count if a file has an error AND extracts some numbers.
    # A more accurate count of files attempted would be from the initial glob. This is files that produced data or errors.

    stats = {
        "run_timestamp": datetime.now().isoformat(),
        "total_text_files_attempted": 0, # This should be set by main after globbing
        "total_text_files_with_data_or_errors": total_files_processed,
        "total_phone_numbers_extracted": len(all_phone_data),
        "extraction_errors_count": sum(len(e) for e in file_processing_errors.values()),
        "numbers_by_client": defaultdict(int),
        "files_processed_by_client": defaultdict(lambda: defaultdict(int)), # client -> filepath -> count
        "detailed_errors": file_processing_errors
    }

    for item in all_phone_data:
        client_id = item.get("client_id", "UnknownClient")
        stats["numbers_by_client"][client_id] += 1
        stats["files_processed_by_client"][client_id][item['raw_text_file_path']] = 1 # Mark file as processed for this client

    stats["numbers_by_client"] = dict(stats["numbers_by_client"])
    stats["files_processed_by_client"] = {
        client: len(files.keys()) for client, files in stats["files_processed_by_client"].items()
    }
    
    return stats

# --- Main Orchestration ---
def main():
    """Main function to orchestrate phone number extraction and processing."""
    parser = argparse.ArgumentParser(description='Extract phone numbers from text files and update database.')
    parser.add_argument(
        '--input_dir', 
        type=str, 
        help='Specific timestamped directory within data/raw/ (e.g., "20250509_214446"). If not provided, processes the latest.'
    )
    parser.add_argument(
        '--data_path',
        type=str,
        default="data/raw",
        help="Base directory for raw data (default: data/raw)"
    )
    
    args = parser.parse_args()

    run_processing_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info(f"Starting phone extraction run: {run_processing_timestamp}")

    base_raw_data_dir = Path(args.data_path)
    if not base_raw_data_dir.exists():
        log.error(f"Base raw data directory not found: {base_raw_data_dir}")
        return 1

    processing_target_dir: Optional[Path] = None
    if args.input_dir:
        processing_target_dir = base_raw_data_dir / args.input_dir
        if not processing_target_dir.is_dir():
            log.error(f"Specified input directory not found: {processing_target_dir}")
            return 1
    else:
        # Find the most recent directory in data/raw
        subdirs = sorted([d for d in base_raw_data_dir.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
        if not subdirs:
            log.error(f"No timestamped directories found in {base_raw_data_dir}")
            return 1
        processing_target_dir = subdirs[0]
    
    log.info(f"Processing data from: {processing_target_dir}")

    # Find all text.txt files in the processed directory
    # Create the corresponding processed directory path
    timestamp = processing_target_dir.name
    base_processed_dir = os.environ.get('PROCESSED_DIR', "data/processed")
    processed_dir = Path(f"{base_processed_dir}/{timestamp}")
    
    if not processed_dir.exists():
        log.warning(f"Processed directory not found: {processed_dir}")
        log.warning("Make sure to run text normalization before extraction.")
        # Create empty results if needed, or just exit.
        all_extracted_phone_data: List[Dict[str, Any]] = []
        overall_errors: Dict[str, List[str]] = {}
        num_files_attempted = 0
        return 1
    
    text_files_to_process = list(processed_dir.glob("**/pages/*/text.txt"))
    if not text_files_to_process:
        log.warning(f"No text.txt files found in {processed_dir} matching the pattern '**/pages/*/text.txt'.")
        # Create empty results if needed, or just exit.
        # For now, let's create empty results.
        all_extracted_phone_data: List[Dict[str, Any]] = []
        overall_errors: Dict[str, List[str]] = {}
        num_files_attempted = 0
    else:
        num_files_attempted = len(text_files_to_process)
        log.info(f"Found {num_files_attempted} text.txt files to process.")

        all_extracted_phone_data: List[Dict[str, Any]] = []
        overall_errors: Dict[str, List[str]] = defaultdict(list) # Store errors per file path

        db_conn = None
        try:
            db_conn = get_db_connection()
            if not db_conn:
                log.error("Failed to connect to the database. Aborting DB operations.")
                # Decide if script should continue for local JSON saving or exit.
                # For now, it will continue and local JSON will be saved, but DB ops will be skipped.
            
            for text_file in text_files_to_process:
                log.info(f"Processing file: {text_file}")
                if db_conn: # Only attempt processing if DB connection was successful
                    phone_data_for_file, errors_for_file = process_text_file(text_file, db_conn)
                    all_extracted_phone_data.extend(phone_data_for_file)
                    if errors_for_file:
                        overall_errors[str(text_file)].extend(errors_for_file)
                else:
                    # Simulate extraction if no DB for local saving, or just log skip
                    log.warning(f"Skipping processing of {text_file} due to DB connection failure.")
                    overall_errors[str(text_file)].append("Skipped due to DB connection failure.")


        except Exception as e:
            log.error(f"An unexpected error occurred during main processing: {e}", exc_info=True)
            # Potentially add this as a general error to overall_errors
        finally:
            if db_conn:
                db_conn.close()
                log.info("Database connection closed.")

    # Generate statistics for the run
    run_stats = generate_run_statistics(all_extracted_phone_data, dict(overall_errors))
    run_stats["total_text_files_attempted"] = num_files_attempted # Add actual count of files globbed

    # Save results locally
    try:
        # Convert datetime objects in all_extracted_phone_data to ISO strings for JSON serialization
        for item in all_extracted_phone_data:
            if "scrape_run_timestamp" in item and isinstance(item["scrape_run_timestamp"], datetime):
                item["scrape_run_timestamp"] = item["scrape_run_timestamp"].isoformat()
            # If 'extraction_details' might contain datetime, handle it here too.
            # Example:
            # if "extraction_details" in item and isinstance(item["extraction_details"], dict):
            #     for key, value in item["extraction_details"].items():
            #         if isinstance(value, datetime):
            #             item["extraction_details"][key] = value.isoformat()

        # Adapt run_stats to match the format expected by save_results
        adapted_stats = {
            'total_websites': run_stats['total_text_files_attempted'],
            'websites_with_numbers': len([item for item in all_extracted_phone_data if item.get('phone_number')]),
            'total_numbers_found': run_stats['total_phone_numbers_extracted'],
            'format_counts': {},  # We don't track this in our new structure
            'country_codes': {},  # We don't track this in our new structure
            'errors': [],  # We handle errors differently
            'results': all_extracted_phone_data # now with datetime converted to string
        }
        
        output_paths = save_results(
            stats_summary=adapted_stats,
            timestamp=run_processing_timestamp # Use the run's timestamp
        )
        log.info(f"All extracted phone numbers saved to: {output_paths['phone_numbers']}")
        log.info(f"Run statistics saved to: {output_paths['statistics']}")
        
        # Print statistics to console (optional, can be verbose)
        # print_statistics(run_stats) # The old print_statistics might not fit the new stats structure well.
        log.info("--- Run Summary ---")
        log.info(f"Timestamp: {run_stats['run_timestamp']}") # This is already a string from an earlier strftime
        log.info(f"Files Attempted: {run_stats['total_text_files_attempted']}")
        log.info(f"Total Phone Numbers Extracted: {run_stats['total_phone_numbers_extracted']}")
        log.info(f"Extraction Errors Count: {run_stats['extraction_errors_count']}")
        # Ensure numbers_by_client is serializable (should be if keys/values are basic types)
        log.info(f"Numbers by Client: {json.dumps(run_stats['numbers_by_client'], indent=2)}")

    except Exception as e:
        log.error(f"Failed to save results or print statistics: {e}", exc_info=True)
        return 1
    
    log.info(f"Phone extraction run {run_processing_timestamp} completed.")
    if run_stats['extraction_errors_count'] > 0:
        log.warning("There were errors during the extraction process. Check logs and statistics.json for details.")
        return 1 # Indicate partial success or failure
        
    return 0

if __name__ == "__main__":
    sys.exit(main())