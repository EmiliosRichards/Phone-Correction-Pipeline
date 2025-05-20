# Phone Extraction Project - API Documentation

This document provides detailed information about the API of the Phone Extraction project.

## Module Structure

### `src.text` Package

#### `src.text.normalizer` Module

##### `normalize_text(text: Union[str, bytes], encoding: Optional[str] = None) -> str`

Normalizes text to UTF-8 encoding. Attempts to detect encoding if not provided.

- **Parameters:**
  - `text`: Input text as string or bytes.
  - `encoding`: Optional encoding to try first (if None, will be detected using `chardet`).
- **Returns:** Normalized text as UTF-8 string.
- **Raises:** `TypeError` if input text is not str or bytes.

##### `clean_text(text: str) -> str`

Cleans text by removing unnecessary characters (e.g., excessive whitespace, non-printable characters) while preserving those useful for phone number detection.

- **Parameters:**
  - `text`: Input text string.
- **Returns:** Cleaned text string.

##### `normalize_and_clean(text: Union[str, bytes], encoding: Optional[str] = None) -> str`

Normalizes text to UTF-8 and cleans it in one step. This is a convenience function combining `normalize_text` and `clean_text`.

- **Parameters:**
  - `text`: Input text as string or bytes.
  - `encoding`: Optional encoding to try first.
- **Returns:** Normalized and cleaned text as UTF-8 string.

### `src.phone` Package

#### `src.phone.extractor` Module

##### Constants

- `PRIORITY_REGIONS: Set[str]`: A set of region codes that are considered priority regions for phone number extraction. Currently includes 'DE', 'AT', and 'CH' (Germany, Austria, and Switzerland).
- `MIN_REPEATING_DIGITS: int`: The minimum number of repeating digits that will cause a phone number to be considered invalid (default: 5).
- `MIN_SEQUENTIAL_DIGITS: int`: The minimum number of sequential digits that will cause a phone number to be considered invalid (default: 8).
- `INVALID_PLACEHOLDERS: Set[str]`: A set of known placeholder phone numbers that should be rejected.

##### `is_valid_phone_number(number_str: str, region: Optional[str] = None, parsed_number: Optional[phonenumbers.PhoneNumber] = None) -> bool`

Validates if a string or a pre-parsed `phonenumbers.PhoneNumber` object represents a legitimate phone number.
It uses the `phonenumbers` library for initial checks and then applies custom rules (placeholder, repeating digits, sequential digits).

- **Parameters:**
  - `number_str`: The phone number string to validate.
  - `region`: The region code (e.g., "US", "DE") to use as a hint for parsing, especially for national numbers.
  - `parsed_number`: An optional pre-parsed `phonenumbers.PhoneNumber` object. If provided, `number_str` and `region` might be ignored for initial parsing.
- **Returns:** `True` if the number is considered valid after all checks, `False` otherwise.

##### `extract_phone_numbers(text: str, default_region: str = 'DE', use_twilio: bool = False) -> List[Dict[str, Any]]`

Extracts, validates, and optionally formats phone numbers from a given text.
It uses `phonenumbers.PhoneNumberMatcher` for finding potential numbers and `is_valid_phone_number` for validation.
Twilio validation can be enabled.

- **Parameters:**
  - `text`: The input text string to search for phone numbers.
  - `default_region`: The default region (e.g., 'DE', 'US') to assume for numbers that are not in international E.164 format. Helps parsing ambiguity. Default is 'DE'.
  - `use_twilio`: If `True`, attempt to validate numbers using Twilio API. Default is `False`.
- **Returns:** A list of dictionaries, where each dictionary represents a valid extracted phone number and contains:
  - `original`: The raw string as found in the text.
  - `e164`: The phone number in E.164 format (e.g., "+14155552671").
  - `region`: The region code inferred for the number (e.g., "US").
  - `priority_region`: Boolean, `True` if the number's region is in the `PRIORITY_REGIONS` set.
  - `position`: The starting index of the number in the original text.
  - `validation_api`: A dictionary containing results from the Twilio API if `use_twilio` was `True` and the call was made. Includes keys like `api_status`, `is_valid`, `type`, `error_message`, `details`.
  - `confidence_score`: A float indicating the confidence in the extracted number (default 0.0).

#### `src.phone.validator` Module

##### `init_twilio_client() -> Optional[twilio.rest.Client]`

Initializes and returns a Twilio REST client if `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are found in environment variables (loaded from `.env`).

- **Returns:** A `twilio.rest.Client` instance or `None` if credentials are not configured.

##### `validate_phone_number_twilio(phone_number_e164: str) -> Dict[str, Any]`

Validates a phone number using the Twilio Lookup v2 API.
Requires Twilio client to be initialized (i.e., credentials in `.env`).

- **Parameters:**
  - `phone_number_e164`: The phone number string in E.164 format.
- **Returns:** A dictionary containing:
  - `api_status`: "successful", "failed", or "skipped".
  - `is_valid`: Boolean, `True` if Twilio considers the number valid.
  - `error_message`: Error message if the API call failed or the number is invalid.
  - `details`: A dictionary with additional information from Twilio (e.g., `type`, `carrier_name`, `country_code`).

#### `src.phone.formatter` Module

##### `format_phone_number(number: str, format_type: str = 'E164', region: Optional[str] = None) -> str`

Formats a phone number string into a specified format using the `phonenumbers` library.

- **Parameters:**
  - `number`: The phone number string to format.
  - `format_type`: The desired format. Common values from `phonenumbers.PhoneNumberFormat` include:
    - `E164` (e.g., "+14155552671")
    - `INTERNATIONAL` (e.g., "+1 415-555-2671")
    - `NATIONAL` (e.g., "(415) 555-2671" for US)
    - `RFC3966` (e.g., "tel:+1-415-555-2671")
  - `region`: The region code (e.g., "US", "DE") required for `NATIONAL` formatting.
- **Returns:** The formatted phone number string, or the original number if formatting fails.

### `src.analysis` Package

#### `src.analysis.statistics` Module

##### `generate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]`

Generates statistics from phone number extraction results.
Example statistics include total numbers found, unique numbers, counts by region, etc.

- **Parameters:**
  - `results`: A list of dictionaries, where each dictionary is an output from `extract_phone_numbers`.
- **Returns:** A dictionary containing various statistics.

##### `save_results(data_to_save: Any, output_dir: Path, filename_base: str, timestamp: Optional[str] = None) -> Dict[str, Path]`

Saves processed data (e.g., extracted numbers, statistics) to files in JSON and TXT formats.

- **Parameters:**
  - `data_to_save`: The data to be saved. If a list of dicts (extracted numbers), it saves both JSON and a simple TXT list. If a dict (statistics), it saves as JSON.
  - `output_dir`: The base directory to save the results.
  - `filename_base`: The base name for the output files (e.g., "phone_numbers", "statistics").
  - `timestamp`: An optional timestamp string to create a subdirectory within `output_dir`. If `None`, uses the current time.
- **Returns:** A dictionary mapping file types ("json", "txt") to their `Path` objects.

##### `print_statistics(stats: Dict[str, Any]) -> None`

Prints statistics to the console in a readable format.

- **Parameters:**
  - `stats`: Dictionary containing statistics, typically the output of `generate_statistics`.

### `src.db_utils` Module

#### `get_db_connection() -> psycopg2.connection`

Establishes a connection to the PostgreSQL database.

- **Returns:** A connection object to the database.
- **Raises:**
  - `ValueError`: If required environment variables are missing.
  - `psycopg2.Error`: If connection to the database fails.

#### `insert_raw_phone_number(conn, phone_data: Dict[str, Any]) -> str`

Inserts a single raw phone number occurrence into the raw_phone_numbers table.

- **Parameters:**
  - `conn`: Database connection object.
  - `phone_data`: Dictionary containing phone number data to insert.
- **Returns:** The generated raw_phone_id.
- **Raises:** `psycopg2.Error` if the insertion fails.

#### `upsert_cleaned_phone_number(conn, phone_data: Dict[str, Any])`

Inserts or updates a cleaned phone number in the cleaned_phone_numbers table.

- **Parameters:**
  - `conn`: Database connection object.
  - `phone_data`: Dictionary containing phone number data to insert or update.
- **Raises:** `psycopg2.Error` if the upsert operation fails.

#### `update_scraping_log_error(conn, log_id: Any, error_message: str)`

Updates the error_message in the scraping_logs table for a given log_id.

- **Parameters:**
  - `conn`: Database connection object.
  - `log_id`: The ID of the log entry to update.
  - `error_message`: The error message to store.
- **Raises:** `psycopg2.Error` if the update fails.

#### `check_db_tables_exist(conn) -> bool`

Check if the required database tables exist.

- **Parameters:**
  - `conn`: Database connection object.
- **Returns:** `True` if all required tables exist, `False` otherwise.

### `src.utils` Package

#### `src.utils.logging_config` Module

##### `ensure_log_directory(log_dir: str = DEFAULT_LOG_DIR) -> None`

Ensure the log directory exists.

- **Parameters:**
  - `log_dir`: Path to the log directory.

##### `get_log_level() -> int`

Get the log level from environment variables or use default.

- **Returns:** The logging level as an integer.

##### `configure_logging(name: Optional[str] = None, log_file: Optional[str] = None, log_level: Optional[int] = None, log_format: Optional[str] = None, log_to_console: bool = True, log_to_file: bool = True, extra_handlers: Optional[list] = None) -> logging.Logger`

Configure logging with consistent settings.

- **Parameters:**
  - `name`: Logger name (usually __name__).
  - `log_file`: Path to the log file (if None, uses <name>.log).
  - `log_level`: Logging level (if None, uses environment variable LOG_LEVEL or INFO).
  - `log_format`: Log message format (if None, uses default format).
  - `log_to_console`: Whether to log to console.
  - `log_to_file`: Whether to log to file.
  - `extra_handlers`: Additional logging handlers to add.
- **Returns:** Configured logger instance.

##### `get_logger(name: str) -> logging.Logger`

Get a logger with the default configuration.

- **Parameters:**
  - `name`: Logger name (usually __name__).
- **Returns:** Configured logger instance.

## Command-line Scripts

Refer to `README.md` for updated information on running scripts and the main application. The scripts in the `scripts/` directory provide command-line interfaces for various operations:

- `scripts/normalize_text.py`: Normalizes raw text files.
- `scripts/extract_phones.py`: Extracts phone numbers from normalized text files.
- `scripts/analyze_results.py`: Analyzes extraction results.
- `scripts/init_db.py`: Initializes the database schema.

## Configuration

*   **Environment Variables (`.env` file):**
    *   `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
    *   `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
    *   `DB_HOST`: Database host (default: "localhost").
    *   `DB_PORT`: Database port (default: "5432").
    *   `DB_NAME`: Database name (default: "phone_extraction").
    *   `DB_USER`: Database user (default: "postgres").
    *   `DB_PASSWORD`: Database password (required for database operations).
    *   `LOG_LEVEL`: Logging level (default: "INFO").
    *   `PROCESSED_DIR`: Directory for processed data (default: "data/processed").

*   **`config/patterns.json`**: Contains custom regex patterns for special cases where the `phonenumbers` library might not detect certain formats. While the primary extraction mechanism relies on the `phonenumbers` library, these patterns can be used to supplement the extraction process for edge cases or region-specific formats.