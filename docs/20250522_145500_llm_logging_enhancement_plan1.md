# Plan: Enhanced Logging and Debuggability for LLM Statuses

**Date:** 2025-05-22

**Goal:** To provide more granular information in the logs when `LLM_Not_Run_Or_NoOutput_For_Canonical` or `LLM_OutputEmpty_Or_NoRelevant_For_Canonical` statuses occur in `main_pipeline.py`. This will make it easier to pinpoint whether the issue lies with an upstream process (like scraping), LLM input, LLM configuration, the LLM call itself, or post-LLM data processing.

**Overall Strategy:**
Trace the lifecycle of data for a canonical URL, from scraping through LLM processing to final consolidation, and log critical decision points or failures more explicitly. The aim is to easily determine if a problem was due to:
*   Upstream Data Issues (no data from scraping, no regex candidates).
*   Configuration/Setup Errors (missing LLM prompt).
*   LLM Call Failures (API errors, LLM refusing to respond, LLM response malformed).
*   LLM Content Issues (LLM returns empty list, data structure mismatch, validation failures).
*   Post-LLM Processing Issues (data handler filters out all numbers).

---

## Phase 1: Enhancements in `src/llm_extractor_component.py` (GeminiLLMExtractor)

This component directly interacts with the LLM.

1.  **Add `file_identifier_prefix` to More Log Messages**:
    *   **Why**: To easily correlate log entries with the specific canonical URL being processed.
    *   **How**: Prepend or append `file_identifier_prefix` to key error or warning messages.
    *   **Examples**:
        *   `logger.error(f"[{file_identifier_prefix}] Initial LLM call: Mismatch...")`
        *   `logger.error(f"[{file_identifier_prefix}] Initial LLM call: Failed to parse JSON...")`
        *   Apply similarly to Pydantic errors, no JSON block, empty response, and their retry counterparts.

2.  **Log Details of `_create_error_llm_item` Creation**:
    *   **Why**: To clearly see when and why an "error item" is substituted for actual LLM output.
    *   **How**: Enhance the existing log message to include `file_identifier_prefix` and more source details.
        *   Example: `logger.warning(f"[{file_identifier_prefix}] Creating error item for input number '{input_item_details.get('number')}' from source '{input_item_details.get('source_url')}' due to: {error_type_str}")`

3.  **Clarify Logging for Final Raw Response**:
    *   **Why**: To know if the returned `final_raw_llm_response_str` was from the initial call or a retry.
    *   **How**: Add a log message before returning this string, indicating its origin (initial call, last retry, or default/error JSON).

4.  **Log Count of Successfully Processed vs. Error Items**:
    *   **Why**: To get a summary of LLM extraction success for each call.
    *   **How**: At the end of `extract_phone_numbers`, calculate and log the count of successful items versus error items out of the total candidates.
        *   Example: `logger.info(f"[{file_identifier_prefix}] LLM extraction summary: {successful_items_count} successful items, {error_items_count} error items out of {len(candidate_items)} candidates.")`

---

## Phase 2: Enhancements in `main_pipeline.py`

This file orchestrates the process and sets the final statuses.

1.  **Refine Logging When `LLM_Not_Run_Or_NoOutput_For_Canonical` is Set**:
    *   **Why**: To provide a more specific upstream reason for this generic status.
    *   **How**: When this status is set, attempt to find more specific causes by checking `canonical_site_pathful_scraper_status` for pathful URLs that map to the true base canonical URL.
    *   **Action**: Log these contributing pathful statuses. For example: `logger.warning(f"Row {index} ({company_name_pass2}): Status LLM_Not_Run_Or_NoOutput_For_Canonical for true_base '{canonical_url_summary}'. Contributing pathful statuses: {'; '.join(specific_reasons)}")`

2.  **Log Reason for `LLM_OutputEmpty_Or_NoRelevant_For_Canonical`**:
    *   **Why**: To distinguish if emptiness was due to the LLM returning no raw candidates or if the data handler filtered everything.
    *   **How**:
        *   Before calling `process_and_consolidate_contact_data` for a true base domain, determine if all its constituent pathful URLs had empty raw LLM outputs from `canonical_site_raw_llm_outputs`. Store this boolean (e.g., in `true_base_raw_llm_was_empty[true_base_domain]`).
        *   When the status `LLM_OutputEmpty_Or_NoRelevant_For_Canonical` is set, use this stored boolean to log the appropriate reason (e.g., "LLM returned no raw candidates..." vs. "LLM returned raw candidates, but all were filtered out...").

---

## Phase 3: Enhancements in `src/data_handler.py` (`process_and_consolidate_contact_data`)

1.  **Log Input and Output Counts**:
    *   **Why**: To track the flow of items through the consolidation process.
    *   **How**:
        *   At the start: `logger.info(f"Processing {len(llm_results)} LLM result items for {company_name_from_input or initial_given_url} (Canonical: {canonical_base})")`
        *   At the end: `logger.info(f"Consolidated to {len(final_consolidated_list)} unique phone numbers for {company_name_from_input or initial_given_url} (Canonical: {canonical_base})")`

2.  **Log Skipped Malformed Items**:
    *   **Why**: To identify if raw LLM outputs are being discarded due to missing essential fields.
    *   **How**: Increment a counter for items skipped in the loop (due to missing `number` or `source_url`). Log this count before returning.
        *   Example: `if skipped_malformed_count > 0: logger.warning(f"{skipped_malformed_count} LLM items were skipped due to being malformed for {company_name_from_input or initial_given_url} (Canonical: {canonical_base}).")`

---

## Phase 4: Debuggability and Metrics

1.  **Review Saved LLM Context Files**:
    *   **Action**: The existing mechanism for saving LLM input and raw output files is valuable. Ensure these filenames are consistently logged alongside errors related to a specific canonical URL to facilitate easy retrieval. The `file_identifier_prefix` is key here.

2.  **Enhance `run_metrics.md`**:
    *   **Why**: For a high-level overview of these specific failure types.
    *   **How**: Add new counters to `run_metrics` in `main_pipeline.py`:
        *   `llm_processing_stats['llm_not_run_no_output_canonical_count']`
        *   `llm_processing_stats['llm_output_empty_no_relevant_canonical_count']`
        *   `llm_processing_stats['llm_output_empty_due_to_no_raw_candidates_count']` (derived from Phase 2.2 logic)
        *   `llm_processing_stats['llm_output_empty_due_to_filtering_count']` (derived from Phase 2.2 logic)
        *   `llm_processing_stats['llm_items_skipped_malformed_in_data_handler_count']` (sum of `skipped_malformed_count` from Phase 3.2 across all calls to data_handler)
    *   These counters would be incremented in `main_pipeline.py` as appropriate.

---

## Visual Plan (Mermaid Diagram)

```mermaid
graph TD
    A[Input Row] --> B{Scraping};
    B -- Success --> C{Regex Extraction};
    B -- Failure --> Z1[Log Scraper Failure];
    C -- No Candidates --> Z2[Log No Regex Candidates];
    C -- Has Candidates --> D{LLM Prompt Available?};
    D -- No --> Z3[Log Prompt Missing];
    D -- Yes --> E[LLM Call (llm_extractor_component.py)];
    E -- API Error/Retry Failure --> F{LLM Output Exists?};
    E -- Success --> F;
    F -- No (Critical LLM Error) --> G[Set Status: LLM_Not_Run_Or_NoOutput_For_Canonical];
    F -- Yes (LLM Responded) --> H{Parse & Validate LLM Output (llm_extractor_component.py)};
    H -- Parse/Validation Error --> G;
    H -- Success (Raw LLM Items) --> I{process_and_consolidate_contact_data (data_handler.py)};
    I -- All Items Filtered/Malformed OR Raw LLM Items were Empty --> J[Set Status: LLM_OutputEmpty_Or_NoRelevant_For_Canonical];
    I -- Has Consolidated Numbers --> K[Normal Processing];

    subgraph Logging Points
        Z1 --> L1[/Enhanced Log/];
        Z2 --> L1;
        Z3 --> L1;
        F -- No --> L2[/Log LLM Critical Failure Details/];
        H -- Parse/Validation Error --> L3[/Log LLM Output Processing Error/];
        I -- All Items Filtered... --> L4[/Log Reason for Emptiness/];
    end

    G --> M[Update run_metrics.md];
    J --> M;