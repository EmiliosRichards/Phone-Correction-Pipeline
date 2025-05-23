# Recent Pipeline Enhancements & Next Steps

**Date:** 2025-05-23

This document summarizes the recent enhancements made to the pipeline, primarily focusing on improving reporting clarity and diagnosing LLM-related processing issues.

## Implemented Enhancements

1.  **Row Attrition Report Upgrade to Excel with Auto-Width:**
    *   The `row_attrition_report_{run_id}.csv` has been changed to `row_attrition_report_{run_id}.xlsx`.
    *   The report now uses the Excel format, with columns automatically adjusting their width for better readability.
    *   The `LLM_Error_Detail_Summary` column is explicitly included in this report.
    *   *Relevant Code:* [`main_pipeline.py`](main_pipeline.py) (function `write_row_attrition_report`).

2.  **Improved LLM Failure Diagnostics in Attrition Report:**
    *   If an exception occurs during an LLM API call (e.g., API error, timeout, model processing error), the specific exception type and message are now captured.
    *   This information is populated into the `LLM_Error_Detail_Summary` column of the `row_attrition_report_{run_id}.xlsx` when the `Final_Row_Outcome_Reason` is `LLM_Processing_Error_AllAttempts`. This provides direct insight into LLM call failures.
    *   *Relevant Code:* [`main_pipeline.py`](main_pipeline.py) (LLM processing `try-except` block, around line 681).

3.  **Refined Outcome Logic for Missing Regex Candidate Status:**
    *   In the `_determine_final_row_outcome_and_fault` function, if the status of whether regex candidates were found for a canonical URL (`canonical_site_regex_candidates_found_status`) is missing, it now defaults to `False` (i.e., assumes no candidates were found).
    *   This makes the assignment of `Final_Row_Outcome_Reason` more conservative and accurate, leaning towards `Canonical_NoRegexCandidatesFound` if this preceding step's status wasn't explicitly recorded.
    *   *Relevant Code:* [`main_pipeline.py`](main_pipeline.py) (around line 175).

4.  **Corrected `Original_Number_Status` Mapping:**
    *   The logic in [`main_pipeline.py`](main_pipeline.py) that maps the new, granular `Final_Row_Outcome_Reason` statuses back to the older `Original_Number_Status` column (for the main summary Excel report) has been updated.
    *   It now correctly uses the exact new status names (e.g., `LLM_Output_NoNumbersFound_AllAttempts`) for this mapping, ensuring consistency.
    *   *Relevant Code:* [`main_pipeline.py`](main_pipeline.py) (around line 1126).

## Natural Next Steps

1.  **Comprehensive Testing of Recent Changes:**
    *   Thoroughly test the new Excel-based Row Attrition Report for correct data population and column auto-width functionality.
    *   Specifically test scenarios that should trigger `LLM_Processing_Error_AllAttempts` to verify that the `LLM_Error_Detail_Summary` column is populated with meaningful error details.
    *   Validate outcomes for rows where `canonical_site_regex_candidates_found_status` might be missing to ensure the new default logic behaves as expected.

2.  **Investigate Persistent LLM Failure for Specific Row(s):**
    *   Run the pipeline with the latest changes, focusing on the row(s) that consistently cause LLM issues.
    *   **Meticulously examine:**
        *   The `row_attrition_report_{run_id}.xlsx`: Check `Final_Row_Outcome_Reason` and the (now hopefully populated) `LLM_Error_Detail_Summary`.
        *   The `llm_context` directory for that run:
            *   Look for `CANONICAL_{...}_llm_input_data.json` for the problematic canonical URL. Its content (or absence) is crucial.
            *   Look for `CANONICAL_{...}_llm_raw_output.json`. Its content (or absence) is also key.
        *   The main `pipeline_run_{run_id}.log` file: Search for the `RowID` or `CompanyName`, and look for any logged IOErrors during context file saving, or specific errors from the `llm_extractor_component`.

3.  **Consider Further Specificity for `LLM_Output_NumbersFound_NoneRelevant_AllAttempts`:**
    *   Currently, this status indicates the LLM returned numbers, but `data_handler.py` filtered them all out.
    *   To enhance this, `data_handler.py` could be modified to return a summary of *why* numbers were filtered (e.g., "all_faxes", "all_failed_country_check", "all_invalid_format_post_llm"). This summary could then be incorporated into a more specific `Final_Row_Outcome_Reason` or an additional detail column.

4.  **Enhance Logging for LLM Inputs:**
    *   Consider adding a debug-level log message immediately before the `llm_extractor.extract_phone_numbers` call. This log could include:
        *   The `final_canonical_entry_url`.
        *   The number of `all_candidate_items_for_llm` being sent.
        *   If `all_candidate_items_for_llm` is empty, this log should clearly state it, as this would explain why the LLM might not effectively process or why `llm_input_data.json` might be empty/missing.
    *   This would provide an explicit log point to confirm what was (or wasn't) passed to the LLM, complementing the `llm_input_data.json` file.