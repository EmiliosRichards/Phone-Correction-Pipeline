import os
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables from .env file
# Try loading from ../.env (relative to src/core) then ../../.env (relative to src)
# This covers running scripts from src/core, src, or phone_validation_pipeline root.
dotenv_path_1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env') # phone_validation_pipeline/.env
dotenv_path_2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.env') # workspace root if src is nested deeper

# Fallback for running main_pipeline.py from phone_validation_pipeline directory
dotenv_path_project_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')


loaded_env = False
if os.path.exists(dotenv_path_1):
    load_dotenv(dotenv_path_1)
    loaded_env = True
elif os.path.exists(dotenv_path_2):
    load_dotenv(dotenv_path_2)
    loaded_env = True
elif os.path.exists(dotenv_path_project_root):
    load_dotenv(dotenv_path_project_root)
    loaded_env = True
else:
    print(f"Warning: .env file not found at {dotenv_path_1}, {dotenv_path_2}, or {dotenv_path_project_root}. Using default configurations or expecting environment variables to be set externally.")


class AppConfig:
    """
    Manages application configurations, loading settings primarily from environment
    variables defined in a .env file.

    This class centralizes all configurable parameters for the phone validation
    pipeline, including scraper settings, output directories, LLM parameters,
    phone number normalization rules, and data handling paths. It provides
    default values for most settings if they are not specified in the environment.

    Attributes:
        user_agent (str): User-agent string for web scraping.
        default_page_timeout (int): Default timeout for page operations in milliseconds.
        default_navigation_timeout (int): Default timeout for navigation actions in milliseconds.
        scrape_max_retries (int): Maximum retries for a failed scrape attempt.
        scrape_retry_delay_seconds (int): Delay in seconds between scrape retries.
        
        target_link_keywords (List[str]): General keywords to identify potentially relevant internal links.
        scraper_critical_priority_keywords (List[str]): Keywords indicating top-priority pages if found as standalone path segments.
        scraper_high_priority_keywords (List[str]): Keywords indicating high-priority pages if found as standalone path segments.
        scraper_max_keyword_path_segments (int): Max path segments for a priority keyword to retain its highest score tier.
        scraper_exclude_link_path_patterns (List[str]): URL path patterns to hard-exclude from scraping.
        scraper_max_pages_per_domain (int): Max pages to scrape per domain (0 for no limit).
        scraper_min_score_to_queue (int): Minimum score a link needs to be added to the scrape queue.
        scraper_score_threshold_for_limit_bypass (int): Score threshold for a page to bypass the max_pages_per_domain limit.
        
        max_depth_internal_links (int): Maximum depth to follow internal links.
        scraper_networkidle_timeout_ms (int): Timeout in ms for Playwright's networkidle wait. 0 to disable.
        snippet_window_chars (int): Number of characters before/after a regex match for snippet extraction.
        
        output_base_dir (str): Base directory for output files.
        scraped_content_subdir (str): Subdirectory name for storing scraped content.
        llm_context_subdir (str): Subdirectory name for storing LLM context/raw responses.
        filename_company_name_max_len (int): Maximum length for the sanitized company name part of output filenames.
        
        respect_robots_txt (bool): Whether the scraper should respect robots.txt.
        robots_txt_user_agent (str): User-agent string for checking robots.txt.
        
        gemini_api_key (Optional[str]): API key for Google Gemini.
        llm_model_name (str): Specific Google Gemini model to use.
        llm_temperature (float): Temperature for LLM response generation.
        llm_max_tokens (int): Maximum tokens for LLM response.
        llm_prompt_template_path (str): Path to the LLM prompt template file.
        
        target_country_codes (List[str]): Target country codes for phone number parsing.
        default_region_code (Optional[str]): Default region code for phone number parsing.
        
        input_excel_file_path (str): Path to the input data file.
        output_excel_file_name_template (str): Template for the output Excel file name.
        skip_rows_config (Optional[int]): Number of rows to skip from the start of the input file (0-indexed).
        nrows_config (Optional[int]): Number of rows to read after skipping. None means read to end.
        
        log_level (str): Logging level for the file log (e.g., INFO, DEBUG).
        console_log_level (str): Logging level for console output (e.g., WARNING, INFO).

    Methods:
        __init__(): Initializes the AppConfig instance by loading values from
                    environment variables or using defaults.
    """

    def __init__(self):
        """
        Initializes the AppConfig instance.

        Loads all configuration parameters from environment variables using `os.getenv()`.
        If an environment variable is not set for a particular configuration, a
        predefined default value is used. It also handles type conversions for
        parameters like integers, floats, booleans, and lists from their string
        representations in environment variables.
        """
        # --- Scraper Configuration ---
        self.user_agent: str = os.getenv('SCRAPER_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        self.default_page_timeout: int = int(os.getenv('SCRAPER_PAGE_TIMEOUT_MS', '30000'))
        self.default_navigation_timeout: int = int(os.getenv('SCRAPER_NAVIGATION_TIMEOUT_MS', '60000'))
        self.scrape_max_retries: int = int(os.getenv('SCRAPER_MAX_RETRIES', '2'))
        self.scrape_retry_delay_seconds: int = int(os.getenv('SCRAPER_RETRY_DELAY_SECONDS', '5'))
        
        # Link Prioritization and Control Settings
        target_link_keywords_str: str = os.getenv('TARGET_LINK_KEYWORDS', 'contact,about,support,impressum,kontakt,legal,privacy,terms,hilfe,datenschutz,ueber-uns')
        self.target_link_keywords: List[str] = [kw.strip().lower() for kw in target_link_keywords_str.split(',') if kw.strip()]
        
        critical_priority_keywords_str: str = os.getenv('SCRAPER_CRITICAL_PRIORITY_KEYWORDS', 'impressum,kontakt,contact,imprint')
        self.scraper_critical_priority_keywords: List[str] = [kw.strip().lower() for kw in critical_priority_keywords_str.split(',') if kw.strip()]
        
        high_priority_keywords_str: str = os.getenv('SCRAPER_HIGH_PRIORITY_KEYWORDS', 'legal,privacy,terms,datenschutz,ueber-uns,about,about-us')
        self.scraper_high_priority_keywords: List[str] = [kw.strip().lower() for kw in high_priority_keywords_str.split(',') if kw.strip()]
        
        self.scraper_max_keyword_path_segments: int = int(os.getenv('SCRAPER_MAX_KEYWORD_PATH_SEGMENTS', '3'))
        
        exclude_link_patterns_str: str = os.getenv('SCRAPER_EXCLUDE_LINK_PATH_PATTERNS', '/media/,/blog/,/wp-content/,/video/,/hilfe-video/')
        self.scraper_exclude_link_path_patterns: List[str] = [p.strip().lower() for p in exclude_link_patterns_str.split(',') if p.strip()]
        
        self.scraper_max_pages_per_domain: int = int(os.getenv('SCRAPER_MAX_PAGES_PER_DOMAIN', '20')) # Default 20, 0 for no limit
        self.scraper_min_score_to_queue: int = int(os.getenv('SCRAPER_MIN_SCORE_TO_QUEUE', '40'))
        self.scraper_score_threshold_for_limit_bypass: int = int(os.getenv('SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS', '80'))

        # Existing Scraper Settings
        self.max_depth_internal_links: int = int(os.getenv('MAX_DEPTH_INTERNAL_LINKS', '1'))
        self.scraper_networkidle_timeout_ms: int = int(os.getenv('SCRAPER_NETWORKIDLE_TIMEOUT_MS', '3000')) # Default 3s, 0 to disable
        self.snippet_window_chars: int = int(os.getenv('SNIPPET_WINDOW_CHARS', '300')) # Character window for snippets, default 300 chars

        # --- Output Configuration ---
        self.output_base_dir: str = os.getenv('OUTPUT_BASE_DIR', 'output_data') # Relative to phone_validation_pipeline
        self.scraped_content_subdir: str = 'scraped_content'
        self.llm_context_subdir: str = 'llm_context' # New subdir for LLM raw responses
        self.filename_company_name_max_len: int = int(os.getenv('FILENAME_COMPANY_NAME_MAX_LEN', '25')) # Default to 25

        # --- Robots.txt Handling ---
        self.respect_robots_txt: bool = os.getenv('RESPECT_ROBOTS_TXT', 'True').lower() == 'true'
        self.robots_txt_user_agent: str = os.getenv('ROBOTS_TXT_USER_AGENT', '*')

        # --- LLM Configuration ---
        self.gemini_api_key: Optional[str] = os.getenv('GEMINI_API_KEY')
        self.llm_model_name: str = os.getenv('LLM_MODEL_NAME', 'gemini-1.5-pro-latest') # Default to a capable model
        self.llm_temperature: float = float(os.getenv('LLM_TEMPERATURE', '0.5'))
        self.llm_max_tokens: int = int(os.getenv('LLM_MAX_TOKENS', '8192')) # Increased default
        
        # Path to the prompt template, relative to the phone_validation_pipeline directory
        self.llm_prompt_template_path: str = os.getenv('LLM_PROMPT_TEMPLATE_PATH', 'prompts/gemini_phone_validation_v1.txt')

        # --- Phone Number Normalization Configuration ---
        target_country_codes_str: str = os.getenv('TARGET_COUNTRY_CODES', 'DE,CH,AT') # Germany, Switzerland, Austria
        self.target_country_codes: List[str] = [code.strip().upper() for code in target_country_codes_str.split(',') if code.strip()]
        self.default_region_code: Optional[str] = os.getenv('DEFAULT_REGION_CODE', 'DE') # Default region for parsing if others fail

        # --- Data Handling ---
        self.input_excel_file_path: str = os.getenv('INPUT_EXCEL_FILE_PATH', 'data_to_be_inputed.xlsx') # Relative to phone_validation_pipeline
        self.output_excel_file_name_template: str = os.getenv('OUTPUT_EXCEL_FILE_NAME_TEMPLATE', 'phone_validation_output_{run_id}.xlsx')

        # --- Row Processing Range Configuration ---
        self.skip_rows_config: Optional[int] = None
        self.nrows_config: Optional[int] = None
        raw_row_range: Optional[str] = os.getenv('ROW_PROCESSING_RANGE', "")

        if raw_row_range:
            raw_row_range = raw_row_range.strip()
            if not raw_row_range or raw_row_range == "0":
                pass # Process all rows, skip_rows_config and nrows_config remain None
            elif '-' in raw_row_range:
                parts = raw_row_range.split('-', 1)
                start_str, end_str = parts[0].strip(), parts[1].strip()

                start_val: Optional[int] = None
                end_val: Optional[int] = None

                if start_str and start_str.isdigit():
                    start_val = int(start_str)
                
                if end_str and end_str.isdigit():
                    end_val = int(end_str)

                if start_val is not None and start_val > 0:
                    self.skip_rows_config = start_val - 1 # 0-indexed skip
                    if end_val is not None and end_val >= start_val:
                        self.nrows_config = end_val - start_val + 1
                    elif end_str == "": # Format "N-" (from N to end)
                        self.nrows_config = None # Read all after skipping
                    elif end_val is not None and end_val < start_val:
                        print(f"Warning: Invalid ROW_PROCESSING_RANGE '{raw_row_range}'. End value < Start value. Processing all rows.")
                        self.skip_rows_config = None
                        self.nrows_config = None
                elif start_str == "" and end_val is not None and end_val > 0: # Format "-M" (first M rows)
                    self.skip_rows_config = None # Or 0, effectively the same for pandas
                    self.nrows_config = end_val
                else:
                    print(f"Warning: Invalid ROW_PROCESSING_RANGE format '{raw_row_range}'. Expected N-M, N-, -M, or N. Processing all rows.")
            elif raw_row_range.isdigit() and int(raw_row_range) > 0: # Single number "N"
                self.skip_rows_config = None # Or 0
                self.nrows_config = int(raw_row_range)
            else:
                if raw_row_range != "0": # "0" is a valid way to say "all rows"
                    print(f"Warning: Invalid ROW_PROCESSING_RANGE value '{raw_row_range}'. Processing all rows.")
        
        # --- Logging Configuration ---
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.console_log_level: str = os.getenv('CONSOLE_LOG_LEVEL', 'WARNING').upper()


# For direct execution testing of this config file
# TODO: [FutureEnhancement] The __main__ block below was for direct script execution and testing of AppConfig.
# It demonstrates how configuration values are loaded and how paths are resolved.
# Commented out to prevent execution during normal library use.
# It can be uncommented for debugging or understanding standalone config script behavior.
# if __name__ == '__main__':
#     config = AppConfig()
#     print("--- AppConfig Loaded Values ---")
#     print(f"Loaded .env: {loaded_env}")
#     print(f"USER_AGENT: {config.user_agent}")
#     print(f"DEFAULT_PAGE_TIMEOUT: {config.default_page_timeout}")
#     print(f"TARGET_LINK_KEYWORDS: {config.target_link_keywords}")
#     print(f"SCRAPER_CRITICAL_PRIORITY_KEYWORDS: {config.scraper_critical_priority_keywords}")
#     print(f"SCRAPER_HIGH_PRIORITY_KEYWORDS: {config.scraper_high_priority_keywords}")
#     print(f"SCRAPER_MAX_KEYWORD_PATH_SEGMENTS: {config.scraper_max_keyword_path_segments}")
#     print(f"SCRAPER_EXCLUDE_LINK_PATH_PATTERNS: {config.scraper_exclude_link_path_patterns}")
#     print(f"SCRAPER_MAX_PAGES_PER_DOMAIN: {config.scraper_max_pages_per_domain}")
#     print(f"SCRAPER_MIN_SCORE_TO_QUEUE: {config.scraper_min_score_to_queue}")
#     print(f"SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS: {config.scraper_score_threshold_for_limit_bypass}")
#     print(f"GEMINI_API_KEY (exists): {'Yes' if config.gemini_api_key else 'No'}")
#     # ... print other relevant new and existing configs ...

#     # Test resolving paths relative to project root (phone_validation_pipeline)
#     project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # up two levels from core
#     print(f"Project root (expected for phone_validation_pipeline): {project_root}")
    
#     abs_prompt_path = os.path.join(project_root, config.llm_prompt_template_path)
#     print(f"Absolute LLM_PROMPT_TEMPLATE_PATH: {abs_prompt_path} (exists: {os.path.exists(abs_prompt_path)})")
    
#     abs_output_dir = os.path.join(project_root, config.output_base_dir)
#     print(f"Absolute OUTPUT_BASE_DIR: {abs_output_dir}")

#     abs_input_excel = os.path.join(project_root, config.input_excel_file_path)
#     print(f"Absolute INPUT_EXCEL_FILE_PATH: {abs_input_excel} (exists: {os.path.exists(abs_input_excel)})")