import pandas as pd
from typing import List, Dict, Set, Optional, Any, Callable, Union, Tuple
from src.data_handler import load_and_preprocess_data
from src.scraper import scrape_website
from src.regex_extractor_component import extract_numbers_with_snippets_from_text
from src.llm_extractor_component import GeminiLLMExtractor
from src.core.schemas import PhoneNumberLLMOutput # LLMExtractionResult not directly used for typing here
from src.scraper.scraper_logic import normalize_url
from src.core.logging_config import setup_logging
from src.core.config import AppConfig
import logging
import os
import asyncio
from datetime import datetime
import time
import json
import re
from urllib.parse import urlparse, quote
import phonenumbers
from phonenumbers import NumberParseException
from openpyxl.utils import get_column_letter

TARGET_COUNTRY_CODES_INT: Set[int] = {49, 41, 43} # Germany, Switzerland, Austria
logger = logging.getLogger(__name__) # Will be configured by setup_logging in main()
app_config: AppConfig = AppConfig()

INPUT_FILE_PATH: str = app_config.input_excel_file_path
if not os.path.isabs(INPUT_FILE_PATH):
    project_root_dir = os.path.dirname(os.path.abspath(__file__))
    INPUT_FILE_PATH = os.path.join(project_root_dir, INPUT_FILE_PATH)
    # Initial log before full setup might go to default console
    print(f"INFO: Resolved relative INPUT_FILE_PATH to absolute: {INPUT_FILE_PATH}")


def is_target_country_number_reliable(phone_number_str: str) -> bool:
    if not phone_number_str or not isinstance(phone_number_str, str):
        return False
    try:
        parsed_num = phonenumbers.parse(phone_number_str, None)
        return parsed_num.country_code in TARGET_COUNTRY_CODES_INT
    except NumberParseException:
        logger.debug(f"NumberParseException for '{phone_number_str}' during target country check.")
        return False

def generate_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def main() -> None:
    run_id = generate_run_id()
    
    output_base_dir_abs: str = app_config.output_base_dir
    if not os.path.isabs(output_base_dir_abs):
        project_root_dir_local = os.path.dirname(os.path.abspath(__file__))
        output_base_dir_abs = os.path.join(project_root_dir_local, output_base_dir_abs)
        
    run_output_dir: str = os.path.join(output_base_dir_abs, run_id)
    os.makedirs(run_output_dir, exist_ok=True)
    
    intermediate_data_dir = os.path.join(run_output_dir, "intermediate_data")
    os.makedirs(intermediate_data_dir, exist_ok=True)
    llm_context_dir = os.path.join(run_output_dir, app_config.llm_context_subdir)
    os.makedirs(llm_context_dir, exist_ok=True)
    
    # Scraper creates: run_output_dir / scraped_content / individual_pages_raw_text /
    # And: run_output_dir / scraped_content / cleaned_pages_text /

    log_file_name = f"pipeline_run_{run_id}.log"
    log_file_path = os.path.join(run_output_dir, log_file_name)
    
    file_log_level_int = getattr(logging, app_config.log_level.upper(), logging.INFO)
    console_log_level_int = getattr(logging, app_config.console_log_level.upper(), logging.WARNING)
    # ---- START DEBUG PRINT ----
    print(f"DEBUG: main_pipeline.py - Effective console_log_level_int: {console_log_level_int} ({logging.getLevelName(console_log_level_int)})")
    print(f"DEBUG: main_pipeline.py - AppConfig console_log_level raw value: '{app_config.console_log_level}'")
    # ---- END DEBUG PRINT ----
    setup_logging(
        file_log_level=file_log_level_int,
        console_log_level=console_log_level_int,
        log_file_path=log_file_path
    )
    
    logger.info(f"Logging initialized. Run ID: {run_id}")
    logger.info(f"File log level set to: {logging.getLevelName(file_log_level_int)} (from LOG_LEVEL='{app_config.log_level}')")
    logger.info(f"Console log level set to: {logging.getLevelName(console_log_level_int)} (from CONSOLE_LOG_LEVEL='{app_config.console_log_level}')")
    logger.info(f"Main log file will be: {log_file_path}")
    logger.info(f"Base output directory for this run: {run_output_dir}")

    logger.info("Starting phone validation pipeline...")
    if not os.path.exists(INPUT_FILE_PATH):
        logger.error(f"CRITICAL: Input file not found at resolved path: {INPUT_FILE_PATH}. Exiting.")
        return

    llm_extractor: GeminiLLMExtractor
    try:
        llm_extractor = GeminiLLMExtractor(config=app_config)
        logger.info("GeminiLLMExtractor initialized successfully.")
    except ValueError as ve:
        logger.error(f"Failed to initialize GeminiLLMExtractor: {ve}. Check GEMINI_API_KEY.")
        return
    except Exception as e:
        logger.error(f"Unexpected error initializing GeminiLLMExtractor: {e}", exc_info=True)
        return

    df: Optional[pd.DataFrame] = None
    try:
        logger.info(f"Attempting to load data from: {INPUT_FILE_PATH}")
        df = load_and_preprocess_data(INPUT_FILE_PATH, app_config_instance=app_config)
        if df is not None:
            logger.info(f"Successfully loaded and preprocessed data from {INPUT_FILE_PATH}. Shape: {df.shape}")
            logger.info(f"DataFrame columns: {df.columns.tolist()}") # Log column names
            if 'GivenURL' in df.columns:
                logger.info(f"First 5 'GivenURL' values: {df['GivenURL'].head().tolist()}")
            else:
                logger.warning("'GivenURL' column not found in the loaded DataFrame.")
                logger.info(f"First 2 rows of loaded DataFrame for inspection:\n{df.head(2).to_string()}")
            logger.debug(f"Loaded DataFrame head:\n{df.head().to_string()}")
        else:
            logger.error(f"Failed to load data from {INPUT_FILE_PATH}. DataFrame is None.")
            return
    except Exception as e:
        logger.error(f"Error loading data in main: {e}", exc_info=True)
        return

    if df is None:
        logger.error("DataFrame is None after loading attempt, cannot proceed.")
        return
    assert df is not None, "DataFrame loading failed."

    required_cols: Dict[str, Any] = {
        'ScrapingStatus': '',
        'RegexCandidateSnippets': lambda: [[] for _ in range(len(df))],
        'TargetCountryCodes': lambda: [[] for _ in range(len(df))],
        'VerificationStatus': '',
        'BestMatchedPhoneNumbers': lambda: [[] for _ in range(len(df))],
        'OtherRelevantNumbers': lambda: [[] for _ in range(len(df))],
        'ConfidenceScore': None,
        'LLMExtractedNumbers': lambda: [[] for _ in range(len(df))],
        'LLMContextPath': '',
        'Notes': ''
    }
    for col, default_val in required_cols.items():
        if col not in df.columns:
            df[col] = default_val() if callable(default_val) else default_val

    globally_processed_urls: Set[str] = set() # Initialize the global set
    all_flattened_rows: List[Dict[str, Any]] = [] # For the detailed flattened report
    canonical_site_llm_results: Dict[str, List[PhoneNumberLLMOutput]] = {}
    canonical_site_scraper_status: Dict[str, str] = {}
    input_to_canonical_map: Dict[str, Optional[str]] = {}

    for i, (index, row_series) in enumerate(df.iterrows()):
        row: pd.Series = row_series
        company_name: str = str(row.get('CompanyName', f"Row_{index}"))
        given_url_original: Optional[str] = row.get('GivenURL')
        current_row_number_for_log: int = i + 1
        
        logger.info(f"--- Processing row {current_row_number_for_log}/{len(df)}: Company '{company_name}', Original URL '{given_url_original}' ---")

        # Initialize per-row status variables
        current_row_scraper_status: str = "Not_Run"
        current_row_verification_status: str = "Uninitialized"
        current_row_best_matched_numbers: List[str] = []
        current_row_other_relevant_numbers: List[str] = []
        current_row_confidence_score: Optional[str] = None
        current_row_llm_context_path: str = ""
        current_row_llm_extracted_numbers: List[Dict[str, Any]] = []
        current_row_regex_candidate_snippets: List[Dict[str, str]] = []
        
        given_url_original_str_key = str(given_url_original) if given_url_original is not None else "None_GivenURL_Input"
        processed_url = given_url_original # Start with original

        try:
            if given_url_original and isinstance(given_url_original, str):
                # URL sanitization (remove spaces, ensure scheme)
                temp_url_stripped = given_url_original.strip()
                
                # Initial parse of the (potentially schemeless) stripped URL
                parsed_obj = urlparse(temp_url_stripped)

                # Extract components
                current_scheme = parsed_obj.scheme
                current_netloc = parsed_obj.netloc
                current_path = parsed_obj.path
                current_params = parsed_obj.params
                current_query = parsed_obj.query
                current_fragment = parsed_obj.fragment

                # If schemeless, the host and path might be muddled.
                # e.g., urlparse("example.com/path") -> scheme='', netloc='', path='example.com/path'
                # We need to add a scheme and re-parse to correctly separate netloc from path.
                if not current_scheme:
                    logger.info(f"URL '{temp_url_stripped}' is schemeless. Adding 'http://' and re-parsing.")
                    temp_for_reparse_schemeless = "http://" + temp_url_stripped
                    parsed_obj_schemed = urlparse(temp_for_reparse_schemeless)
                    
                    current_scheme = parsed_obj_schemed.scheme # Should be 'http'
                    current_netloc = parsed_obj_schemed.netloc
                    current_path = parsed_obj_schemed.path
                    current_params = parsed_obj_schemed.params # Re-assign from new parse
                    current_query = parsed_obj_schemed.query   # Re-assign
                    current_fragment = parsed_obj_schemed.fragment # Re-assign
                    logger.debug(f"After adding scheme: N='{current_netloc}', P='{current_path}'")

                # Handle spaces in netloc (domain) by removing them
                if " " in current_netloc:
                    logger.warning(f"Spaces found in domain part '{current_netloc}' for {company_name}. Removing them.")
                    current_netloc = current_netloc.replace(" ", "")
                
                # Percent-encode path, query, and fragment components safely
                # `safe` parameter ensures existing percent-encodings and specified chars are not re-encoded.
                current_path = quote(current_path, safe='/%')
                current_query = quote(current_query, safe='=&/?+%')
                current_fragment = quote(current_fragment, safe='/?#%')

                # Append .de TLD if necessary (logic from original code)
                if current_netloc and not re.search(r'\.[a-zA-Z]{2,}$', current_netloc) and not current_netloc.endswith('.'):
                    is_ip_address = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", current_netloc)
                    if current_netloc.lower() != 'localhost' and not is_ip_address:
                        logger.info(f"Appending .de to netloc '{current_netloc}' for {company_name}")
                        current_netloc += ".de"
                
                # Reconstruct the final URL
                # Ensure path is at least '/' if it's empty and there's a netloc, otherwise urlunparse might omit it.
                effective_path = current_path if current_path else ('/' if current_netloc else '')

                processed_url = urlparse('')._replace(
                    scheme=current_scheme,
                    netloc=current_netloc,
                    path=effective_path,
                    params=current_params,
                    query=current_query,
                    fragment=current_fragment
                ).geturl()

                if processed_url != given_url_original: # Compare with original, not just stripped
                    logger.info(f"URL pre-processed: Original='{given_url_original}', Processed='{processed_url}'")
            
            if not processed_url or not isinstance(processed_url, str) or not processed_url.startswith(('http://', 'https://')):
                logger.warning(f"Skipping row {current_row_number_for_log} due to invalid or missing URL after processing: {processed_url} (Original was: '{given_url_original}')")
                df.at[index, 'ScrapingStatus'] = 'InvalidURL'
                current_row_scraper_status = 'InvalidURL'
                df.at[index, 'VerificationStatus'] = 'Skipped_InvalidURL'
                continue

            scraped_pages_details: List[Tuple[str, str]]
            scraper_status: str
            final_canonical_entry_url: Optional[str] = None # Initialize for this scope
            
            scraped_pages_details, scraper_status, final_canonical_entry_url = asyncio.run(
                scrape_website(processed_url, run_output_dir, company_name, globally_processed_urls)
            )
            df.at[index, 'ScrapingStatus'] = scraper_status
            df.at[index, 'CanonicalEntryURL'] = final_canonical_entry_url # Store it
            current_row_scraper_status = scraper_status # Keep for local logging within this iteration
            given_url_original_str_key = str(given_url_original) if given_url_original is not None else "None_GivenURL_Input" # Ensure it's defined for the current row
            input_to_canonical_map[given_url_original_str_key] = final_canonical_entry_url

            logger.info(f"Row {current_row_number_for_log} ({company_name}): Scraper status: {current_row_scraper_status}, Canonical URL: {final_canonical_entry_url}")

            if current_row_scraper_status == "Success" and final_canonical_entry_url:
                if final_canonical_entry_url not in canonical_site_llm_results: # Process this canonical site for the first time
                    logger.info(f"Processing new canonical URL for LLM: {final_canonical_entry_url} (from input {given_url_original})")
                    all_candidate_items_for_llm: List[Dict[str, str]] = []
                    if scraped_pages_details:
                        target_codes_raw: Any = row.get('TargetCountryCodes', [])
                        target_codes_list_for_regex: List[str] = []
                        if isinstance(target_codes_raw, str) and target_codes_raw.startswith('[') and target_codes_raw.endswith(']'):
                            try:
                                import ast
                                parsed_eval = ast.literal_eval(target_codes_raw)
                                if isinstance(parsed_eval, list):
                                    target_codes_list_for_regex = [str(item) for item in parsed_eval if isinstance(item, (str, int))]
                            except (ValueError, SyntaxError):
                                logger.warning(f"Could not parse TargetCountryCodes string: {target_codes_raw} for {company_name}.")
                        elif isinstance(target_codes_raw, list):
                            target_codes_list_for_regex = [str(item) for item in target_codes_raw if isinstance(item, (str, int))]

                        for page_content_file, source_page_url in scraped_pages_details:
                            if os.path.exists(page_content_file):
                                try:
                                    with open(page_content_file, 'r', encoding='utf-8') as f_content:
                                        text_content = f_content.read()
                                    page_candidate_items: List[Dict[str, str]] = extract_numbers_with_snippets_from_text(
                                        text_content=text_content, source_url=source_page_url,
                                        target_country_codes=target_codes_list_for_regex,
                                        snippet_window_chars=app_config.snippet_window_chars
                                    )
                                    all_candidate_items_for_llm.extend(page_candidate_items)
                                except Exception as file_read_exc:
                                    logger.error(f"Error reading scraped page content {page_content_file} for {company_name} (canonical: {final_canonical_entry_url}): {file_read_exc}", exc_info=True)
                            else:
                                logger.warning(f"Scraped page content file not found: {page_content_file} for {company_name} (canonical: {final_canonical_entry_url})")
                        
                        # Save regex snippets (still linked to original input row for traceability if needed)
                        if all_candidate_items_for_llm:
                            safe_company_name_for_file_regex = "".join(c if c.isalnum() else "_" for c in company_name)
                            regex_snippets_filename = f"{safe_company_name_for_file_regex}_Row{index}_regex_snippets.json"
                            regex_snippets_filepath = os.path.join(intermediate_data_dir, regex_snippets_filename)
                            try:
                                with open(regex_snippets_filepath, 'w', encoding='utf-8') as f_snippets: json.dump(all_candidate_items_for_llm, f_snippets, indent=2)
                                logger.info(f"Saved {len(all_candidate_items_for_llm)} regex candidate snippets (for input row {index}) to {regex_snippets_filepath}")
                            except IOError as e: logger.error(f"IOError saving regex snippets to {regex_snippets_filepath}: {e}")
                        logger.info(f"Generated {len(all_candidate_items_for_llm)} candidate items for LLM for canonical URL {final_canonical_entry_url} (triggered by input row {index}).")

                    if all_candidate_items_for_llm:
                        try:
                            prompt_template_abs_path: str = app_config.llm_prompt_template_path
                            if not os.path.isabs(prompt_template_abs_path):
                                project_root_dir_local = os.path.dirname(os.path.abspath(__file__))
                                prompt_template_abs_path = os.path.join(project_root_dir_local, prompt_template_abs_path)

                            if not os.path.exists(prompt_template_abs_path):
                                logger.error(f"LLM prompt template file not found at {prompt_template_abs_path}. Cannot process canonical URL {final_canonical_entry_url}.")
                                canonical_site_llm_results[final_canonical_entry_url] = []
                                canonical_site_scraper_status[final_canonical_entry_url] = "Error_LLM_PromptMissing"
                            else:
                                # Save LLM input candidates file, perhaps named with canonical URL context
                                safe_canonical_name_for_file = "".join(c if c.isalnum() else "_" for c in final_canonical_entry_url.replace("http://","").replace("https://",""))
                                llm_input_filename = f"CANONICAL_{safe_canonical_name_for_file}_llm_input_data.json"
                                llm_input_filepath = os.path.join(llm_context_dir, llm_input_filename)
                                try:
                                    with open(llm_input_filepath, 'w', encoding='utf-8') as f_in: json.dump(all_candidate_items_for_llm, f_in, indent=2)
                                    logger.info(f"Saved LLM input data for {final_canonical_entry_url} to {llm_input_filepath}")
                                except IOError as e: logger.error(f"IOError saving LLM input data for {final_canonical_entry_url}: {e}")

                                llm_classified_outputs, llm_raw_response = llm_extractor.extract_phone_numbers(
                                    candidate_items=all_candidate_items_for_llm,
                                    prompt_template_path=prompt_template_abs_path,
                                    llm_context_dir=llm_context_dir,
                                    file_identifier_prefix=f"CANONICAL_{safe_canonical_name_for_file}"
                                )
                                canonical_site_llm_results[final_canonical_entry_url] = llm_classified_outputs
                                canonical_site_scraper_status[final_canonical_entry_url] = current_row_scraper_status # Should be "Success"
                                
                                llm_raw_output_filename = f"CANONICAL_{safe_canonical_name_for_file}_llm_raw_output.json"
                                llm_raw_output_filepath = os.path.join(llm_context_dir, llm_raw_output_filename)
                                try:
                                    with open(llm_raw_output_filepath, 'w', encoding='utf-8') as f_llm_out:
                                        f_llm_out.write(llm_raw_response if isinstance(llm_raw_response, str) else json.dumps(llm_raw_response or {}, indent=2))
                                    logger.info(f"LLM classification for canonical {final_canonical_entry_url} complete. Raw output saved to {llm_raw_output_filepath}")
                                except IOError as e: logger.error(f"IOError saving raw LLM output for {final_canonical_entry_url} to {llm_raw_output_filepath}: {e}")
                        except Exception as llm_exc:
                            logger.error(f"Error during LLM processing for canonical {final_canonical_entry_url}: {llm_exc}", exc_info=True)
                            canonical_site_llm_results[final_canonical_entry_url] = []
                            canonical_site_scraper_status[final_canonical_entry_url] = "Error_LLM_Processing"
                    else: # No candidate items from regex for this new canonical site
                        logger.info(f"No candidate snippets for LLM from canonical {final_canonical_entry_url}. Caching empty LLM result.")
                        canonical_site_llm_results[final_canonical_entry_url] = []
                        canonical_site_scraper_status[final_canonical_entry_url] = current_row_scraper_status # "Success"
                else: # This canonical URL's LLM data is already cached or scrape failed for pages
                    logger.info(f"LLM data for canonical URL {final_canonical_entry_url} already cached or no pages scraped. Input row {given_url_original} maps to it.")
            
            elif current_row_scraper_status != "Success": # Scraping failed for this input_row
                logger.info(f"Row {current_row_number_for_log} ({company_name}): Scraper status '{current_row_scraper_status}'. No LLM processing for this input.")
                if final_canonical_entry_url and final_canonical_entry_url not in canonical_site_scraper_status: # Store failure status for canonical if not already there
                    canonical_site_scraper_status[final_canonical_entry_url] = current_row_scraper_status
                # For summary report, ensure Overall_VerificationStatus reflects this scrape failure
                df.at[index, 'Overall_VerificationStatus'] = f'Unverified_Scrape_{current_row_scraper_status}'
                df.at[index, 'Original_Number_Status'] = f'Scrape_{current_row_scraper_status}' if row.get('NormalizedGivenPhoneNumber') else 'Original_Not_Provided'
            
            # Logging for the current input row after its individual processing in Pass 1
            # The df.at[index, 'Overall_VerificationStatus'] might be preliminary here.
            # Final summary status is determined in Pass 2.
            logger.info(f"Row {current_row_number_for_log} ({company_name}): Pass 1 processing complete. OriginalURL: {given_url_original_str_key}, CanonicalURL: {final_canonical_entry_url}, ScraperStatus: {current_row_scraper_status}")

        except Exception as e:
            logger.error(f"Error during Pass 1 processing for row {current_row_number_for_log} ({company_name}), Original URL {given_url_original_str_key}: {e}", exc_info=True)
            df.at[index, 'Overall_VerificationStatus'] = 'Error_Pass1_RowProcessing'
            current_scraper_status_for_df = df.at[index, 'ScrapingStatus'] # Get current status
            if current_scraper_status_for_df in ["Not_Run", "Success", None] or not current_scraper_status_for_df : # If scraper status wasn't an error, mark as pipeline error
                 df.at[index, 'ScrapingStatus'] = f'PipelineError_{type(e).__name__}'
            logger.error(
                f"Row {current_row_number_for_log} ({company_name}) errored in Pass 1. "
                f"ScraperStatus='{df.at[index, 'ScrapingStatus']}', "
                f"OverallVerificationStatus='{df.at[index, 'Overall_VerificationStatus']}'"
            )
            # Ensure summary fields related to LLM are blanked on error for this input row
            for col_prefix in ['Primary_', 'Secondary_']:
                for suffix in ['Number_1', 'Type_1', 'SourceURL_1', 'Number_2', 'Type_2', 'SourceURL_2']:
                    col_name = f"{col_prefix}{suffix}"
                    if col_name in df.columns:
                        df.at[index, col_name] = None
            if 'Original_Number_Status' in df.columns: # Check if column exists
                df.at[index, 'Original_Number_Status'] = 'Error_Pass1_RowProcessing'

    # --- After the main loop (End of Pass 1) ---
    logger.info(f"Pass 1 (Scraping and LLM Caching) complete. Processed {len(df)} input rows.")
    logger.info(f"Unique canonical sites for which LLM processing was attempted/cached: {len(canonical_site_llm_results)}")
    logger.debug(f"Canonical site LLM results cache keys: {list(canonical_site_llm_results.keys())}")
    logger.debug(f"Canonical site scraper status cache: {list(canonical_site_scraper_status.keys())}") # Log keys for brevity
    logger.debug(f"Input to Canonical URL map entries: {len(input_to_canonical_map)}")

# Define column order for Excel exports (moved here for clarity before Pass 2)
    detailed_columns_order = [
        'CompanyName', 'GivenURL', 'CanonicalEntryURL', 'ScrapingStatus_Canonical',
        'LLM_Processing_Status_Canonical', 'Original_Number_Status',
        'extracted_number', 'country_code', 'is_mobile', 'is_fixed_line',
        'possible_countries', 'classification', 'reasoning', 'source_url',
        'RunID', 'TargetCountryCodes'
    ]

    summary_columns_order = [
        'CompanyName', 'GivenURL', 'CanonicalEntryURL', 'ScrapingStatus_Canonical',
        'LLM_Processing_Status_Canonical', 'Overall_VerificationStatus', 'Original_Number_Status',
        'Primary_Number_1', 'Primary_Number_1_Country', 'Primary_Number_1_IsMobile',
        'Secondary_Number_1', 'Secondary_Number_1_Country', 'Secondary_Number_1_IsMobile',
        'Secondary_Number_2', 'Secondary_Number_2_Country', 'Secondary_Number_2_IsMobile',
        'RunID', 'TargetCountryCodes'
    ]

    # --- Pass 2: Building Reports ---
    logger.info("Starting Pass 2: Building Detailed Flattened and Summary Reports...")

    # A. Detailed Flattened Report - Populate all_flattened_rows
    classification_precedence = { # Define once for de-duplication
        'Primary': 1, 'Secondary': 2, 'Support': 3,
        'Low Relevance': 4, 'Non-Business': 5, None: 99
    }

    for index, original_row_data in df.iterrows(): # Iterate original input rows
        company_name_pass2 = str(original_row_data.get('CompanyName', f"Row_{index}"))
        given_url_pass2 = original_row_data.get('GivenURL')
        canonical_url_pass2 = original_row_data.get('CanonicalEntryURL')
        scraper_status_pass2 = original_row_data.get('ScrapingStatus')

        if scraper_status_pass2 == "Success" and canonical_url_pass2 and canonical_url_pass2 in canonical_site_llm_results:
            llm_outputs_for_canonical = canonical_site_llm_results[canonical_url_pass2]
            
            best_llm_outputs_for_this_site: Dict[str, PhoneNumberLLMOutput] = {}
            if llm_outputs_for_canonical:
                for llm_item_iter in llm_outputs_for_canonical:
                    current_number_iter = llm_item_iter.number
                    if current_number_iter:
                        current_classification_score_iter = classification_precedence.get(llm_item_iter.classification, 99)
                        existing_item_iter = best_llm_outputs_for_this_site.get(current_number_iter)
                        if not existing_item_iter or current_classification_score_iter < classification_precedence.get(existing_item_iter.classification, 99):
                            best_llm_outputs_for_this_site[current_number_iter] = llm_item_iter
            
            if best_llm_outputs_for_this_site:
                for llm_item_final in best_llm_outputs_for_this_site.values():
                    new_flattened_row: Dict[str, Any] = {
                        'RunID': original_row_data.get('RunID'),
                        'TargetCountryCodes': original_row_data.get('TargetCountryCodes'),
                        'CompanyName': company_name_pass2,
                        'GivenURL': given_url_pass2, # Original input URL for traceability
                        'Canonical_URL': canonical_url_pass2, # The URL data was actually scraped from
                        # 'Description': original_row_data.get('Description'), # Removed
                        'ScrapingStatus': canonical_site_scraper_status.get(canonical_url_pass2, scraper_status_pass2), # Status of canonical scrape
                        'LLM_Source_URL': llm_item_final.source_url,
                        'LLM_Number': llm_item_final.number,
                        'LLM_Type': llm_item_final.type,
                        'LLM_Classification': llm_item_final.classification
                    }
                    all_flattened_rows.append(new_flattened_row)
            # else: No unique relevant numbers from LLM for this successfully scraped canonical site - no row in detailed.
        # else: Scraping failed or no canonical URL or no LLM results for this canonical - no row in detailed.

    # B. Summary Report - Populate specific columns in main 'df'
    for index, row_summary in df.iterrows():
        given_url_summary = str(row_summary.get('GivenURL')) if row_summary.get('GivenURL') is not None else "None_GivenURL_Input"
        canonical_url_summary = row_summary.get('CanonicalEntryURL')
        scraper_status_summary = row_summary.get('ScrapingStatus')

        llm_outputs_for_summary: List[PhoneNumberLLMOutput] = []
        if canonical_url_summary and canonical_url_summary in canonical_site_llm_results:
            llm_outputs_for_summary = canonical_site_llm_results[canonical_url_summary]

        primary_numbers_summary: List[PhoneNumberLLMOutput] = []
        secondary_numbers_summary: List[PhoneNumberLLMOutput] = []
        support_numbers_summary: List[PhoneNumberLLMOutput] = [] # For Overall_VerificationStatus
        low_relevance_summary: List[PhoneNumberLLMOutput] = [] # For Overall_VerificationStatus

        if llm_outputs_for_summary:
            for item_summary in llm_outputs_for_summary:
                if item_summary.classification == 'Primary': primary_numbers_summary.append(item_summary)
                elif item_summary.classification == 'Secondary': secondary_numbers_summary.append(item_summary)
                elif item_summary.classification == 'Support': support_numbers_summary.append(item_summary)
                elif item_summary.classification == 'Low Relevance': low_relevance_summary.append(item_summary)
        
        # Populate Primary/Secondary numbers for summary
        if primary_numbers_summary:
            df.at[index, 'Primary_Number_1'] = primary_numbers_summary[0].number
            df.at[index, 'Primary_Type_1'] = primary_numbers_summary[0].type
            df.at[index, 'Primary_SourceURL_1'] = primary_numbers_summary[0].source_url
        if secondary_numbers_summary:
            df.at[index, 'Secondary_Number_1'] = secondary_numbers_summary[0].number
            df.at[index, 'Secondary_Type_1'] = secondary_numbers_summary[0].type
            df.at[index, 'Secondary_SourceURL_1'] = secondary_numbers_summary[0].source_url
            if len(secondary_numbers_summary) > 1:
                df.at[index, 'Secondary_Number_2'] = secondary_numbers_summary[1].number
                df.at[index, 'Secondary_Type_2'] = secondary_numbers_summary[1].type
                df.at[index, 'Secondary_SourceURL_2'] = secondary_numbers_summary[1].source_url

        # Determine Original_Number_Status
        original_norm_phone_summary = row_summary.get('NormalizedGivenPhoneNumber')
        if original_norm_phone_summary and original_norm_phone_summary != "InvalidFormat":
            if any(p.number == original_norm_phone_summary for p in primary_numbers_summary) or \
               any(s.number == original_norm_phone_summary for s in secondary_numbers_summary):
                df.at[index, 'Original_Number_Status'] = 'Verified'
            elif primary_numbers_summary or secondary_numbers_summary:
                df.at[index, 'Original_Number_Status'] = 'Corrected'
            elif llm_outputs_for_summary: # LLM ran but found no primary/secondary, and original didn't match
                 df.at[index, 'Original_Number_Status'] = 'No Match Found by LLM'
            else: # LLM did not run or had no output for this canonical URL
                 df.at[index, 'Original_Number_Status'] = 'LLM_NoOutput_For_Canonical'

        elif original_norm_phone_summary == "InvalidFormat":
            df.at[index, 'Original_Number_Status'] = 'Original_InvalidFormat'
        else:
            df.at[index, 'Original_Number_Status'] = 'Original_Not_Provided'
        
        # Determine Overall_VerificationStatus
        overall_status = "Unverified" # Default
        if scraper_status_summary != "Success":
            overall_status = f"Unverified_Scrape_{scraper_status_summary}"
        elif primary_numbers_summary:
            overall_status = "Verified_Primary_Found"
        elif secondary_numbers_summary:
            overall_status = "Verified_Secondary_Found"
        elif support_numbers_summary: # Only if no primary/secondary
            overall_status = "Verified_Support_Found"
        elif low_relevance_summary: # Only if no primary/secondary/support
            overall_status = "Verified_LowRelevance_Found"
        elif llm_outputs_for_summary: # LLM ran, found items, but none matched above categories
            overall_status = "Unverified_LLM_NoHighValueMatch"
        elif canonical_url_summary and canonical_url_summary in canonical_site_llm_results and not llm_outputs_for_summary:
            # LLM ran for this canonical URL but returned absolutely nothing
            overall_status = "Unverified_LLM_OutputEmpty"
        elif canonical_url_summary and canonical_site_scraper_status.get(canonical_url_summary) == "Error_LLM_Processing":
            overall_status = "Error_LLM_Processing_For_Canonical"
        elif canonical_url_summary and canonical_site_scraper_status.get(canonical_url_summary) == "Error_LLM_PromptMissing":
            overall_status = "Error_LLM_PromptMissing_For_Canonical"
        # else: stays "Unverified" if scrape was success but no LLM results for canonical (e.g. no regex snippets)

        # Prepend redirect info if applicable
        original_input_url_for_map = str(row_summary.get('GivenURL')) if row_summary.get('GivenURL') is not None else "None_GivenURL_Input"
        if canonical_url_summary and input_to_canonical_map.get(original_input_url_for_map) != original_input_url_for_map : # Check if it was actually different from input
             # Check if the original input URL (if valid) is different from the canonical one
            normalized_original_for_comparison = normalize_url(original_input_url_for_map) if original_input_url_for_map != "None_GivenURL_Input" else None
            if normalized_original_for_comparison and normalized_original_for_comparison != canonical_url_summary:
                 overall_status = f"RedirectedTo[{canonical_url_summary}]_" + overall_status
        
        df.at[index, 'Overall_VerificationStatus'] = overall_status
        df.at[index, 'ScrapingStatus_Canonical'] = canonical_site_scraper_status.get(str(canonical_url_summary), scraper_status_summary) if canonical_url_summary is not None else scraper_status_summary
        df.at[index, 'LLM_Processing_Status_Canonical'] = "Processed" if canonical_url_summary and canonical_url_summary in canonical_site_llm_results else (canonical_site_scraper_status.get(str(canonical_url_summary), "Not_Processed_Or_Scrape_Failed") if canonical_url_summary is not None else "Not_Processed_Or_Scrape_Failed")


    # Create and save Detailed Flattened Report
    if all_flattened_rows:
        df_detailed_flattened = pd.DataFrame(all_flattened_rows)
        
        # Custom sort for LLM_Classification
        classification_sort_order = ['Primary', 'Secondary', 'Support', 'Low Relevance', 'Non-Business']
        df_detailed_flattened['LLM_Classification_Sort'] = pd.Categorical(
            df_detailed_flattened['LLM_Classification'],
            categories=classification_sort_order,
            ordered=True
        )
        df_detailed_flattened = df_detailed_flattened.sort_values(
            by=['CompanyName', 'Canonical_URL', 'LLM_Classification_Sort', 'LLM_Number'],
            na_position='last' # Ensure NaNs in sort key are handled if any
        ).drop(columns=['LLM_Classification_Sort'])
        
        # Ensure all columns are present, fill missing with None or empty string
        for col in detailed_columns_order:
            if col not in df_detailed_flattened.columns:
                df_detailed_flattened[col] = None # Or appropriate default like ''
        
        df_detailed_export = df_detailed_flattened[detailed_columns_order].copy()

        detailed_output_filename = f"phone_validation_detailed_output_{run_id}.xlsx"
        detailed_output_excel_path = os.path.join(run_output_dir, detailed_output_filename)
        try:
            logger.info(f"Attempting to save detailed report to: {detailed_output_excel_path}")
            with pd.ExcelWriter(detailed_output_excel_path, engine='openpyxl') as writer:
                df_detailed_export.to_excel(writer, index=False, sheet_name='Detailed_Phone_Data')
                # Auto-adjust column widths for detailed report
                for column in df_detailed_export:
                    column_length = max(df_detailed_export[column].astype(str).map(len).max(), len(str(column)))
                    col_letter = get_column_letter(list(df_detailed_export.columns).index(str(column)) + 1)
                    writer.sheets['Detailed_Phone_Data'].column_dimensions[col_letter].width = column_length + 2
            logger.info(f"Detailed report saved successfully to {detailed_output_excel_path}")
        except Exception as e_detailed:
            logger.error(f"Error saving detailed report to {detailed_output_excel_path}: {e_detailed}", exc_info=True)
    else:
        logger.info("No data for detailed flattened report. Skipping file creation.")

    # Prepare and save Summary Report (from the modified main df)
    # Ensure all expected columns exist in df before selecting/reordering
    for col in summary_columns_order:
        if col not in df.columns:
            # Initialize missing columns that should have been created by data_handler or this script
            if col in ['CanonicalEntryURL', 'ScrapingStatus_Canonical', 'LLM_Processing_Status_Canonical', 'Overall_VerificationStatus', 'Original_Number_Status',
                       'Primary_Number_1', 'Primary_Type_1', 'Primary_SourceURL_1', 
                       'Secondary_Number_1', 'Secondary_Type_1', 'Secondary_SourceURL_1',
                       'Secondary_Number_2', 'Secondary_Type_2', 'Secondary_SourceURL_2']:
                df[col] = None # Or appropriate default like ''
            elif col == 'RunID':
                df[col] = run_id
            # 'TargetCountryCodes' should come from input or be added by data_handler
            # 'CompanyName', 'GivenURL' are expected from input.
            # If other critical columns are missing, it indicates an earlier problem.
            # For now, just ensure they exist to prevent KeyError on selection.
            elif col not in df.columns: # Catch-all for any other defined in summary_columns_order
                 df[col] = None


    df_summary_export = df[[col for col in summary_columns_order if col in df.columns]].copy()
    
    summary_output_filename = app_config.output_excel_file_name_template.format(run_id=run_id)
    summary_output_excel_path = os.path.join(run_output_dir, summary_output_filename)
    try:
        logger.info(f"Attempting to save summary report to: {summary_output_excel_path}")
        with pd.ExcelWriter(summary_output_excel_path, engine='openpyxl') as writer:
            df_summary_export.to_excel(writer, index=False, sheet_name='Phone_Validation_Summary')
            # Auto-adjust column widths for summary report
            for column in df_summary_export:
                column_length = max(df_summary_export[column].astype(str).map(len).max(), len(str(column)))
                col_letter = get_column_letter(list(df_summary_export.columns).index(str(column)) + 1)
                writer.sheets['Phone_Validation_Summary'].column_dimensions[col_letter].width = column_length + 2
        logger.info(f"Summary report saved successfully to {summary_output_excel_path}")
    except Exception as e_summary:
        logger.error(f"Error saving summary report to {summary_output_excel_path}: {e_summary}", exc_info=True)

    logger.info(f"Pipeline run {run_id} finished.")
    total_duration = time.time() - datetime.strptime(run_id, "%Y%m%d_%H%M%S").timestamp()
    logger.info(f"Total pipeline duration: {total_duration:.2f} seconds.")


if __name__ == '__main__':
    # This basic setup is for when the script is run directly.
    # The main() function will then call the more detailed setup_logging.
    if not logger.hasHandlers(): # Ensure basic config if run directly and not imported
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    main()