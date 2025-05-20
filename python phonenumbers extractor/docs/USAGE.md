# Phone Extraction Project - Usage Guide

This document provides detailed instructions on how to set up and use the Phone Extraction project.

## Prerequisites

- Python 3.7 or higher.
- Git (for cloning the repository).

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd Regex-Phone-Extraction
    ```

2.  **Create and activate a virtual environment:**
    *   On macOS and Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    *(Replace `venv` with your preferred virtual environment name if desired.)*

3.  **Install required packages:**
    With your virtual environment activated, install dependencies from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Environment Variables for Twilio API (Optional but Recommended):**
    For enhanced phone number validation using the Twilio Lookup API, you need to provide your Twilio credentials.
    *   Create a file named `.env` in the project root directory.
    *   Add your Account SID and Auth Token to this file:
        ```env
        TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        TWILIO_AUTH_TOKEN="your_auth_token_here"
        ```
    *   A `.env.example` file is provided as a template.
    *   **Important**: Ensure `.env` is added to your `.gitignore` file to prevent committing your credentials.

## Core Functionality

The primary functionalities of this project are encapsulated in the modules within the `src/` directory.

### Text Processing (`src.text.normalizer`, `src.text.utils`)

-   **`normalize_text(text, encoding=None)`**: Converts text to a standard UTF-8 encoding.
-   **`clean_text(text)`**: Removes unwanted characters and whitespace.
-   **`normalize_and_clean(text, encoding=None)`**: A combination of the above two.

These functions prepare raw text for reliable phone number extraction.

### Phone Number Extraction and Validation (`src.phone.extractor`, `src.phone.validator`)

-   **`extract_phone_numbers(text, default_region='DE', use_twilio=False)`** (from `src.phone.extractor`):
    *   This is the main function for finding and validating phone numbers in a given text.
    *   It uses the `phonenumbers` library (specifically `PhoneNumberMatcher`) for robust identification of numbers in various international and national formats.
    *   The `default_region` (e.g., "US", "DE", "GB") is a crucial hint for correctly parsing numbers written in a national format (e.g., "089/123456" for Germany if `default_region="DE"`).
    *   It applies custom validation rules defined in `is_valid_phone_number` (e.g., checks for placeholders, repeating digits, sequential digits).
    *   If `use_twilio=True` and Twilio credentials are set up in the `.env` file, it will call `validate_phone_number_twilio` for an additional layer of validation.
    *   Returns a list of dictionaries, each containing details about an extracted valid phone number (original string, E.164 format, region, position, API validation results if applicable, confidence score).

-   **`is_valid_phone_number(number_str, region=None, parsed_number=None)`** (from `src.phone.extractor`):
    *   Performs validation using `phonenumbers` library functions and custom logic (sequential digits, repeating digits, placeholders).
    *   The constants `MIN_REPEATING_DIGITS` (default 5) and `MIN_SEQUENTIAL_DIGITS` (default 8) control the sensitivity of these custom checks.

-   **`validate_phone_number_twilio(phone_number_e164)`** (from `src.phone.validator`):
    *   Contacts the Twilio Lookup v2 API to get validation information for a number (must be in E.164 format).
    *   Returns a dictionary with API status, validity, and other details from Twilio.

### Database Operations (`src.db_utils`)

-   **`get_db_connection()`**: Establishes a connection to the PostgreSQL database using environment variables.
-   **`insert_raw_phone_number(conn, phone_data)`**: Inserts a raw phone number into the database.
-   **`upsert_cleaned_phone_number(conn, phone_data)`**: Inserts or updates a cleaned phone number in the database.
-   **`check_db_tables_exist(conn)`**: Checks if the required database tables exist.

### Analysis (`src.analysis.statistics`)

-   **`generate_statistics(results)`**: Takes the list of extracted phone numbers and computes various statistics (e.g., total found, unique counts, counts by country).
-   **`save_results(data_to_save, output_dir, filename_base, timestamp=None)`**: Saves extracted data and statistics to JSON and TXT files.
-   **`print_statistics(stats)`**: Prints a summary of statistics to the console.

### Logging Configuration (`src.utils.logging_config`)

-   **`get_logger(name)`**: Gets a logger with the default configuration.
-   **`configure_logging(name, log_file, log_level, log_format, log_to_console, log_to_file, extra_handlers)`**: Configures logging with consistent settings.

## Running the Application (Examples)

### Using the Main Script

The `main.py` script provides a complete pipeline for processing phone numbers:

```bash
# Process the latest data directory with default settings
python main.py

# Process the latest data directory with Twilio validation
python main.py --use-twilio

# Process a specific directory and skip normalization
python main.py --dir data/raw/20250509_214446 --skip-normalize

# Only run analysis on a specific results file
python main.py --file data/results/20250509_214446/phone_numbers.json --skip-normalize --skip-extract
```

### Using Individual Command-line Scripts

#### Text Normalization

```bash
# Normalize the latest raw data directory
python scripts/normalize_text.py

# Normalize a specific raw data directory
python scripts/normalize_text.py --input_dir data/raw/20250509_214446

# Specify custom output directory
python scripts/normalize_text.py --output_dir data/my_processed_data
```

#### Phone Number Extraction

```bash
# Extract phone numbers from the latest processed data directory
python scripts/extract_phones.py

# Extract from a specific processed data directory
python scripts/extract_phones.py --input_dir 20250509_214446

# Specify a custom base data path
python scripts/extract_phones.py --data_path /path/to/data/raw
```

#### Database Initialization

```bash
# Initialize the database with default settings
python scripts/init_db.py

# Initialize with custom database name
python scripts/init_db.py --db_name my_phone_db
```

### Using the API in Python Code

```python
# Example usage within a Python script:
from src.text.utils import normalize_and_clean
from src.phone.extractor import extract_phone_numbers
from src.analysis.statistics import generate_statistics, print_statistics, save_results
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv() # To load .env file for Twilio credentials

# 1. Sample Text
sample_text_filepath = "path/to/your/input_text_file.txt" # Or use a string directly
# Ensure this file exists or provide text directly
# For example:
# with open(sample_text_filepath, 'r', encoding='utf-8') as f:
#     raw_text = f.read()
raw_text = "Call us at +49 (176) 12345678 or 089/9876543. US: (212) 555-1212."


# 2. Normalize Text
normalized_text = normalize_and_clean(raw_text)
print(f"Normalized Text: {normalized_text[:200]}...") # Print a snippet

# 3. Extract Phone Numbers
# Provide a default_region if your text is likely to contain national numbers from a specific country
# Enable Twilio validation if .env is set up
extracted_numbers = extract_phone_numbers(
    normalized_text,
    default_region="DE", # Example: Germany
    use_twilio=bool(os.getenv("TWILIO_ACCOUNT_SID"))
)
print(f"\nExtracted Numbers ({len(extracted_numbers)}):")
for num_data in extracted_numbers:
    print(f"  - Original: {num_data['original']}, E.164: {num_data['e164']}, Region: {num_data['region']}")
    if 'validation_api' in num_data and num_data['validation_api'].get('api_status') == 'successful':
        print(f"    Twilio Valid: {num_data['validation_api']['is_valid']}, Type: {num_data['validation_api'].get('type')}")

# 4. Generate Statistics (if numbers were extracted)
if extracted_numbers:
    stats = generate_statistics(extracted_numbers) # Pass the list of dicts directly
    print("\nStatistics:")
    print_statistics(stats)

    # 5. Save Results
    results_output_dir = Path("data/results")
    # Ensure the output directory exists
    results_output_dir.mkdir(parents=True, exist_ok=True) # Create if it doesn't exist

    saved_files = save_results(stats, results_output_dir, "extraction_summary")
    print(f"\nSummary saved to: {saved_files.get('json')}")

    # To save the detailed list of numbers:
    saved_numbers_files = save_results(extracted_numbers, results_output_dir, "phone_numbers_detailed")
    print(f"Detailed numbers saved to: {saved_numbers_files.get('json')} and {saved_numbers_files.get('txt')}")
else:
    print("\nNo phone numbers extracted to generate statistics or save results.")
```

### Using the Database Utilities

```python
from src.db_utils import get_db_connection, check_db_tables_exist, insert_raw_phone_number
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure DB_PASSWORD is set in .env
if not os.getenv("DB_PASSWORD"):
    print("DB_PASSWORD environment variable is not set")
    exit(1)

# Connect to the database
try:
    conn = get_db_connection()
    print("Successfully connected to the database.")
    
    # Check if required tables exist
    if check_db_tables_exist(conn):
        print("All required database tables exist.")
        
        # Example: Insert a phone number
        phone_data = {
            "client_id": "example_client",
            "page_id": "example_page",
            "log_id": None,
            "phone_number": "+491701234567",
            "url": "https://example.com",
            "source_page": "example.com",
            "scrape_run_timestamp": None,
            "notes": "Example phone number",
            "confidence_score": 0.9
        }
        
        raw_phone_id = insert_raw_phone_number(conn, phone_data)
        print(f"Inserted phone number with ID: {raw_phone_id}")
    else:
        print("Some required database tables are missing.")
        print("Run scripts/init_db.py to initialize the database.")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
```

## Configuring and Using Logging

The project uses a centralized logging configuration through the `src.utils.logging_config` module. This ensures consistent logging across all modules.

### Basic Usage

```python
from src.utils.logging_config import get_logger

# Get a logger for your module
log = get_logger(__name__)

# Use the logger
log.debug("This is a debug message")
log.info("This is an info message")
log.warning("This is a warning message")
log.error("This is an error message")
log.critical("This is a critical message")
```

### Advanced Configuration

```python
from src.utils.logging_config import configure_logging
import logging

# Configure a custom logger
logger = configure_logging(
    name="my_custom_logger",
    log_file="logs/custom.log",
    log_level=logging.DEBUG,
    log_format="%(asctime)s - %(levelname)s - %(message)s",
    log_to_console=True,
    log_to_file=True
)

# Use the custom logger
logger.debug("This is a debug message")
logger.info("This is an info message")
```

### Setting Log Level via Environment Variables

You can control the log level by setting the `LOG_LEVEL` environment variable in your `.env` file:

```env
# Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=DEBUG
```

## Testing

The project includes a suite of unit tests located in the `tests/` directory. To run the tests:

1.  Ensure your virtual environment is activated.
2.  Ensure all development dependencies (including `pytest`, `pytest-mock`) are installed via `pip install -r requirements.txt`.
3.  Navigate to the project root directory in your terminal.
4.  Run the `pytest` command:
    ```bash
    pytest
    ```
    Pytest will automatically discover and execute the tests.

### Running Specific Tests

```bash
# Run tests in a specific file
pytest tests/test_phone_extractor.py

# Run a specific test function
pytest tests/test_phone_extractor.py::TestPhoneExtractorRefactored::test_is_valid_phone_number_new

# Run tests with a specific marker
pytest -m "slow"

# Run tests with verbose output
pytest -v
```

### Test Coverage

To check test coverage:

```bash
# Install pytest-cov if not already installed
pip install pytest-cov

# Run tests with coverage report
pytest --cov=src tests/

# Generate HTML coverage report
pytest --cov=src --cov-report=html tests/
```

### Mock Objects in Tests

The tests use `unittest.mock` to mock external dependencies like the Twilio API. For example, in `test_phone_extractor.py`:

```python
@patch('src.phone.extractor.validate_phone_number_twilio', return_value=MOCK_API_RESPONSE)
def test_extract_phone_numbers_new(self, mock_validate_twilio):
    # Test code here
    # mock_validate_twilio will be used instead of the real function
```

## Customizing Phone Number Identification

-   **`phonenumbers` Library**: The primary mechanism for identifying and parsing phone numbers is the `phonenumbers` Python library. Its `PhoneNumberMatcher` is highly effective for various formats. The `default_region` parameter in `extract_phone_numbers` is key to its accuracy with national numbers.
-   **Custom Validation Rules**: The `is_valid_phone_number` function in `src.phone.extractor` contains custom logic to filter out common non-valid numbers (placeholders, excessive repeating/sequential digits). You can adjust the constants `MIN_REPEATING_DIGITS` and `MIN_SEQUENTIAL_DIGITS` in this module to fine-tune this behavior.
-   **`config/patterns.json`**: This file contains custom regex patterns that can be used for special cases where the `phonenumbers` library might not detect certain formats. While the primary extraction logic relies on the `phonenumbers` library, these patterns can be used to supplement the extraction process for edge cases or region-specific formats.

## Troubleshooting

-   **Twilio Errors**: If `use_twilio=True`, ensure your `.env` file is correctly set up with valid `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`. Check Twilio's API logs if issues persist.
-   **No Numbers Extracted**:
    *   Verify the `default_region` supplied to `extract_phone_numbers` is appropriate for your text data if it contains many national-format numbers.
    *   Check the `clean_text` function's behavior if you suspect important characters are being stripped.
    *   Review the custom validation logic in `is_valid_phone_number` if valid numbers seem to be filtered out.
-   **Test Failures**: Examine the `pytest` output for details on which assertions failed. The test files in `tests/` provide examples of expected behavior.
-   **Database Connection Issues**: Ensure your `.env` file contains the correct database credentials and that the PostgreSQL server is running.

## Logs

The application uses Python's standard `logging` module with a centralized configuration in `src.utils.logging_config`. Log files are stored in the `logs/` directory.

To configure logging:

1. Set the `LOG_LEVEL` environment variable in your `.env` file (default is "INFO").
2. Use `get_logger(__name__)` in your modules to get a properly configured logger.
3. For more advanced configuration, use `configure_logging()` with custom parameters.

Example log file output:
```
2025-05-13 15:30:45,123 - INFO - src.phone.extractor - extract_phone_numbers - Found 3 potential numbers in text
2025-05-13 15:30:45,456 - DEBUG - src.phone.extractor - is_valid_phone_number - Validating number: '+49123456789', region: DE
2025-05-13 15:30:45,789 - ERROR - src.db_utils - insert_raw_phone_number - Error inserting raw phone number: connection refused