# Phone Number Extraction Project

A Python project for extracting, validating, and analyzing phone numbers from scraped web content.

## Key Features

*   **Text Normalization**: Cleans and normalizes raw text scraped from websites.
*   **Robust Phone Number Extraction**: Utilizes the `phonenumbers` library for parsing and initial validation of numbers from various international formats.
*   **Custom Validation Rules**: Implements additional checks for placeholder numbers, repeating digits, and sequential digits.
*   **Optional Twilio API Validation**: Can leverage Twilio's Lookup API for enhanced validation of phone numbers (requires API credentials).
*   **Structured Data Output**: Saves detailed extraction results and summary statistics.
*   **Comprehensive Test Suite**: Includes unit tests run with `pytest`.

## Project Structure

```
Regex-Phone-Extraction/
├── .env.example              # Example environment variables file
├── .gitignore
├── LICENSE
├── main.py                   # Main entry point
├── pytest.ini                # Pytest configuration
├── README.md
├── requirements.txt
├── setup.py                  # Project setup script (if used for packaging)
├── config/                   # Configuration files
│   ├── default.json          # Default configuration (currently not used)
│   └── patterns.json         # Phone number patterns (used for special cases)
├── data/                     # Data directories
│   ├── raw/                  # Raw scraped data
│   │   └── [timestamp]/
│   │       └── pages/
│   │           └── [domain]/
│   │               └── text.txt
│   ├── processed/            # Processed data (normalized text files)
│   │   └── [timestamp]/
│   │       └── pages/
│   │           └── [domain]/
│   │               └── text.txt
│   └── results/              # Extraction results
│       └── [timestamp]/
│           ├── phone_numbers.json
│           ├── phone_numbers.txt
│           └── statistics.json
├── docs/                     # Documentation
│   ├── API.md
│   └── USAGE.md
├── logs/                     # Log files
├── scripts/                  # Command-line scripts
│   ├── normalize_text.py
│   ├── extract_phones.py
│   └── analyze_results.py
├── src/                      # Source code
│   ├── __init__.py
│   ├── db_utils.py           # Database utilities
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── statistics.py
│   ├── phone/
│   │   ├── __init__.py
│   │   ├── extractor.py      # Phone number extraction and core validation logic
│   │   ├── formatter.py      # Phone number formatting (if needed)
│   │   └── validator.py      # Twilio API validation logic
│   ├── text/
│   │   ├── __init__.py
│   │   ├── normalizer.py     # Text normalization
│   │   └── utils.py          # Text utility functions
│   └── utils/
│       ├── __init__.py
│       └── logging_config.py # Centralized logging configuration
└── tests/                    # Unit tests
    ├── __init__.py
    ├── conftest.py           # Pytest fixtures and configuration
    ├── test_analysis.py
    ├── test_phone_extractor.py
    ├── test_phone_validator.py
    └── test_text_normalizer.py
```

## Installation

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

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables for Twilio (Optional but Recommended for full validation):**
    *   Create a file named `.env` in the project root directory (e.g., alongside `README.md`).
    *   Add your Twilio Account SID and Auth Token to the `.env` file:
        ```
        TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        TWILIO_AUTH_TOKEN="your_auth_token_here"
        ```
    *   Ensure `.env` is listed in your `.gitignore` file to prevent committing credentials. A `.env.example` file is provided.

## Usage

### Running the Full Pipeline (Example via `main.py`)

The `main.py` script serves as an example entry point. You may need to adapt it or use the individual components as per your requirements.

```bash
python main.py [options]
```

#### Command-line Arguments for `main.py`

The following command-line arguments are available:

* `--dir`: Directory containing scraped data (default: latest)
* `--file`: JSON file containing extraction results (for analysis only)
* `--skip-normalize`: Skip the normalization step
* `--skip-extract`: Skip the extraction step
* `--skip-analyze`: Skip the analysis step
* `--use-twilio`: Enable Twilio API for phone number validation (requires .env setup)

Example:
```bash
# Process the latest data directory with Twilio validation
python main.py --use-twilio

# Process a specific directory and skip normalization
python main.py --dir data/raw/20250509_214446 --skip-normalize

# Only run analysis on a specific results file
python main.py --file data/results/20250509_214446/phone_numbers.json --skip-normalize --skip-extract
```

Refer to `main.py` and the scripts in the `scripts/` directory for more detailed examples. The primary logic for extraction and validation resides in `src/phone/extractor.py` and `src/phone/validator.py`.

### Running Individual Steps (Conceptual)

While `main.py` provides a high-level flow, the core functionalities are modular:

*   **Text Normalization**: See `src/text/normalizer.py`.
*   **Phone Number Extraction & Validation**: See `src/phone/extractor.py` (includes `phonenumbers` library usage and custom checks) and `src/phone/validator.py` (for Twilio API calls).
*   **Results Analysis**: See `src/analysis/statistics.py`.

## Testing

The project uses `pytest` for running unit tests.

1.  Ensure all development dependencies are installed (including `pytest` and `pytest-mock`, which are in `requirements.txt`).
2.  From the project root directory, run:
    ```bash
    pytest
    ```
    This will discover and run all tests in the `tests/` directory.

## Data Flow

1.  **Input**: Text data from `data/raw/[timestamp]/pages/[domain]/text.txt`.
2.  **Text Normalization** (`src.text.normalizer`):
    *   Cleans and prepares text for extraction.
    *   Normalized files are saved to `data/processed/[timestamp]/pages/[domain]/text.txt`.
3.  **Phone Extraction & Validation** (`src.phone.extractor`, `src.phone.validator`):
    *   Reads normalized text files from the processed directory.
    *   Uses `phonenumbers.PhoneNumberMatcher` to find potential phone number matches in the text.
    *   Applies initial validation using `phonenumbers` library capabilities (e.g., `is_possible_number`, `is_valid_number`).
    *   Performs custom validation checks (placeholder, repeating digits, sequential digits).
    *   Optionally, uses the Twilio Lookup API via `src.phone.validator` for further validation if credentials are provided.
    *   Assigns a confidence score to each extracted number.
4.  **Analysis** (`src.analysis.statistics`):
    *   Generates statistics and insights from the extracted and validated phone numbers.
5.  **Output**: Results are saved to the `data/results/[timestamp]/` directory.

## Configuration

### Environment Variables

The project uses the following environment variables (defined in `.env`):

*   **Twilio Credentials**:
    *   `TWILIO_ACCOUNT_SID`: Your Twilio Account SID for phone validation.
    *   `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token for phone validation.

*   **Database Configuration**:
    *   `DB_HOST`: Database host (default: "localhost").
    *   `DB_PORT`: Database port (default: "5432").
    *   `DB_NAME`: Database name (default: "phone_extraction").
    *   `DB_USER`: Database user (default: "postgres").
    *   `DB_PASSWORD`: Database password (required for database operations).

*   **Logging Configuration**:
    *   `LOG_LEVEL`: Logging level (default: "INFO"). Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL.

*   **Data Directories**:
    *   `PROCESSED_DIR`: Directory for processed data (default: "data/processed").

### Phone Number Patterns

The `config/patterns.json` file contains custom regex patterns that can be used for special cases where the `phonenumbers` library might not detect certain formats. While the primary extraction logic relies on the `phonenumbers` library, these patterns can be used to supplement the extraction process for edge cases or region-specific formats.

## Results

Extraction results are typically saved in the `data/results/` directory, often including:

*   `phone_numbers.json`: Detailed extraction results.
*   `phone_numbers.txt`: Simple text list of extracted phone numbers.
*   `statistics.json`: Summary statistics.

## License

[MIT License](LICENSE)