#!/usr/bin/env python3
"""
Main entry point for the Phone Extraction project.
This script runs the entire pipeline: normalize text, extract phone numbers, and analyze results.
"""
import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import project modules
from src.text.normalizer import normalize_latest_data, get_latest_scraping_dir
from src.text.utils import normalize_and_clean
from src.phone.extractor import extract_phone_numbers
from src.phone.formatter import format_phone_number
from src.analysis.statistics import generate_statistics, save_results, print_statistics
from scripts.export_phone_numbers_to_excel import generate_phone_numbers_excel_report

def run_normalization(args):
    """Run the text normalization step."""
    logger.info("Starting text normalization...")
    
    try:
        if args.dir:
            # Use specified directory
            data_dir = Path(args.dir)
            if not data_dir.exists():
                logger.error(f"Directory {data_dir} does not exist!")
                return None
                
            logger.info(f"Processing files in: {data_dir}")
            from src.text.normalizer import process_scraped_texts
            stats = process_scraped_texts(str(data_dir))
        else:
            # Use latest directory
            stats = normalize_latest_data()
        
        logger.info(f"Successfully processed {stats['processed_files']} out of {stats['total_files']} files.")
        logger.info(f"Normalized files written to data/processed/{Path(args.dir if args.dir else get_latest_scraping_dir()).name}")
        return stats
        
    except Exception as e:
        logger.error(f"Error during normalization: {str(e)}")
        return None

def run_extraction(args, scraping_dir=None, use_twilio_validation=False):
    """Run the phone number extraction step."""
    logger.info("Starting phone number extraction...")
    if use_twilio_validation:
        logger.info("Twilio validation is ENABLED.")
    else:
        logger.info("Twilio validation is DISABLED.")
    
    try:
        # Determine the scraping directory to process
        if scraping_dir:
            pass  # Use the provided directory
        elif args.dir:
            scraping_dir = Path(args.dir)
        else:
            # Find the most recent scraping directory
            scraping_dir = get_latest_scraping_dir()
        
        logger.info(f"Extracting phone numbers from raw directory: {scraping_dir}")
        logger.info(f"Using normalized text from processed directory: data/processed/{scraping_dir.name}")
        
        # Process each website's text file
        results = []
        errors = []
        
        # Import the necessary function
        from scripts.extract_phones import process_website_directory
        
        # Process each website directory
        website_dirs = list(scraping_dir.glob("**/pages/*"))
        logger.info(f"Found {len(website_dirs)} website directories to process.")
        
        for i, website_dir in enumerate(website_dirs):
            if not website_dir.is_dir():
                continue
            
            if i % 10 == 0:
                logger.info(f"Processing website {i+1}/{len(website_dirs)}...")

            # Pass the use_twilio_validation flag to process_website_directory
            result = process_website_directory(website_dir, use_twilio_validation=use_twilio_validation)
            if result:
                if 'error' in result:
                    errors.append({
                        'website': result['website'],
                        'error': result['error']
                    })
                results.append(result)
        
        # Generate statistics
        stats = generate_statistics(results) # 'results' here is a list of dicts, potentially with datetime objects
        stats['errors'] = errors
        
        # Convert datetime objects in stats['results'] before saving
        # This is crucial because generate_statistics simply passes the 'results' list along.
        if 'results' in stats and isinstance(stats['results'], list):
            for website_result in stats['results']:
                # Each website_result is a dictionary that might come from process_website_directory
                # It might contain 'numbers', and each number dict might have 'scrape_run_timestamp'
                if 'numbers' in website_result and isinstance(website_result['numbers'], list):
                    for number_entry in website_result['numbers']:
                        if isinstance(number_entry, dict) and \
                           "scrape_run_timestamp" in number_entry and \
                           isinstance(number_entry["scrape_run_timestamp"], datetime):
                            number_entry["scrape_run_timestamp"] = number_entry["scrape_run_timestamp"].isoformat()
                # Also, the top-level website_result itself might have a timestamp if added by process_website_directory
                # However, based on current process_website_directory, timestamps are inside the 'numbers' list items.
                # If process_website_directory were to add a 'scrape_run_timestamp' to its direct output, handle here:
                # if "scrape_run_timestamp" in website_result and isinstance(website_result["scrape_run_timestamp"], datetime):
                #     website_result["scrape_run_timestamp"] = website_result["scrape_run_timestamp"].isoformat()


        # Save results
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S") # Renamed to avoid conflict with datetime module
        output_files = save_results(stats, timestamp_str) # stats should now be serializable
        
        logger.info(f"Extraction complete. Found {stats['total_numbers_found']} phone numbers in {stats['websites_with_numbers']} websites.")
        logger.info(f"Results saved to: {output_files['json']}")
        
        return stats, output_files
        
    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        return None, None

def run_analysis(args, stats=None, results_file=None):
    """Run the analysis step."""
    logger.info("Starting analysis...")
    
    try:
        # If stats are provided, use them directly
        if stats:
            logger.info("Using provided statistics for analysis.")
        # Otherwise, load from file
        elif results_file:
            logger.info(f"Loading results from: {results_file}")
            with open(results_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        # Or find the most recent results file
        else:
            # Import the necessary function
            from scripts.analyze_results import load_results
            
            if args.file:
                results_file = Path(args.file)
            else:
                # Find the most recent results file
                results_dir = Path("data/results")
                if not results_dir.exists():
                    logger.error("No results directory found!")
                    return None
                    
                # Find all JSON files in the results directory and its subdirectories
                json_files = list(results_dir.glob("**/phone_numbers.json"))
                
                if not json_files:
                    logger.error("No results files found!")
                    return None
                    
                # Sort by modification time (most recent first)
                results_file = sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            
            logger.info(f"Loading results from: {results_file}")
            stats = load_results(results_file)
        
        # Print statistics
        print_statistics(stats)
        
        # Perform additional analyses
        from scripts.analyze_results import analyze_country_distribution, analyze_format_distribution
        analyze_country_distribution(stats)
        analyze_format_distribution(stats)
        
        logger.info("Analysis complete.")
        return stats
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        return None

def main():
    """Main function to run the entire pipeline."""
    parser = argparse.ArgumentParser(description='Phone Extraction Pipeline')
    parser.add_argument('--dir', type=str, help='Directory containing scraped data (default: latest)')
    parser.add_argument('--file', type=str, help='JSON file containing extraction results (for analysis only)')
    parser.add_argument('--skip-normalize', action='store_true', help='Skip the normalization step')
    parser.add_argument('--skip-extract', action='store_true', help='Skip the extraction step')
    parser.add_argument('--skip-analyze', action='store_true', help='Skip the analysis step')
    parser.add_argument('--use-twilio', action='store_true', help='Enable Twilio API for phone number validation (requires .env setup)')

    args = parser.parse_args()
    
    try:
        # Create necessary directories if they don't exist
        Path("logs").mkdir(exist_ok=True)
        Path("data/processed").mkdir(parents=True, exist_ok=True)
        Path("data/results").mkdir(parents=True, exist_ok=True)
        
        logger.info("Starting Phone Extraction Pipeline...")
        
        # Step 1: Normalize text
        norm_stats = None
        if not args.skip_normalize:
            norm_stats = run_normalization(args)
            if norm_stats is None:
                logger.error("Normalization failed. Exiting pipeline.")
                return 1
        else:
            logger.info("Skipping normalization step.")
        
        # Step 2: Extract phone numbers
        extraction_stats = None
        output_files = None
        if not args.skip_extract:
            # Pass the use_twilio flag to run_extraction
            extraction_stats, output_files = run_extraction(args, use_twilio_validation=args.use_twilio)
            if extraction_stats is None:
                logger.error("Extraction failed. Exiting pipeline.")
                return 1
        else:
            logger.info("Skipping extraction step.")

        # Step 3: Generate Excel Report (after successful extraction)
        if not args.skip_extract and extraction_stats is not None: # Only run if extraction was attempted and successful
            logger.info("Starting Excel report generation...")
            try:
                report_path = generate_phone_numbers_excel_report()
                if report_path:
                    logger.info(f"Excel report generated successfully: {report_path}")
                else:
                    logger.warning("Excel report generation did not produce a file path, but no error was raised.")
            except Exception as report_err:
                logger.error(f"Failed to generate Excel report: {report_err}", exc_info=True)
                # Do not exit pipeline, just log the error
        elif args.skip_extract:
            logger.info("Skipping Excel report generation because extraction was skipped.")
        else: # extraction_stats is None, meaning extraction failed
            logger.info("Skipping Excel report generation because extraction failed.")

        # Step 4: Analyze results
        if not args.skip_analyze:
            results_file = args.file
            if output_files and 'json' in output_files:
                results_file = output_files['json']
                
            analysis_stats = run_analysis(args, extraction_stats, results_file)
            if analysis_stats is None:
                logger.error("Analysis failed.")
                return 1
        else:
            logger.info("Skipping analysis step.")
        
        logger.info("Pipeline completed successfully.")
        return 0
        
    except Exception as e:
        logger.error(f"Error in pipeline: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())