# Plan: Enhanced Run Metrics for Phone Correction Pipeline

This plan details the implementation of enhanced run metrics, including LLM token statistics and more granular scraping statistics, as a follow-up to the initial GitHub Issue #2 implementation.

## A. LLM Token Statistics

**Objective:** Track and report LLM token usage.

**Phase 1: Modify `GeminiLLMExtractor` in `src/llm_extractor_component.py`**
1.  **Access Usage Metadata:**
    *   Inside the `extract_phone_numbers` method, after the call to `_generate_content_with_retry`, check if `response.usage_metadata` exists.
2.  **Extract Token Counts:**
    *   If `usage_metadata` is present, extract:
        *   `prompt_token_count`
        *   `candidates_token_count` (completion tokens)
        *   `total_token_count`
3.  **Update Return Value of `extract_phone_numbers`:**
    *   Change return signature from `Tuple[List[PhoneNumberLLMOutput], Optional[str]]` to `Tuple[List[PhoneNumberLLMOutput], Optional[str], Optional[Dict[str, int]]]`.
    *   The new third element will be a dictionary like `{"prompt_tokens": X, "completion_tokens": Y, "total_tokens": Z}`.

**Phase 2: Modify `main_pipeline.py`**
1.  **Adapt to New Return Value:**
    *   Update calls to `llm_extractor.extract_phone_numbers(...)` to receive the token counts dictionary.
2.  **Initialize and Aggregate Token Counts in `run_metrics`:**
    *   Add keys to `run_metrics`: `total_llm_prompt_tokens`, `total_llm_completion_tokens`, `total_llm_tokens_overall`, `llm_successful_calls`.
    *   Increment `llm_successful_calls` on successful LLM calls with token data.
    *   Accumulate token counts from each call into these totals.
3.  **Update `write_run_metrics` Function:**
    *   Include aggregated LLM token counts in `run_metrics_{run_id}.md`.
    *   Calculate and display:
        *   Average prompt tokens per request (`total_llm_prompt_tokens / llm_successful_calls`)
        *   Average completion tokens per request (`total_llm_completion_tokens / llm_successful_calls`)
        *   Average total tokens per request (`total_llm_tokens_overall / llm_successful_calls`)
    *   Handle division by zero if `llm_successful_calls` is 0.

**Mermaid Diagram for LLM Token Stats:**
```mermaid
graph TD
    A[main_pipeline.py: main function initializes run_metrics] --> B{Loop through data for LLM processing};
    B -- For each item --> C(Call llm_extractor.extract_phone_numbers);
    C --> D[llm_extractor_component.py: extract_phone_numbers];
    D -- Calls --> E(_generate_content_with_retry);
    E -- Calls Gemini API --> F((Gemini API));
    F -- Returns API Response (with usage_metadata) --> E;
    E -- Returns API Response --> D;
    D -- Extracts token counts from usage_metadata --> D;
    D -- Returns extracted_data, raw_response, token_counts_for_call --> C;
    C -- Accumulates token_counts_for_call into run_metrics --> B;
    B -- After loop --> G(Call write_run_metrics with final run_metrics);
    G -- Writes to file --> H([run_metrics_{run_id}.md with token counts]);
```

## B. Enhanced Scraping Statistics

**Objective:** Track and report more detailed scraping metrics, including page counts per type.

**1. Modify `AppConfig` (`src/core/config.py`):**
    *   Add new configuration lists for page type classification keywords:
        *   `PAGE_TYPE_KEYWORDS_CONTACT: ["contact", "kontakt", "ansprechpartner"]`
        *   `PAGE_TYPE_KEYWORDS_IMPRINT: ["imprint", "impressum", "legal-notice", "legalnotice"]`
        *   `PAGE_TYPE_KEYWORDS_LEGAL: ["privacy", "datenschutz", "terms", "agb", "legal"]`
        *   (Define others as needed, e.g., for "general_content" or rely on a fallback).

**2. Modify `scrape_website` in `src/scraper/scraper_logic.py`:**
    *   **Page Type Classification:**
        *   After successfully fetching `html_content` for a `final_landed_url_normalized`:
            *   Implement logic to classify the page type based on keywords from `AppConfig` found in the `final_landed_url_normalized`.
            *   Assign a type (e.g., "contact", "imprint", "legal", "general_content", "unknown").
    *   **Return Enhanced Scraped Page Details:**
        *   Modify `scraped_page_details` (currently `List[Tuple[str, str]]`) to store tuples of `(cleaned_page_filepath, final_landed_url_normalized, page_type_str)`.
        *   The function's return signature for the first element will change to `List[Tuple[str, str, str]]`.

**3. Modify `main_pipeline.py`:**
    *   **Adapt to New Return Value from `scrape_website`**.
    *   **Initialize and Aggregate Scraping Stats in `run_metrics`:**
        *   `total_pages_scraped_overall`: Sum of successfully scraped pages across all canonical sites.
        *   `pages_scraped_by_type`: Dictionary `{"contact": X, "imprint": Y, "legal": Z, "general_content": A, "unknown": B}`.
        *   `total_successful_canonical_scrapes`: Count of canonical sites for which at least one page was successfully scraped.
        *   `total_urls_fetched_by_scraper`: Count of unique `final_landed_url_normalized` for which content was successfully fetched.
    *   **Update `write_run_metrics` Function:**
        *   Display `total_pages_scraped_overall`.
        *   Display `pages_scraped_by_type` (e.g., as a list or table).
        *   Display `total_urls_fetched_by_scraper`.
        *   Calculate and display "Average pages scraped per successfully scraped canonical site" (`total_pages_scraped_overall / total_successful_canonical_scrapes`, handle division by zero).

**Mermaid Diagram for Scraping Stats:**
```mermaid
graph TD
    AA[main_pipeline.py: main function initializes run_metrics] --> BB{Loop through input data for scraping};
    BB -- For each input URL/company --> CC(Call scraper_logic.scrape_website);
    CC --> DD[scraper_logic.py: scrape_website];
    DD -- Fetches page --> EE{Page Content};
    EE -- Classify page type based on URL & config --> DD;
    DD -- Returns list_of_scraped_pages_with_types, status, canonical_url --> CC;
    CC -- For each scraped page in list --> FF{Update run_metrics};
    FF -- Increment total_pages_scraped_overall --> FF;
    FF -- Increment pages_scraped_by_type[type] --> FF;
    FF -- Add to set of unique fetched URLs --> FF;
    CC -- After processing a canonical site --> GG{Update total_successful_canonical_scrapes};
    BB -- After loop --> HH(Call write_run_metrics with final run_metrics);
    HH -- Writes to file --> II([run_metrics_{run_id}.md with enhanced scraping stats]);