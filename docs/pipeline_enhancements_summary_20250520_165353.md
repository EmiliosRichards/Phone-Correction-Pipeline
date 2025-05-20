# Pipeline Enhancements Summary (as of 2025-05-20 16:53)

This document summarizes the significant enhancements, refactoring, and robustness improvements made to the phone extraction pipeline.

## Overall Goal
To improve the accuracy, reliability, configurability, and maintainability of the phone number extraction and reporting process.

## Key Changes & Features Implemented:

### 1. LLM Processing & Prompt Engineering
*   **Prompt Content & Structure:**
    *   Updated input example in `prompts/gemini_phone_validation_v1.txt` to use `"number"` key and include `"original_input_company_name"`.
    *   Instructed LLM to process and return an entry for *every* candidate number provided.
    *   Added guidance for LLM to critically use snippet context to verify if pre-formatted numbers are genuine phone numbers or artifacts (e.g., dates, IDs).
    *   Refined country-specific instructions to guide the LLM on prioritizing DE, CH, AT for 'Primary'/'Secondary' classifications, rather than exclusive extraction.
    *   Introduced a new LLM type: `'Non-Priority-Country Contact'` for numbers from other countries.
*   **API Call Robustness:**
    *   Implemented retry logic for Gemini API calls within `GeminiLLMExtractor` using the `tenacity` library. This includes exponential backoff for retriable exceptions like rate limits or temporary server errors.
    *   Added `tenacity` to `requirements.txt`.

### 2. Reporting & Data Handling Logic
*   **`Top_Contacts_Report` (Tertiary Report) Enhancements:**
    *   **Filtering:**
        *   Numbers classified as `'Non-Business'` by the LLM (after consolidation) are now excluded.
        *   Numbers with source types `'Unknown'`, `'Fax'`, `'Mobile'`, `'Date'`, or `'ID'` are excluded.
        *   Numbers with type `'Non-Priority-Country Contact'` are now potentially includable if they are not 'Non-Business' and not excluded by other type rules.
    *   **Major Refactor & Consolidation:**
        *   Implemented global consolidation of all phone numbers by their *true base domain* before any report generation.
        *   The report now features one row per true base domain, providing a unified view for each core website.
        *   Company names in the report are aggregated from all input rows that map to the same true base domain (e.g., `[TrueBaseDomain] - CompanyA - CompanyB`).
        *   `GivenURL`s are also aggregated from all relevant input rows.
        *   Ensured accurate company attribution *per specific phone number* by tracking `original_input_company_name` through the pipeline to the `ConsolidatedPhoneNumberSource` and displaying this in the phone number string (e.g., `+49... (Type) [OriginalCompanyForThisNumber]`).
        *   Rows are excluded from this report if no eligible phone numbers are found for a canonical URL after all filtering.
*   **Data Flow & Schemas:**
    *   Propagated `original_input_company_name` from initial regex extraction through to `PhoneNumberLLMOutput` and `ConsolidatedPhoneNumberSource` schemas.
    *   Updated `Detailed Flattened Report` and `Summary Report` to utilize the globally consolidated data for lookups and consistency.
*   **Phone Number Sorting:**
    *   Enhanced the sorting logic in `src/data_handler.py` to use a secondary sort key based on phone `type` (e.g., 'Main Line' preferred over 'Info-Hotline') when primary LLM classifications are identical.

### 3. Scraper Configuration & Operation
*   **Scraping Volume Control:**
    *   Added a new environment variable `SCRAPER_MAX_HIGH_PRIORITY_PAGES_AFTER_LIMIT` (configurable in `.env`) to allow scraping a few additional high-priority pages (like 'contact', 'impressum') even after the general `SCRAPER_MAX_PAGES_PER_DOMAIN` limit is met.
    *   Updated `src/core/config.py` and `src/scraper/scraper_logic.py` to implement this.
*   **Duplicate URL Handling:**
    *   Analysis confirmed the system's design handles duplicate `GivenURL`s and different `GivenURL`s resolving to the same true base domain gracefully through caching of scraped/LLM-processed pathful canonical URLs and global consolidation by true base domain.

### 4. Operational Robustness & Maintainability
*   **Logging:**
    *   Implemented log rotation in `src/core/logging_config.py` using `RotatingFileHandler`. This prevents log files from growing indefinitely during long runs, splitting them into manageable chunks (e.g., 10MB files, keeping 5 backups).
*   **Configuration:**
    *   Updated `.env.example` to include the new `SCRAPER_MAX_HIGH_PRIORITY_PAGES_AFTER_LIMIT` variable.

### 5. Documentation
*   Ongoing updates to `README.md` and `USAGE.md` for clarity and to reflect new features.
*   Archiving of older, superseded planning and summary documents into `docs/archive/`.
*   This summary document itself.

## Impact
These changes collectively aim for:
*   **Improved Accuracy:** More precise LLM instructions and refined data handling lead to better quality phone number extraction and classification.
*   **Enhanced Robustness:** Retry mechanisms for API calls and log rotation make the pipeline more resilient for large-scale and overnight runs.
*   **Greater Configurability:** New settings provide more control over the scraping process.
*   **Clearer Reporting:** The `Top_Contacts_Report` is now significantly more insightful and less redundant.
*   **Better Maintainability:** Clearer code paths for data consolidation and improved documentation.