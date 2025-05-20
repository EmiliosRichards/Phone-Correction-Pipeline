# Project Overview & Recent Updates

**Version:** 1.0 (as of 2025-05-20)

## 1. Project Purpose

The Phone Validation Pipeline is designed to automate the process of finding and validating contact phone numbers for a list of companies. It involves several key stages:
1.  Web scraping company websites to gather text content.
2.  Extracting potential phone number candidates using regular expressions.
3.  Utilizing a Large Language Model (LLM) to analyze the context around these candidates and classify them (e.g., Best Match, Other Relevant, Low Value).
4.  Normalizing and validating extracted phone numbers.
5.  Generating comprehensive reports detailing the findings.

This document provides an overview of the project's current state and summarizes significant recent enhancements.

## 2. Core Components

The pipeline consists of the following main components:

*   **Web Scraper (`src/scraper/scraper_logic.py`):** Responsible for fetching and parsing web content from company URLs.
*   **Regex Extractor (`src/regex_extractor_component.py`):** Extracts potential phone number candidates and surrounding text snippets using regular expressions.
*   **LLM Extractor (`src/llm_extractor_component.py`):** Interacts with a Large Language Model (currently Google Gemini) to analyze snippets and classify phone numbers.
*   **Data Handler (`src/data_handler.py`):** Manages input data loading, preprocessing, and output report generation.
*   **Configuration (`src/core/config.py`):** Centralizes all pipeline configurations, loaded from an `.env` file.
*   **Main Pipeline Orchestrator (`main_pipeline.py`):** Coordinates the execution flow of all components.

## 3. Summary of Recent Major Enhancements

The following key features and improvements have been recently integrated into the pipeline:

### 3.1. Advanced Scraper Link Prioritization & Control
(Based on `docs/scraper_enhancement_plan.md`)

To make web scraping more efficient and targeted, an advanced link prioritization system has been implemented:

*   **Multi-Tier Link Scoring:** Internal links discovered by the scraper are now assigned a numerical score based on a sophisticated, multi-tier evaluation:
    *   **Tier 1 (Critical Priority):** Highest scores for links whose paths contain standalone "critical" keywords (e.g., `/kontakt`, `/impressum`).
    *   **Tier 2 (High Priority):** Very high scores for links with standalone "high priority" keywords (e.g., `/legal`, `/privacy`).
    *   **Tier 3 (Priority Keyword Early/Short Path):** High scores for priority keywords found early in shorter URL paths.
    *   **Tier 4 (Target Keyword in Segment):** Medium scores if a general target keyword is part of a URL path segment.
    *   **Tier 5 (Target Keyword in Link Text):** Lower scores if a general target keyword is only found in the link's anchor text.
*   **New Configuration Options (in `.env` and `src/core/config.py`):**
    *   `TARGET_LINK_KEYWORDS`: General keywords for initial link discovery.
    *   `SCRAPER_CRITICAL_PRIORITY_KEYWORDS`: Defines keywords for Tier 1 scoring.
    *   `SCRAPER_HIGH_PRIORITY_KEYWORDS`: Defines keywords for Tier 2 scoring.
    *   `SCRAPER_MAX_KEYWORD_PATH_SEGMENTS`: Influences scoring for Tier 1-3 based on path length.
    *   `SCRAPER_EXCLUDE_LINK_PATH_PATTERNS`: For hard-excluding specific URL paths (e.g., `/media/`, `/video/`).
    *   `SCRAPER_MAX_PAGES_PER_DOMAIN`: Limits the number of pages scraped per domain.
    *   `SCRAPER_MIN_SCORE_TO_QUEUE`: Links scoring below this are not added to the scrape queue.
    *   `SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS`: High-scoring links can bypass the `SCRAPER_MAX_PAGES_PER_DOMAIN` limit.
*   **Benefits:** This system allows the scraper to focus on the most promising pages for contact/legal information while avoiding excessive crawling of less relevant sections (like blogs or extensive help video libraries).

### 3.2. LLM Output Handling Modification
(Based on `docs/llm_output_modification_plan.md`)

The interaction with the LLM (Google Gemini) has been adjusted for more flexible output handling:

*   **LLM API Returns Plain Text:** The Gemini API is now configured to return its response as plain text, rather than enforcing a strict JSON schema at the API level.
*   **Prompt-Guided JSON Formatting:** The prompt sent to the LLM still instructs it to format its output as a JSON string.
*   **Application-Side Parsing & Validation:**
    *   The application (`src/llm_extractor_component.py`) receives the LLM's raw text output.
    *   It attempts to parse this text as JSON.
    *   Potential pre-processing steps can be added to clean the text before parsing (e.g., stripping markdown code fences).
    *   If parsing is successful, the resulting JSON object is validated against the project's Pydantic schemas (`LLMExtractionResult`).
*   **Benefits:** This approach provides more robustness if the LLM occasionally struggles with perfect JSON schema adherence but can still produce a parsable JSON-like string. Error handling for parsing and validation remains critical.

### 3.3. Enhanced Logging & Dedicated Data Dumps
(Based on `docs/enhanced_logging_plan.md`)

To improve traceability, debugging, and review of pipeline runs, logging and data persistence have been significantly enhanced:

*   **Run-Specific Log File:** A detailed, human-readable log file (`pipeline_run_{run_id}.log`) is generated for each pipeline execution, stored in the run-specific output directory.
*   **Configurable Log Levels:**
    *   `LOG_LEVEL` (for file log, default `INFO`): Controls verbosity of the main log file.
    *   `CONSOLE_LOG_LEVEL` (for console, default `WARNING`): Keeps CLI output concise.
*   **Dedicated File Dumps for Key Intermediate Data:**
    *   **Cleaned Scraped Text:** Plain text content from each scraped page is saved to `run_output_dir/scraped_content/cleaned_pages_text/`.
    *   **Regex-Extracted Snippets:** Aggregated snippets for each company are saved to `run_output_dir/intermediate_data/..._regex_snippets.json`.
    *   **LLM Input Data:** The structured candidate items (JSON) fed into the LLM prompt template are saved to `run_output_dir/llm_context/CANONICAL_{...}_llm_input_data.json`.
    *   **Full LLM Prompt Text:** The complete, final text prompt sent to the LLM is saved to `run_output_dir/llm_context/CANONICAL_{...}_llm_full_prompt.txt`.
    *   **Raw LLM JSON Output:** The raw JSON response from the LLM is saved to `run_output_dir/llm_context/CANONICAL_{...}_llm_raw_output.json`.
    *   (Raw scraped HTML was likely already being saved and will continue to be).
*   **Narrative Logging:** The main log file provides a high-level narrative of the pipeline's execution for each company, including references (file paths) to these dedicated data dump files.
*   **Benefits:** This provides a clear audit trail for each run, making it easier to diagnose issues, review specific data points, and understand the pipeline's behavior.

### 3.4. Configurable Scraper Filename Lengths
(Based on `docs/scraper_filename_config_plan.md`)

To prevent `IOError` exceptions caused by overly long file paths (especially on Windows), the length of the company name component in generated filenames is now configurable:

*   **New Configuration:** `FILENAME_COMPANY_NAME_MAX_LEN` (integer, default 25) added to `AppConfig` and configurable via `.env`.
*   **Usage:** The `get_safe_filename` function in `src/scraper/scraper_logic.py` uses this setting when creating filenames for scraped content, truncating the company name part if necessary.
*   **Benefits:** Improves the robustness of file saving operations across different operating systems and environments with varying path length limitations.

### 3.5. URL Consolidation & Dual Excel Reports
(Based on `docs/url_consolidation_and_dual_report_plan.md`)

A major architectural enhancement to handle URL redirects and improve reporting clarity:

*   **Data Consolidation by Canonical URL:** The pipeline now identifies a `final_canonical_entry_url` for each processed input company. Scraping and LLM processing for a given website (identified by its canonical URL) are performed only once, even if multiple input URLs redirect to it.
*   **Global Caching:** `main_pipeline.py` uses global caches to store LLM results and scraper statuses keyed by the canonical URL, avoiding redundant processing. An `input_to_canonical_map` tracks the relationship between original input URLs and their resolved canonical URLs.
*   **Two-Pass Processing in `main_pipeline.py`:**
    1.  **First Pass:** Iterates through input URLs, performs scraping, determines canonical URLs, and populates the caches with processing results (scraper status, LLM outputs) for each unique canonical site.
    2.  **Second Pass:** Builds the output reports using the cached data and the input-to-canonical mapping.
*   **Dual Excel Reports:**
    1.  **Detailed Flattened Report (`phone_validation_detailed_output_{run_id}.xlsx`):**
        *   One row per unique LLM-extracted phone number.
        *   Grouped by `Canonical_URL`.
        *   Includes original `GivenURL` for context.
        *   Excludes data from sites where scraping failed.
    2.  **Summary Report (`phone_validation_output_{run_id}.xlsx` - the main output):**
        *   One row per original input `GivenURL`.
        *   Shows top phone numbers (Primary, Secondary).
        *   Includes `CanonicalEntryURL` and `ScrapingStatus`.
        *   `Overall_VerificationStatus` indicates if redirection occurred and reflects the status of the canonical site processing.
*   **Benefits:** Ensures data integrity by processing each unique website only once, provides clearer and more useful reports, and accurately reflects the outcome for each original input URL, including handling of redirects.

## 4. Next Steps for Documentation

*   Update `README.md` with a revised project description and links to this summary.
*   Significantly expand `USAGE.md` to detail:
    *   Pipeline workflow (front-to-back).
    *   Detailed explanation of all `.env` configurations, including the new scraper and logging settings, with guidance on choosing values.
    *   Examples of input data and expected output formats for both reports.
*   Review and potentially consolidate or archive older specific plan documents in `docs/` if their content is fully superseded by this summary and the updated `README.md`/`USAGE.md`.

This document serves as a starting point for comprehensive project documentation.