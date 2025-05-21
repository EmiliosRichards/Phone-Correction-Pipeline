import pandas as pd
from typing import List, Dict, Set, Optional, Any, Callable, Union, Tuple
from src.data_handler import load_and_preprocess_data, process_and_consolidate_contact_data, get_canonical_base_url # Added process_and_consolidate_contact_data
from src.scraper import scrape_website
from src.regex_extractor_component import extract_numbers_with_snippets_from_text
from src.llm_extractor_component import GeminiLLMExtractor
from src.core.schemas import PhoneNumberLLMOutput, CompanyContactDetails, ConsolidatedPhoneNumber # Added ConsolidatedPhoneNumber
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
EXCLUDED_TYPES_FOR_TOP_CONTACTS_REPORT: Set[str] = {
    'Unknown', 'Fax', 'Mobile', 'Date', 'ID' # 'Non-Priority-Country Contact' removed as per user request
}
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
        # TargetCountryCodes is added by load_and_preprocess_data
        # 'VerificationStatus': '', # This will be Overall_VerificationStatus
        'BestMatchedPhoneNumbers': lambda: [[] for _ in range(len(df))], # Potentially for future use or other reports
        'OtherRelevantNumbers': lambda: [[] for _ in range(len(df))], # Potentially for future use
        'ConfidenceScore': None, # Potentially for future use
        'LLMExtractedNumbers': lambda: [[] for _ in range(len(df))], # Stores raw list from LLM for a canonical URL - USAGE MAY CHANGE
        # 'AllCompanyContacts': lambda: [None for _ in range(len(df))], # Removed as per plan docs/top_contacts_report_refactor_plan_20250520_140819.md
        'LLMContextPath': '',
        'Notes': '',
        # New columns for the revised summary report
        'Top_Number_1': None,
        'Top_Type_1': None,
        'Top_SourceURL_1': None,
        'Top_Number_2': None,
        'Top_Type_2': None,
        'Top_SourceURL_2': None,
        'Top_Number_3': None,
        'Top_Type_3': None,
        'Top_SourceURL_3': None,
        # CanonicalEntryURL, Original_Number_Status, Overall_VerificationStatus are handled in main loop
        # GivenPhoneNumber and Description should come from load_and_preprocess_data
    }
    for col, default_val in required_cols.items():
        if col not in df.columns:
            # Ensure 'TargetCountryCodes' is initialized if somehow missed by load_and_preprocess_data, though unlikely
            if col == 'TargetCountryCodes' and col not in df.columns:
                 df[col] = pd.Series([[] for _ in range(len(df))], dtype=object)
            else:
                df[col] = default_val() if callable(default_val) else default_val
    
    # Ensure essential columns from load_and_preprocess_data are present for summary report
    # These are expected to be populated by load_and_preprocess_data
    if 'GivenPhoneNumber' not in df.columns:
        df['GivenPhoneNumber'] = None
    if 'Description' not in df.columns:
        df['Description'] = None


    globally_processed_urls: Set[str] = set() # Initialize the global set
    all_flattened_rows: List[Dict[str, Any]] = [] # For the detailed flattened report
    all_tertiary_rows: List[Dict[str, Any]] = [] # For the new tertiary report
    # This will store raw LLM outputs keyed by the pathful canonical URL from the scraper
    canonical_site_raw_llm_outputs: Dict[str, List[PhoneNumberLLMOutput]] = {}
    # This will store the scraper status keyed by the pathful canonical URL from the scraper
    canonical_site_pathful_scraper_status: Dict[str, str] = {}
    input_to_canonical_map: Dict[str, Optional[str]] = {} # Maps original input URL to its true_base_domain_for_row

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
            # Store the TRUE BASE DOMAIN as the CanonicalEntryURL for the input row
            true_base_domain_for_row = get_canonical_base_url(final_canonical_entry_url) if final_canonical_entry_url else None
            df.at[index, 'CanonicalEntryURL'] = true_base_domain_for_row
            current_row_scraper_status = scraper_status # Keep for local logging within this iteration
            given_url_original_str_key = str(given_url_original) if given_url_original is not None else "None_GivenURL_Input" # Ensure it's defined for the current row
            # input_to_canonical_map now maps original input URL to its true_base_domain_for_row
            input_to_canonical_map[given_url_original_str_key] = true_base_domain_for_row

            logger.info(f"Row {current_row_number_for_log} ({company_name}): Scraper status: {current_row_scraper_status}, Pathful Canonical URL from Scraper: {final_canonical_entry_url}, True Base Domain: {true_base_domain_for_row}")

            if current_row_scraper_status == "Success" and final_canonical_entry_url: # final_canonical_entry_url is pathful here
                # We collect raw LLM outputs per pathful_canonical_url. Consolidation per true_base_domain happens after this loop.
                if final_canonical_entry_url not in canonical_site_raw_llm_outputs: # Process this pathful canonical URL for the first time
                    logger.info(f"Processing new pathful canonical URL for LLM data collection: {final_canonical_entry_url} (from input {given_url_original})")
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
                                    # company_name is from the current input row (df.iterrows)
                                    page_candidate_items: List[Dict[str, str]] = extract_numbers_with_snippets_from_text(
                                        text_content=text_content,
                                        source_url=source_page_url,
                                        original_input_company_name=company_name, # Pass the original company name
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
                                logger.error(f"LLM prompt template file not found at {prompt_template_abs_path}. Cannot process pathful canonical URL {final_canonical_entry_url}.")
                                canonical_site_raw_llm_outputs[final_canonical_entry_url] = [] # Store empty LLM results
                                canonical_site_pathful_scraper_status[final_canonical_entry_url] = "Error_LLM_PromptMissing"
                            else:
                                # Save LLM input candidates file, perhaps named with canonical URL context
                                safe_canonical_name_for_file = "".join(c if c.isalnum() else "_" for c in final_canonical_entry_url.replace("http://","").replace("https://",""))
                                # Truncate safe_canonical_name_for_file to prevent excessively long filenames
                                max_len_url_part = 100 # Define a max length for the URL-derived part
                                if len(safe_canonical_name_for_file) > max_len_url_part:
                                    safe_canonical_name_for_file = safe_canonical_name_for_file[:max_len_url_part]
                                    logger.info(f"Truncated safe_canonical_name_for_file for {final_canonical_entry_url} to: {safe_canonical_name_for_file}")

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
                                canonical_site_raw_llm_outputs[final_canonical_entry_url] = llm_classified_outputs
                                canonical_site_pathful_scraper_status[final_canonical_entry_url] = current_row_scraper_status # Should be "Success"
                                
                                llm_raw_output_filename = f"CANONICAL_{safe_canonical_name_for_file}_llm_raw_output.json"
                                llm_raw_output_filepath = os.path.join(llm_context_dir, llm_raw_output_filename)
                                logger.info(f"Attempting to save LLM raw output. Path: '{llm_raw_output_filepath}', Length: {len(llm_raw_output_filepath)}") # DEBUG PATH LENGTH
                                try:
                                    with open(llm_raw_output_filepath, 'w', encoding='utf-8') as f_llm_out:
                                        f_llm_out.write(llm_raw_response if isinstance(llm_raw_response, str) else json.dumps(llm_raw_response or {}, indent=2))
                                    logger.info(f"LLM classification for canonical {final_canonical_entry_url} complete. Raw output saved to {llm_raw_output_filepath}")
                                except IOError as e: logger.error(f"IOError saving raw LLM output for {final_canonical_entry_url} to {llm_raw_output_filepath}: {e}")
                        except Exception as llm_exc:
                            logger.error(f"Error during LLM processing for pathful canonical {final_canonical_entry_url}: {llm_exc}", exc_info=True)
                            canonical_site_raw_llm_outputs[final_canonical_entry_url] = []
                            canonical_site_pathful_scraper_status[final_canonical_entry_url] = "Error_LLM_Processing"
                    else: # No candidate items from regex for this new pathful canonical site
                        logger.info(f"No candidate snippets for LLM from pathful canonical {final_canonical_entry_url}. Storing empty LLM result.")
                        canonical_site_raw_llm_outputs[final_canonical_entry_url] = []
                        canonical_site_pathful_scraper_status[final_canonical_entry_url] = current_row_scraper_status # "Success"
                else: # Raw LLM data for this pathful canonical URL is already cached.
                    logger.info(f"Raw LLM data for pathful canonical URL {final_canonical_entry_url} already cached. Input row {given_url_original} maps to it.")
            
            elif current_row_scraper_status != "Success": # Scraping failed for this input_row
                logger.info(f"Row {current_row_number_for_log} ({company_name}): Scraper status '{current_row_scraper_status}'. No LLM processing for this input.")
                if final_canonical_entry_url and final_canonical_entry_url not in canonical_site_pathful_scraper_status: # Store failure status for pathful canonical if not already there
                    canonical_site_pathful_scraper_status[final_canonical_entry_url] = current_row_scraper_status
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
    logger.info(f"Pass 1 (Scraping and Raw LLM Data Collection) complete. Processed {len(df)} input rows.")
    logger.info(f"Unique pathful canonical sites for which raw LLM data was collected: {len(canonical_site_raw_llm_outputs)}")
    logger.debug(f"Pathful canonical site raw LLM data cache keys: {list(canonical_site_raw_llm_outputs.keys())}")
    logger.debug(f"Pathful canonical site scraper status cache: {list(canonical_site_pathful_scraper_status.keys())}")
    logger.debug(f"Input to True Base Domain map entries: {len(input_to_canonical_map)}")

    # --- New Global Consolidation Step (Consolidate raw LLM outputs by TRUE BASE DOMAIN) ---
    logger.info("Starting Global Consolidation of LLM data by True Base Domain...")
    final_consolidated_data_by_true_base: Dict[str, Optional[CompanyContactDetails]] = {}
    # Map: true_base_domain -> list of pathful_canonical_urls that belong to it
    true_base_to_pathful_map: Dict[str, List[str]] = {}
    # Map: true_base_domain -> list of original company names from input that map to it
    true_base_to_input_company_names: Dict[str, Set[str]] = {}
    # Map: true_base_domain -> final scraper status (e.g. if one path succeeded, it's success)
    true_base_scraper_status: Dict[str, str] = {}


    for pathful_url_key, raw_llm_list in canonical_site_raw_llm_outputs.items():
        true_base = get_canonical_base_url(pathful_url_key)
        if not true_base:
            logger.warning(f"Could not get true_base_domain for pathful_url_key '{pathful_url_key}' during global consolidation. Skipping.")
            continue
        
        if true_base not in true_base_to_pathful_map:
            true_base_to_pathful_map[true_base] = []
            true_base_to_input_company_names[true_base] = set()
            true_base_scraper_status[true_base] = "Unknown" # Initialize
        
        true_base_to_pathful_map[true_base].append(pathful_url_key)
        
        # Update scraper status for the true_base_domain
        current_pathful_status = canonical_site_pathful_scraper_status.get(pathful_url_key, "Unknown")
        if true_base_scraper_status[true_base] == "Unknown" or \
           (current_pathful_status == "Success" and true_base_scraper_status[true_base] != "Success") or \
           ("Error" not in current_pathful_status and "Error" in true_base_scraper_status[true_base]): # Prefer non-error or success
            true_base_scraper_status[true_base] = current_pathful_status


    # Collect original company names for each true_base_domain by looking up input_df
    # This assumes df['CanonicalEntryURL'] now stores the true_base_domain
    if 'CanonicalEntryURL' in df.columns and 'CompanyName' in df.columns:
        for true_base_domain_key in true_base_to_pathful_map.keys():
            # Find all input rows that map to this true_base_domain_key
            # Ensure df['CanonicalEntryURL'] is not None before comparing
            mask = df['CanonicalEntryURL'].notna() & (df['CanonicalEntryURL'] == true_base_domain_key)
            matching_companies = df.loc[mask, 'CompanyName'].dropna().astype(str).unique()
            if len(matching_companies) > 0:
                 true_base_to_input_company_names[true_base_domain_key].update(matching_companies)
            else: # Fallback if no direct match in df (e.g. if df['CanonicalEntryURL'] wasn't perfectly set)
                 # Try to find first company name from the pathful URLs that triggered this true_base
                 first_pathful_for_base = true_base_to_pathful_map[true_base_domain_key][0]
                 # This requires iterating df again to find which input row led to first_pathful_for_base
                 # This part is complex to get right without more context on how initial company name was passed to process_and_consolidate
                 # For now, we'll rely on the df lookup. If empty, the company name in CompanyContactDetails will be from the *first* pathful URL's trigger.
                 logger.warning(f"No matching company names found in df for true_base_domain '{true_base_domain_key}'. Company name in report might be from first pathful trigger.")


    for true_base_domain, list_of_pathful_urls in true_base_to_pathful_map.items():
        all_llm_results_for_this_true_base: List[PhoneNumberLLMOutput] = []
        for pathful_url_item in list_of_pathful_urls:
            all_llm_results_for_this_true_base.extend(canonical_site_raw_llm_outputs.get(pathful_url_item, []))
        
        # Determine a representative company name for this true_base_domain for process_and_consolidate_contact_data
        # This name is primarily for the CompanyContactDetails object, not necessarily the final report name.
        # The final report name will be constructed later using all names from true_base_to_input_company_names.
        representative_company_name_for_consolidation = "Unknown"
        if true_base_to_input_company_names.get(true_base_domain):
            representative_company_name_for_consolidation = sorted(list(true_base_to_input_company_names[true_base_domain]))[0]
        elif list_of_pathful_urls: # Fallback: try to find an original company name from one of the input rows that led to these pathful URLs
            # This is tricky; for now, use a generic or the first one found during earlier processing if available.
            # The `company_name` argument to `process_and_consolidate_contact_data` is Optional.
            # Let's find the company name from the first input row that generated any of the pathful_urls.
            # This requires iterating df again or having a map from pathful_url to original input company name.
            # For simplicity now, we might pass None or a generic name if not easily found.
            # The `company_name` field in `CompanyContactDetails` is optional.
            # The `company_name` used in `process_and_consolidate_contact_data` is the one from the *first* input row that triggered the processing of a *pathful* canonical URL.
            # We can try to retrieve that.
            # Find an input row that generated one of these pathful URLs.
            # This is complex. Let's pass the first company name from the collected set for this true_base_domain.
            pass


        final_consolidated_data_by_true_base[true_base_domain] = process_and_consolidate_contact_data(
            llm_results=all_llm_results_for_this_true_base,
            company_name_from_input=representative_company_name_for_consolidation, # Use the representative name
            initial_given_url=true_base_domain # Use the true_base_domain as the "initial URL" for this consolidation scope
        )
    logger.info(f"Global Consolidation complete. {len(final_consolidated_data_by_true_base)} true base domains processed.")


# Define column order for Excel exports (moved here for clarity before Pass 2)
    detailed_columns_order = [
        'CompanyName',
        'Number',
        'LLM_Type',
        'LLM_Classification',
        'LLM_Source_URL',
        'ScrapingStatus',
        'TargetCountryCodes',
        'RunID'
    ]

    summary_columns_order = [
        'CompanyName',
        'GivenURL',
        'GivenPhoneNumber',
        'Original_Number_Status',
        'Top_Number_1',
        'Top_Type_1',
        'Description',
        'ScrapingStatus_Canonical', # This will be the 'ScrapingStatus' column requested by user
        'CanonicalEntryURL',
        'Top_Number_1', # Repeated as per user request
        'Top_Type_1',   # Repeated as per user request
        'Top_Number_2',
        'Top_Type_2',
        'Top_Number_3',
        'Top_Type_3',
        'Top_SourceURL_1',
        'Top_SourceURL_2',
        'Top_SourceURL_3',
        'TargetCountryCodes',
        'RunID'
    ]

    tertiary_report_columns_order = [
        'CompanyName',
        'GivenURL',
        'CanonicalEntryURL',
        # 'Description', # Removed as per plan docs/top_contacts_report_refactor_plan_20250520_140819.md
        'ScrapingStatus', # This will map to ScrapingStatus_Canonical
        'PhoneNumber_1',
        'PhoneNumber_2',
        'PhoneNumber_3',
        'SourceURL_1',
        'SourceURL_2',
        'SourceURL_3'
    ]

    # --- Pass 2: Building Reports ---
    logger.info("Starting Pass 2: Building Detailed Flattened and Summary Reports...")

    # A. Detailed Flattened Report - Populate all_flattened_rows
    # This report iterates original input rows. For each, it finds the consolidated data for its true base domain.
    classification_precedence = { # Define once for de-duplication
        'Primary': 1, 'Secondary': 2, 'Support': 3,
        'Low Relevance': 4, 'Non-Business': 5, None: 99
    }

    for index, original_row_data in df.iterrows(): # Iterate original input rows
        company_name_pass2 = str(original_row_data.get('CompanyName', f"Row_{index}"))
        given_url_pass2 = original_row_data.get('GivenURL')
        canonical_url_pass2 = original_row_data.get('CanonicalEntryURL')
        scraper_status_pass2 = original_row_data.get('ScrapingStatus')

        # Access consolidated data using the true_base_domain_for_row (which is canonical_url_pass2)
        company_contact_details_pass2: Optional[CompanyContactDetails] = None
        if canonical_url_pass2 and canonical_url_pass2 in final_consolidated_data_by_true_base: # Use new global data
            company_contact_details_pass2 = final_consolidated_data_by_true_base[canonical_url_pass2]
        
        # Use scraper status for the true_base_domain
        scraper_status_for_true_base_detailed = true_base_scraper_status.get(str(canonical_url_pass2), "Unknown") if canonical_url_pass2 else "Unknown_NoTrueBase"

        if scraper_status_for_true_base_detailed == "Success" and company_contact_details_pass2 and company_contact_details_pass2.consolidated_numbers:
            # Iterate through sorted consolidated numbers
            for consolidated_number_item in company_contact_details_pass2.consolidated_numbers:
                # For the detailed report, we want to show each unique number and its aggregated sources.
                # The classification is already the "best" one for that number.
                
                # Aggregate types and source URLs for this number
                aggregated_types = []
                aggregated_source_urls = []
                seen_types_for_number = set() # To avoid "Sales, Sales" if type is same from different paths
                
                for source_detail in consolidated_number_item.sources:
                    type_with_path = f"{source_detail.type} (from {source_detail.source_path})"
                    if source_detail.type not in seen_types_for_number: # Add distinct types
                        aggregated_types.append(source_detail.type)
                        seen_types_for_number.add(source_detail.type)
                    if source_detail.original_full_url not in aggregated_source_urls: # Add distinct full URLs
                         aggregated_source_urls.append(source_detail.original_full_url)

                llm_type_str = ", ".join(aggregated_types) if aggregated_types else consolidated_number_item.sources[0].type if consolidated_number_item.sources else "Unknown"
                llm_source_url_str = ", ".join(aggregated_source_urls) if aggregated_source_urls else consolidated_number_item.sources[0].original_full_url if consolidated_number_item.sources else "N/A"

                new_flattened_row: Dict[str, Any] = {
                    'CompanyName': company_name_pass2,
                    'Number': consolidated_number_item.number,
                    'LLM_Type': llm_type_str, # Aggregated types
                    'LLM_Classification': consolidated_number_item.classification, # Best classification for this number
                    'LLM_Source_URL': llm_source_url_str, # Aggregated source URLs
                    'ScrapingStatus': scraper_status_for_true_base_detailed, # Use status of true_base_domain
                    'TargetCountryCodes': original_row_data.get('TargetCountryCodes'),
                    'RunID': run_id # Uses the date/time-based run_id
                }
                all_flattened_rows.append(new_flattened_row)
            # else: No unique relevant numbers from LLM for this successfully scraped canonical site - no row in detailed.
        # else: Scraping failed or no canonical URL or no consolidated data for this canonical - no row in detailed.
        
        # Old Tertiary report logic removed here. It will be rebuilt after this loop.

    # --- End of Loop for Detailed Flattened Report (and old Tertiary) ---

    # --- New Aggregation Step for Top_Contacts_Report (Tertiary Report) ---
    logger.info("Starting Aggregation for Top_Contacts_Report...")
    top_contacts_aggregation_map: Dict[str, Dict[str, Any]] = {}

    if 'CanonicalEntryURL' not in df.columns:
        logger.error("'CanonicalEntryURL' column is missing from DataFrame. This is critical for Top_Contacts_Report aggregation. Initializing to None.")
        df['CanonicalEntryURL'] = None
    if 'CompanyName' not in df.columns:
        logger.error("'CompanyName' column is missing from DataFrame. This is critical for Top_Contacts_Report aggregation. Initializing to 'Unknown_Input_Company'.")
        df['CompanyName'] = "Unknown_Input_Company"
    if 'GivenURL' not in df.columns:
        logger.error("'GivenURL' column is missing from DataFrame. This is critical for Top_Contacts_Report aggregation. Initializing to 'Unknown_Input_GivenURL'.")
        df['GivenURL'] = "Unknown_Input_GivenURL"

    # This loop iterates through final_consolidated_data_by_true_base which is already keyed by true_base_domain
    for true_base_domain_key_agg, company_contact_details_object in final_consolidated_data_by_true_base.items():
        if company_contact_details_object is None:
            logger.warning(f"Skipping true_base_domain '{true_base_domain_key_agg}' for Top_Contacts_Report aggregation as its CompanyContactDetails is None.")
            continue

        # Find all original input rows from df that map to this true_base_domain_key_agg
        # df['CanonicalEntryURL'] should store the true_base_domain
        matching_input_rows = df[df['CanonicalEntryURL'].astype(str) == str(true_base_domain_key_agg)]

        unique_original_company_names: Set[str]
        unique_original_given_urls: Set[str]

        if matching_input_rows.empty:
            logger.warning(f"No input rows found in df mapping to true_base_domain '{true_base_domain_key_agg}'. "
                           f"Using company name ('{company_contact_details_object.company_name}') from CompanyContactDetails and its original_input_urls as fallback.")
            unique_original_company_names = {str(company_contact_details_object.company_name)} if company_contact_details_object.company_name else {"Unknown_Company"}
            unique_original_given_urls = set(map(str, company_contact_details_object.original_input_urls))
        else:
            unique_original_company_names = set(matching_input_rows['CompanyName'].dropna().astype(str))
            unique_original_given_urls = set(matching_input_rows['GivenURL'].dropna().astype(str))
            if not unique_original_company_names:
                 unique_original_company_names = {str(company_contact_details_object.company_name)} if company_contact_details_object.company_name else {"Unknown_Company"}
            if not unique_original_given_urls:
                 unique_original_given_urls = set(map(str, company_contact_details_object.original_input_urls))

        report_company_name = f"{true_base_domain_key_agg} - {' - '.join(sorted(list(unique_original_company_names)))}"
        report_given_urls = ", ".join(sorted(list(unique_original_given_urls)))
        
        top_contacts_aggregation_map[true_base_domain_key_agg] = {
            "report_company_name": report_company_name,
            "report_given_urls": report_given_urls,
            "canonical_entry_url": true_base_domain_key_agg, # This is the true base domain
            "scraper_status": true_base_scraper_status.get(true_base_domain_key_agg, "Unknown"), # Use status for true_base_domain
            "contact_details": company_contact_details_object,
            "all_input_companies_for_canonical": sorted(list(unique_original_company_names))
        }
    logger.info(f"Aggregation for Top_Contacts_Report complete. Found {len(top_contacts_aggregation_map)} unique canonical URLs to report on.")

    # C. Top_Contacts_Report (formerly Tertiary Report) - Populate all_tertiary_rows from aggregated data
    logger.info("Building Top_Contacts_Report (formerly Tertiary) from aggregated data...")
    all_tertiary_rows.clear()

    for aggregated_entry in top_contacts_aggregation_map.values():
        company_contact_details_for_report = aggregated_entry["contact_details"]
        
        new_tertiary_row: Dict[str, Any] = {
            'CompanyName': aggregated_entry["report_company_name"],
            'GivenURL': aggregated_entry["report_given_urls"],
            'CanonicalEntryURL': aggregated_entry["canonical_entry_url"],
            'ScrapingStatus': aggregated_entry["scraper_status"],
            'PhoneNumber_1': None, 'PhoneNumber_2': None, 'PhoneNumber_3': None,
            'SourceURL_1': None, 'SourceURL_2': None, 'SourceURL_3': None
        }

        if company_contact_details_for_report and company_contact_details_for_report.consolidated_numbers:
            # Filter numbers based on EXCLUDED_TYPES_FOR_TOP_CONTACTS_REPORT
            eligible_numbers_for_report: List[ConsolidatedPhoneNumber] = []
            for cn_item in company_contact_details_for_report.consolidated_numbers:
                source_types = {s.type for s in cn_item.sources if s.type}
                if cn_item.classification != 'Non-Business' and \
                   not EXCLUDED_TYPES_FOR_TOP_CONTACTS_REPORT.intersection(source_types):
                    eligible_numbers_for_report.append(cn_item)
                else:
                    excluded_reasons = []
                    if cn_item.classification == 'Non-Business':
                        excluded_reasons.append("classification is Non-Business")
                    intersecting_types = EXCLUDED_TYPES_FOR_TOP_CONTACTS_REPORT.intersection(source_types)
                    if intersecting_types:
                        excluded_reasons.append(f"excluded types: {intersecting_types}")
                    logger.debug(f"Excluding number {cn_item.number} from Top_Contacts_Report for company '{aggregated_entry['report_company_name']}' due to: {'; '.join(excluded_reasons)}")

            # all_input_companies_str = ", ".join(aggregated_entry["all_input_companies_for_canonical"]) # Keep this for the main CompanyName column if needed, but for individual numbers, derive from sources.

            for i, consolidated_number_item in enumerate(eligible_numbers_for_report[:3]): # Use filtered list
                phone_num_key = f'PhoneNumber_{i+1}'
                source_url_key = f'SourceURL_{i+1}'
                
                number_str = consolidated_number_item.number
                types_str = ", ".join(sorted(list(set(s.type for s in consolidated_number_item.sources))))
                
                # Get unique original input company names specifically for *this* phone number's sources
                companies_for_this_number = sorted(list(set(
                    s.original_input_company_name
                    for s in consolidated_number_item.sources
                    if s.original_input_company_name
                )))
                companies_for_this_number_str = ", ".join(companies_for_this_number) if companies_for_this_number else "UnknownCompany" # Fallback if somehow empty

                new_tertiary_row[phone_num_key] = f"{number_str} ({types_str}) [{companies_for_this_number_str}]"
                new_tertiary_row[source_url_key] = ", ".join(sorted(list(set(s.original_full_url for s in consolidated_number_item.sources))))
        
        # Only add the row to the report if it actually has at least one phone number populated after filtering
        # The check for new_tertiary_row['PhoneNumber_1'] etc. effectively determines if eligible_numbers_for_report was non-empty
        if new_tertiary_row['PhoneNumber_1'] or new_tertiary_row['PhoneNumber_2'] or new_tertiary_row['PhoneNumber_3']:
            all_tertiary_rows.append(new_tertiary_row)
        else:
            # This log message will trigger if no numbers remained after filtering OR if there were no numbers to begin with.
            logger.info(f"Skipping row for canonical URL '{aggregated_entry['canonical_entry_url']}' (Company: '{aggregated_entry['report_company_name']}') in Top_Contacts_Report as it has no eligible phone numbers after filtering.")
            
    logger.info(f"Finished building Top_Contacts_Report. {len(all_tertiary_rows)} rows created.")


    # B. Summary Report - Populate specific columns in main 'df' (This section remains per-input-row)
    for index, row_summary in df.iterrows():
        given_url_summary = str(row_summary.get('GivenURL')) if row_summary.get('GivenURL') is not None else "None_GivenURL_Input"
        # canonical_url_summary is the true_base_domain for this input row
        canonical_url_summary = row_summary.get('CanonicalEntryURL')
        # scraper_status_summary_original_pass1 is the original scraper status from Pass 1 for the input row's specific pathful URL processing
        scraper_status_summary_original_pass1 = row_summary.get('ScrapingStatus')

        # Get the globally consolidated data for this true_base_domain (canonical_url_summary)
        company_contact_details_summary: Optional[CompanyContactDetails] = None
        if canonical_url_summary and canonical_url_summary in final_consolidated_data_by_true_base: # Ensure this was already correct
            company_contact_details_summary = final_consolidated_data_by_true_base[canonical_url_summary]

        # The consolidated_numbers list is already de-duplicated and sorted by classification
        unique_sorted_consolidated_numbers: List[ConsolidatedPhoneNumber] = []
        if company_contact_details_summary:
            unique_sorted_consolidated_numbers = company_contact_details_summary.consolidated_numbers

        # Populate Top_Number_1, Top_Type_1, Top_SourceURL_1
        if len(unique_sorted_consolidated_numbers) > 0:
            top_item_1 = unique_sorted_consolidated_numbers[0]
            df.at[index, 'Top_Number_1'] = top_item_1.number
            df.at[index, 'Top_Type_1'] = ", ".join(list(set(s.type for s in top_item_1.sources))) # Concatenate unique types
            df.at[index, 'Top_SourceURL_1'] = ", ".join(list(set(s.original_full_url for s in top_item_1.sources))) # Concatenate unique source URLs
        # Populate Top_Number_2, Top_Type_2, Top_SourceURL_2
        if len(unique_sorted_consolidated_numbers) > 1:
            top_item_2 = unique_sorted_consolidated_numbers[1]
            df.at[index, 'Top_Number_2'] = top_item_2.number
            df.at[index, 'Top_Type_2'] = ", ".join(list(set(s.type for s in top_item_2.sources)))
            df.at[index, 'Top_SourceURL_2'] = ", ".join(list(set(s.original_full_url for s in top_item_2.sources)))
        # Populate Top_Number_3, Top_Type_3, Top_SourceURL_3
        if len(unique_sorted_consolidated_numbers) > 2:
            top_item_3 = unique_sorted_consolidated_numbers[2]
            df.at[index, 'Top_Number_3'] = top_item_3.number
            df.at[index, 'Top_Type_3'] = ", ".join(list(set(s.type for s in top_item_3.sources)))
            df.at[index, 'Top_SourceURL_3'] = ", ".join(list(set(s.original_full_url for s in top_item_3.sources)))

        # Determine Original_Number_Status
        original_norm_phone_summary = row_summary.get('NormalizedGivenPhoneNumber')
        found_original_in_top_llm = False
        if original_norm_phone_summary and original_norm_phone_summary != "InvalidFormat":
            for top_num_item in unique_sorted_consolidated_numbers[:3]: # Check against top 3 populated numbers
                if top_num_item.number == original_norm_phone_summary:
                    found_original_in_top_llm = True
                    break
        
        if original_norm_phone_summary and original_norm_phone_summary != "InvalidFormat":
            if found_original_in_top_llm:
                df.at[index, 'Original_Number_Status'] = 'Verified'
            elif unique_sorted_consolidated_numbers: # Consolidated data has numbers, but original wasn't among them
                df.at[index, 'Original_Number_Status'] = 'Corrected'
            # If consolidated data exists for canonical but has no numbers
            elif company_contact_details_summary and not company_contact_details_summary.consolidated_numbers:
                 df.at[index, 'Original_Number_Status'] = 'LLM_OutputEmpty_Or_NoRelevant_For_Canonical' # Simplified
            elif company_contact_details_summary: # Consolidated data exists, had numbers, but after filtering unique_sorted_consolidated_numbers is empty (should not happen if logic is correct)
                 df.at[index, 'Original_Number_Status'] = 'No Relevant Match Found by LLM' # Should be covered by above
            else: # LLM did not run or had no output for this canonical URL (e.g. scrape fail)
                 df.at[index, 'Original_Number_Status'] = 'LLM_Not_Run_Or_NoOutput_For_Canonical'
        elif original_norm_phone_summary == "InvalidFormat":
            df.at[index, 'Original_Number_Status'] = 'Original_InvalidFormat'
        else: # No original phone number provided
            df.at[index, 'Original_Number_Status'] = 'Original_Not_Provided'

        # Determine Overall_VerificationStatus (This is a general status for the row, can be simplified or enhanced based on new top numbers)
        # For now, let's base it on whether any top LLM number was found.
        overall_status = "Unverified" # Default
        # Determine overall_status based on the true_base_domain's consolidated data and scraper status
        scraper_status_for_true_base_domain_summary = true_base_scraper_status.get(str(canonical_url_summary), "Unknown") if canonical_url_summary else "Unknown_NoTrueBase"

        if scraper_status_for_true_base_domain_summary != "Success":
            overall_status = f"Unverified_Scrape_{scraper_status_for_true_base_domain_summary}"
        elif unique_sorted_consolidated_numbers: # If any top number was found in the consolidated data for the true_base_domain
            overall_status = "Verified_LLM_Match_Found"
        elif company_contact_details_summary and not company_contact_details_summary.consolidated_numbers: # True base domain processed, but no relevant numbers
            overall_status = "Unverified_LLM_NoRelevantNumbers"
        elif scraper_status_for_true_base_domain_summary == "Error_LLM_Processing":
            overall_status = "Error_LLM_Processing_For_Canonical"
        elif scraper_status_for_true_base_domain_summary == "Error_LLM_PromptMissing":
            overall_status = "Error_LLM_PromptMissing_For_Canonical"
        # else: remains "Unverified" if true_base_domain was success but LLM found nothing relevant (covered by Unverified_LLM_NoRelevantNumbers)
        # else: stays "Unverified"
        
        # Prepend redirect info if applicable
        # input_to_canonical_map stores true_base_domain for the original input URL
        original_input_url_for_map = str(row_summary.get('GivenURL')) if row_summary.get('GivenURL') is not None else "None_GivenURL_Input"
        true_base_domain_from_map = input_to_canonical_map.get(original_input_url_for_map) # This is already a true base domain

        # Compare the original input URL (after normalization to a base domain) with the true_base_domain stored for the row
        normalized_original_input_base = get_canonical_base_url(original_input_url_for_map) if original_input_url_for_map != "None_GivenURL_Input" else None
        
        if canonical_url_summary and normalized_original_input_base and normalized_original_input_base != canonical_url_summary:
            # This means the original input URL's base domain was different from the final canonical base domain for this row (e.g. major redirect)
            overall_status = f"RedirectedTo[{canonical_url_summary}]_" + overall_status
        
        df.at[index, 'Overall_VerificationStatus'] = overall_status
        df.at[index, 'ScrapingStatus_Canonical'] = scraper_status_for_true_base_domain_summary # Use status of true_base_domain
        df.at[index, 'LLM_Processing_Status_Canonical'] = "Processed" if company_contact_details_summary is not None else scraper_status_for_true_base_domain_summary


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
            by=['CompanyName', 'LLM_Classification_Sort', 'Number'],
            na_position='last' # Ensure NaNs in sort key are handled if any
        ).drop(columns=['LLM_Classification_Sort'])
        
        # Ensure all columns are present, fill missing with None or empty string
        for col in detailed_columns_order:
            if col not in df_detailed_flattened.columns:
                df_detailed_flattened[col] = None # Or appropriate default like ''
        
        df_detailed_export = df_detailed_flattened[detailed_columns_order].copy()

        detailed_output_filename = f"All_LLM_Extractions_Report_{run_id}.xlsx" # Updated filename
        detailed_output_excel_path = os.path.join(run_output_dir, detailed_output_filename)
        try:
            logger.info(f"Attempting to save detailed report to: {detailed_output_excel_path}")
            with pd.ExcelWriter(detailed_output_excel_path, engine='openpyxl') as writer:
                df_detailed_export.to_excel(writer, index=False, sheet_name='Detailed_Phone_Data')
                # Auto-adjust column widths for detailed report
                worksheet_detailed = writer.sheets['Detailed_Phone_Data']
                for col_idx, col_name in enumerate(df_detailed_export.columns):
                    series_data = df_detailed_export.iloc[:, col_idx]
                    if series_data.empty:
                        max_val_len = 0
                    else:
                        lengths = series_data.astype(str).map(len)
                        max_val_len = lengths.max() if not lengths.empty else 0
                    
                    column_header_len = len(str(col_name))
                    adjusted_width = max(max_val_len, column_header_len) + 2
                    worksheet_detailed.column_dimensions[get_column_letter(col_idx + 1)].width = adjusted_width
            logger.info(f"Detailed report saved successfully to {detailed_output_excel_path}")
        except Exception as e_detailed:
            logger.error(f"Error saving detailed report to {detailed_output_excel_path}: {e_detailed}", exc_info=True)
    else:
        logger.info("No data for detailed flattened report. Skipping file creation.")

    # Prepare and save Summary Report (from the modified main df)
    # Ensure all columns for the summary report exist in df, initializing if necessary.
    # The summary_columns_order list defines what we want. We iterate through its unique names.
    unique_summary_cols_needed = list(dict.fromkeys(summary_columns_order)) # Get unique column names while preserving order for first occurrences

    for col_name in unique_summary_cols_needed:
        if col_name not in df.columns:
            # Initialize columns that are expected to be derived or set during the pipeline
            if col_name in ['Original_Number_Status', 'Overall_VerificationStatus',
                            'CanonicalEntryURL', 'ScrapingStatus_Canonical', 'LLM_Processing_Status_Canonical',
                            'Top_Number_1', 'Top_Type_1', 'Top_SourceURL_1',
                            'Top_Number_2', 'Top_Type_2', 'Top_SourceURL_2',
                            'Top_Number_3', 'Top_Type_3', 'Top_SourceURL_3']:
                df[col_name] = None # Default to None if not populated
                logger.warning(f"Summary report column '{col_name}' was not found in DataFrame and was initialized to None. Check population logic.")
            elif col_name == 'RunID':
                df[col_name] = run_id # Should always be available
            # Columns like CompanyName, GivenURL, GivenPhoneNumber, Description, TargetCountryCodes
            # are expected from load_and_preprocess_data. If missing here, it's a more fundamental issue.
            # However, the required_cols initialization at the top should have handled these.
            # This loop is an additional safeguard.
            elif col_name not in ['CompanyName', 'GivenURL', 'GivenPhoneNumber', 'Description', 'TargetCountryCodes']:
                 logger.error(f"Unexpected summary column '{col_name}' missing and not covered by specific initialization. Defaulting to None.")
                 df[col_name] = None


    # Select columns for export based on summary_columns_order.
    # All unique names in summary_columns_order should now exist in df due to the loop above.
    # If a column name is repeated in summary_columns_order, it will be included multiple times.
    df_summary_export = df[summary_columns_order].copy()
    
    summary_output_filename = app_config.output_excel_file_name_template.format(run_id=run_id)
    summary_output_excel_path = os.path.join(run_output_dir, summary_output_filename)
    try:
        logger.info(f"Attempting to save summary report to: {summary_output_excel_path}")
        with pd.ExcelWriter(summary_output_excel_path, engine='openpyxl') as writer:
            df_summary_export.to_excel(writer, index=False, sheet_name='Phone_Validation_Summary')
            # Auto-adjust column widths for summary report
            worksheet_summary = writer.sheets['Phone_Validation_Summary']
            for col_idx, col_name in enumerate(df_summary_export.columns):
                series_data = df_summary_export.iloc[:, col_idx]
                if series_data.empty:
                    max_val_len = 0
                else:
                    lengths = series_data.astype(str).map(len)
                    max_val_len = lengths.max() if not lengths.empty else 0
                
                column_header_len = len(str(col_name))
                adjusted_width = max(max_val_len, column_header_len) + 2
                worksheet_summary.column_dimensions[get_column_letter(col_idx + 1)].width = adjusted_width
        logger.info(f"Summary report saved successfully to {summary_output_excel_path}")
    except Exception as e_summary:
        logger.error(f"Error saving summary report to {summary_output_excel_path}: {e_summary}", exc_info=True)

    # Create and save new Tertiary Report
    if all_tertiary_rows:
        df_tertiary_report = pd.DataFrame(all_tertiary_rows)
        
        # Ensure all columns are present as per tertiary_report_columns_order
        for col_t in tertiary_report_columns_order:
            if col_t not in df_tertiary_report.columns:
                df_tertiary_report[col_t] = None # Initialize if missing
        
        df_tertiary_export = df_tertiary_report[tertiary_report_columns_order].copy()

        tertiary_output_filename = app_config.tertiary_report_file_name_template.format(run_id=run_id)
        tertiary_output_excel_path = os.path.join(run_output_dir, tertiary_output_filename)
        try:
            logger.info(f"Attempting to save tertiary report to: {tertiary_output_excel_path}")
            with pd.ExcelWriter(tertiary_output_excel_path, engine='openpyxl') as writer_t:
                df_tertiary_export.to_excel(writer_t, index=False, sheet_name='Contact_Focused_Report')
                # Auto-adjust column widths
                worksheet_tertiary = writer_t.sheets['Contact_Focused_Report']
                for col_idx, col_name in enumerate(df_tertiary_export.columns):
                    series_data = df_tertiary_export.iloc[:, col_idx]
                    if series_data.empty:
                        max_val_len = 0
                    else:
                        lengths = series_data.astype(str).map(len)
                        max_val_len = lengths.max() if not lengths.empty else 0
                    
                    column_header_len = len(str(col_name))
                    adjusted_width = max(max_val_len, column_header_len) + 2
                    worksheet_tertiary.column_dimensions[get_column_letter(col_idx + 1)].width = adjusted_width
            logger.info(f"Tertiary report saved successfully to {tertiary_output_excel_path}")
        except Exception as e_tertiary:
            logger.error(f"Error saving tertiary report to {tertiary_output_excel_path}: {e_tertiary}", exc_info=True)
    else:
        logger.info("No data for tertiary report. Skipping file creation.")

    logger.info(f"Pipeline run {run_id} finished.")
    total_duration = time.time() - datetime.strptime(run_id, "%Y%m%d_%H%M%S").timestamp()
    logger.info(f"Total pipeline duration: {total_duration:.2f} seconds.")


if __name__ == '__main__':
    # This basic setup is for when the script is run directly.
    # The main() function will then call the more detailed setup_logging.
    if not logger.hasHandlers(): # Ensure basic config if run directly and not imported
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    main()