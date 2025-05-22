# Project Enhancements Summary (as of 2025-05-21)

This document summarizes the recent enhancements made to the Phone Correction Pipeline, primarily addressing GitHub Issue #2 and subsequent improvements to run metrics.

## 1. Core Enhancements (GitHub Issue #2)

### 1.1. Run Metrics File (`run_metrics_{run_id}.md`)
*   **Purpose:** To provide a human-readable summary of each pipeline run's performance and key statistics.
*   **Content:**
    *   Run ID and total run duration.
    *   Start and end timestamps of the pipeline.
    *   Duration breakdown for major pipeline tasks (e.g., data loading, scraping, regex extraction, LLM processing, report generation).
    *   Success vs. failure statistics for various stages.
    *   Initially noted LLM token counts as "not currently tracked" (this was enhanced later, see section 2.1).
    *   List of significant errors encountered during the run.
*   **Location:** Generated in the `run_output_dir` (e.g., `output_data/{run_id}/`).
*   **Primary Files Modified:** [`main_pipeline.py`](main_pipeline.py:1) for logic and metrics collection.

### 1.2. Dedicated Failure Log (`failed_rows_{run_id}.csv`)
*   **Purpose:** To simplify debugging and potential reruns by providing a clear list of rows that failed during processing.
*   **Content:**
    *   `input_row_identifier`: Identifier for the input row (e.g., DataFrame index).
    *   `stage_of_failure`: The pipeline stage where the failure occurred (e.g., "URL_Validation", "Scraping", "LLM_Processing_Error").
    *   `error_reason`: A sanitized, concise explanation of the failure.
*   **Location:** Generated in the `run_output_dir`.
*   **Primary Files Modified:** [`main_pipeline.py`](main_pipeline.py:1) (added `log_row_failure` helper and integrated logging at failure points).

### 1.3. File System Optimizations
*   **Scraped Content Organization:**
    *   Cleaned text from scraped pages is now organized into source-specific subdirectories.
    *   New Structure: `scraped_content/cleaned_pages_text/{source}/{filename}` (where `{source}` is derived from the URL's domain).
    *   Primary Files Modified: [`src/scraper/scraper_logic.py`](src/scraper/scraper_logic.py:1).
*   **Duplicate File Removal:**
    *   Removed the generation of redundant `regex_snippets.json` files.
    *   Retained `CANONICAL_{...}_llm_input_data.json` in the `llm_context_dir` as it's more semantically aligned.
    *   Primary Files Modified: [`main_pipeline.py`](main_pipeline.py:1).
*   **LLM Prompt Template Consolidation:**
    *   Replaced the saving of individual `llm_full_prompt_{timestamp}.txt` files for each LLM API call.
    *   Now saves a single `llm_prompt_template.txt` (containing the base prompt template used for the run) once per run in the `run_output_dir`.
    *   Primary Files Modified: [`src/llm_extractor_component.py`](src/llm_extractor_component.py:1).

## 2. Subsequent Metrics Enhancements

### 2.1. LLM Token Statistics
*   **Purpose:** To track and report LLM token usage for better cost and performance analysis.
*   **Implementation:**
    *   The `GeminiLLMExtractor` now extracts `prompt_token_count`, `candidates_token_count` (completion tokens), and `total_token_count` from the Gemini API response's `usage_metadata`.
    *   The `extract_phone_numbers` method in [`src/llm_extractor_component.py`](src/llm_extractor_component.py:1) now returns these token statistics.
    *   [`main_pipeline.py`](main_pipeline.py:1) aggregates these token counts (total prompt, total completion, total overall) and counts successful LLM calls with token data.
*   **Reporting:**
    *   The `run_metrics_{run_id}.md` file now includes:
        *   Total LLM prompt tokens.
        *   Total LLM completion tokens.
        *   Total LLM tokens overall.
        *   Number of successful LLM calls that returned token data.
        *   Average prompt, completion, and total tokens per successful call.

### 2.2. Enhanced Scraping Statistics
*   **Purpose:** To provide more granular insights into the scraping process.
*   **Implementation:**
    *   **Page Type Classification:**
        *   Scraped pages are now classified into types like "contact", "imprint", "legal", "homepage", "general_content", or "unknown".
        *   Classification is based on keywords (configurable in [`src/core/config.py`](src/core/config.py:1)) found in the page URL.
        *   Logic added to `_classify_page_type` and integrated into `scrape_website` in [`src/scraper/scraper_logic.py`](src/scraper/scraper_logic.py:1).
        *   The `scrape_website` function now returns a list of tuples, each including the `(cleaned_page_filepath, final_landed_url_normalized, page_type_str)`.
    *   **Metrics Aggregation:**
        *   [`main_pipeline.py`](main_pipeline.py:1) was updated to collect and aggregate these new scraping details.
*   **Reporting (in `run_metrics_{run_id}.md`):**
    *   Total pages scraped overall.
    *   Total unique URLs successfully fetched by the scraper.
    *   Total number of successfully scraped canonical sites (sites for which at least one page was fetched).
    *   Average number of pages scraped per successfully scraped canonical site.
    *   A breakdown of pages scraped by their classified type (e.g., Contact: X, Imprint: Y).

These enhancements collectively improve the pipeline's monitoring, debuggability, file management, and provide deeper insights into its operational performance and resource consumption.