# Plan: URL Consolidation and Dual Excel Report Generation

This document outlines a plan to:
1.  Consolidate phone number data by the final canonical URL of a website, even if multiple input URLs redirect to it.
2.  Generate two distinct Excel reports:
    *   A **Detailed Flattened Report** with one row per unique LLM-extracted phone number, grouped under its canonical URL.
    *   A **Summary Report** with one row per original input URL, showing top phone numbers and an overall status, including information about redirects.
3.  Enhance logging for scraper statuses and redirect handling.

## Core Requirements Addressed:

*   Preventing data duplication in the detailed report when multiple input URLs point to the same website.
*   Clearly indicating in the summary report when an input URL was redirected or its data was sourced from an already processed canonical site.
*   Excluding data from sites where scraping failed (e.g., timeout, DNS error) from the detailed report.
*   Ensuring the detailed report lists unique phone numbers per canonical site, prioritizing by classification if duplicates are suggested by the LLM.
*   Adjusting column selection and order for both reports as per user feedback.

## Revised Plan Details:

### Phase 1: Enhance Scraper (`phone_validation_pipeline/src/scraper/scraper_logic.py`)

1.  **Modify `scrape_website` function:**
    *   **Return Values:** Change the return signature to:
        `Tuple[List[Tuple[str, str]], str, Optional[str]]`
        This corresponds to: `(scraped_pages_details, scraper_status, final_canonical_entry_url)`.
    *   **Logic:** Ensure `final_canonical_entry_url` is robustly determined. This is the URL of the very first page successfully accessed after all redirects from the initial `given_url` provided to `scrape_website`. If the initial `given_url` itself fails to scrape (e.g., timeout before any page content is retrieved), `final_canonical_entry_url` might be `None` or the last known URL before failure.

### Phase 2: Major Refactor of `main_pipeline.py`

1.  **Global Caches & Mapping (Initialize before the main loop):**
    *   `canonical_site_llm_results: Dict[str, List[PhoneNumberLLMOutput]] = {}`
        *   Stores the list of `PhoneNumberLLMOutput` objects, keyed by the `final_canonical_entry_url`.
    *   `canonical_site_scraper_status: Dict[str, str] = {}`
        *   Stores the `scraper_status` for each processed `final_canonical_entry_url`.
    *   `input_to_canonical_map: Dict[str, Optional[str]] = {}`
        *   Maps each original `GivenURL` from the input file to its determined `final_canonical_entry_url`.

2.  **First Pass - Scraping, LLM Processing, and Cache Population (Inside the main loop over input `df`):**
    *   For each `input_row` from `df`:
        *   Call `scrape_website(given_url_original, ...)` to get `scraped_pages_details`, `current_scraper_status`, and `current_final_canonical_entry_url`.
        *   Store `current_final_canonical_entry_url` in `df.at[index, 'CanonicalEntryURL']` (a new temporary column).
        *   Store `current_scraper_status` in `df.at[index, 'ScrapingStatus']`.
        *   Update `input_to_canonical_map[given_url_original] = current_final_canonical_entry_url`.
        *   **If `current_scraper_status == "Success"` AND `current_final_canonical_entry_url` is not `None`:**
            *   If `current_final_canonical_entry_url` is **NOT** already in `canonical_site_llm_results`:
                *   Extract regex snippets from `scraped_pages_details` to get `all_candidate_items_for_llm`.
                *   If `all_candidate_items_for_llm` exist:
                    *   Call `llm_extractor.extract_phone_numbers(...)` to get `llm_classified_outputs`.
                    *   Store these `llm_classified_outputs` in `canonical_site_llm_results[current_final_canonical_entry_url]`.
                *   Else (no regex candidates):
                    *   Store an empty list in `canonical_site_llm_results[current_final_canonical_entry_url]`.
                *   Store `current_scraper_status` (which is "Success") in `canonical_site_scraper_status[current_final_canonical_entry_url]`.
            *   Else (`current_final_canonical_entry_url` IS in `canonical_site_llm_results`):
                *   Log that this canonical URL has already been processed.
        *   Else (`current_scraper_status != "Success"`):
            *   If `current_final_canonical_entry_url` is known, store `current_scraper_status` in `canonical_site_scraper_status[current_final_canonical_entry_url]`.

3.  **Second Pass - Building Reports (After the first loop completes):**

    *   **A. Detailed Flattened Report (`phone_validation_detailed_output_{run_id}.xlsx`):**
        *   Initialize `all_flattened_rows = []`.
        *   Iterate through the original input `df` (`for index, original_row in df.iterrows():`).
            *   `scraper_status_for_original_row = original_row.get('ScrapingStatus')`.
            *   `canonical_url_for_original_row = original_row.get('CanonicalEntryURL')`.
            *   **If `scraper_status_for_original_row == "Success"` AND `canonical_url_for_original_row` is not `None` AND `canonical_url_for_original_row` in `canonical_site_llm_results`:**
                *   `llm_outputs_list = canonical_site_llm_results[canonical_url_for_original_row]`.
                *   **De-duplicate `llm_outputs_list`:** Use `best_llm_outputs_for_this_canonical_site = {}` and `classification_precedence` logic.
                *   For each `llm_item` in `best_llm_outputs_for_this_canonical_site.values()`:
                    *   Create `new_flattened_row_data`. Populate with `CompanyName`, `GivenURL` (original), `Canonical_URL`, `ScrapingStatus` (of canonical), LLM fields, `RunID`, `TargetCountryCodes`.
                    *   Append to `all_flattened_rows`.
        *   Create `df_detailed_flattened = pd.DataFrame(all_flattened_rows)`.
        *   **Sort `df_detailed_flattened`:** By `CompanyName`, `Canonical_URL`, then custom `LLM_Classification` order.
        *   **Define `detailed_columns_order`:** `['CompanyName', 'GivenURL', 'Canonical_URL', 'ScrapingStatus', 'LLM_Source_URL', 'LLM_Number', 'LLM_Type', 'LLM_Classification', 'TargetCountryCodes', 'RunID']`.
        *   Reorder/select columns. Save to `phone_validation_detailed_output_{run_id}.xlsx`.

    *   **B. Summary Report (modifying the main `df`):**
        *   Loop `for index, row in df.iterrows():`.
            *   Get `final_canonical_url = row.get('CanonicalEntryURL')`, `current_scraper_status = row.get('ScrapingStatus')`.
            *   `llm_outputs_for_summary = canonical_site_llm_results.get(final_canonical_url, [])`.
            *   `overall_status_prefix = ""`. If `final_canonical_url` and `input_to_canonical_map.get(row.get('GivenURL')) != row.get('GivenURL')`: `overall_status_prefix = f"RedirectedTo[{final_canonical_url}]_"`.
            *   Populate `Primary_Number_1`, `Secondary_Number_1/2` (and types, sourceURLs) in `df.at[index, ...]`.
            *   Determine and set `df.at[index, 'Original_Number_Status']`.
            *   Determine and set `df.at[index, 'Overall_VerificationStatus']`, prepending `overall_status_prefix`. Scraper status takes precedence if not "Success".
        *   **After loop, define `summary_columns_order`:** `['CompanyName', 'GivenURL', 'CanonicalEntryURL', 'GivenPhoneNumber', 'NormalizedGivenPhoneNumber', 'Description', 'ScrapingStatus', 'Original_Number_Status', 'Overall_VerificationStatus', 'Primary_Number_1', ..., 'Secondary_SourceURL_2', 'TargetCountryCodes', 'RunID']`.
        *   Select/reorder columns for `df`, drop unwanted. Save `df` to `phone_validation_output_{run_id}.xlsx`.

### Phase 3: Column Definitions in `data_handler.py` (`load_and_preprocess_data`)

*   In the `new_columns` list:
    *   **Add:** `CanonicalEntryURL` (initialized to `None`).
    *   Summary report columns (`Overall_VerificationStatus`, `Original_Number_Status`, `Primary_Number_1`, etc.) remain as planned.
    *   Obsolete columns removed as planned.

### Mermaid Diagram (Updated Conceptual Flow)

```mermaid
graph TD
    A[Start Pipeline] --> B(Load & Preprocess Data);
    B --> C[Add `CanonicalEntryURL` to df_cols, init summary cols];
    C --> D[Init `canonical_site_llm_results` cache, `input_to_canonical_map`, `canonical_site_scraper_status`];

    subgraph Pass1_ScrapeAndLLMCache
        D --> E{Loop `input_row` in `df`};
        E --> F[Scrape `input_row.GivenURL` -> `status`, `final_canonical_url`, `pages`];
        F --> G[Store `final_canonical_url` & `status` in `df` for `input_row`];
        G --> H[Update `input_to_canonical_map`];
        H --> I{`status=="Success"` AND `final_canonical_url` NOT IN `canonical_site_llm_results`?};
        I -- Yes --> J[LLM Process `pages` -> `llm_outputs`];
        J --> K[Store `llm_outputs` in `canonical_site_llm_results[final_canonical_url]`];
        K --> L[Store `status` in `canonical_site_scraper_status[final_canonical_url]`];
        L --> E_LoopEnd1[Next input_row];
        I -- No (or scrape fail) --> M{`status!="Success"` AND `final_canonical_url` known AND `final_canonical_url` NOT IN `canonical_site_scraper_status`?};
        M -- Yes --> N[Store `status` in `canonical_site_scraper_status[final_canonical_url]`];
        N --> E_LoopEnd1;
        M -- No --> E_LoopEnd1;
    end
    
    E_LoopEnd1 -- All input rows processed --> P[Start Pass 2: Build Reports];

    subgraph Pass2_BuildDetailedReport
        P --> Q[Init `all_flattened_rows = []`];
        Q --> R{Loop `original_row` in `df`};
        R --> S[Get `canonical_url = original_row.CanonicalEntryURL`];
        S --> T{`original_row.ScrapingStatus=="Success"` AND `canonical_url` IN `canonical_site_llm_results`?};
        T -- Yes --> U[Get `llm_list` from `canonical_site_llm_results[canonical_url]`];
        U --> V[De-duplicate `llm_list` -> `unique_llm_items`];
        V --> W{Loop `llm_item` in `unique_llm_items`};
        W --> X[Create `flat_row` with `original_row.Company`, `original_row.GivenURL`, `canonical_url`, `llm_item` data, etc.];
        X --> Y[Append `flat_row` to `all_flattened_rows`];
        Y --> W;
        W -- End unique_llm_items --> R_LoopEnd2;
        T -- No --> R_LoopEnd2;
        R_LoopEnd2 -- All original_rows for detailed --> Z[Create, Sort, Save `df_detailed_flattened`];
    end

    subgraph Pass2_BuildSummaryReport
        P --> AA[Loop `input_row` (index, row) in `df`];
        AA --> AB[Get `canonical_url = row.CanonicalEntryURL`];
        AB --> AC[Get `llm_list` for `canonical_url` from cache (if exists)];
        AC --> AD[Populate `Primary/Secondary` nos, `Original_Number_Status`, `Overall_VerificationStatus` in `df.at[index, ...]` based on `llm_list` and `row.ScrapingStatus`];
        AD --> AA_LoopEnd2[Next input_row];
        AA_LoopEnd2 -- All input_rows for summary --> AE[Select/Order cols, Save summary `df`];
    end
    
    Z --> AF[End];
    AE --> AF;