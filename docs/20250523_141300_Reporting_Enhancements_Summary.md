# Summary of Reporting and Traceability Enhancements (2025-05-23)

This document summarizes the key new features and improvements implemented in the phone number extraction pipeline, primarily focused on enhancing reporting clarity and data traceability.

## New Core Features:

1.  **Canonical Domain Journey Report (`canonical_domain_processing_summary_{run_id}.xlsx`)**:
    *   **Purpose**: Provides a comprehensive, domain-centric view of the pipeline's processing. Each row details the journey of a unique canonical base domain from input to final outcome.
    *   **Key Details Tracked**:
        *   Associated input row IDs, company names, and given URLs.
        *   List of all pathful URLs attempted under the canonical domain.
        *   Overall scraper status for the domain.
        *   Aggregated counts of scraped pages by type.
        *   Status of regex candidate finding and LLM call attempts for the domain.
        *   Counts of raw and consolidated numbers extracted by the LLM.
        *   Summary of LLM consolidated number types.
        *   Flags and messages for LLM processing errors.
        *   `Final_Domain_Outcome_Reason`: The concluding status for the canonical domain (e.g., "Contact_Successfully_Extracted_For_Domain", "Domain_NoRegexCandidatesFound_OnAnyPage").
        *   `Primary_Fault_Category_For_Domain`: The main reason if contacts were not found for the domain.

2.  **Enhanced Row Attrition Report (`row_attrition_report_{run_id}.xlsx`)**:
    *   **Purpose**: Improved traceability for input rows that did not yield contacts.
    *   **New Columns Added**:
        *   `Derived_Input_CanonicalURL`: The canonical URL derived directly from the input `GivenURL`.
        *   `Final_Processed_Canonical_Domain`: The actual canonical base domain processed for the input row (after any redirects, etc.).
        *   `Link_To_Canonical_Domain_Outcome`: The `Final_Processed_Canonical_Domain` value, allowing users to cross-reference this row with its corresponding entry in the `canonical_domain_processing_summary_{run_id}.xlsx`.

3.  **Improved `run_metrics_{run_id}.md`**:
    *   **New Section**: Includes a summary of the `canonical_domain_processing_summary` report, showing counts of canonical domains by their `Final_Domain_Outcome_Reason` and `Primary_Fault_Category_For_Domain`. This gives a high-level overview of domain processing success and failure points.

4.  **Enhanced `failed_rows_{run_id}.csv`**:
    *   **New Column**: `Associated_Pathful_Canonical_URL` added to provide a more direct link between a logged failure and the specific canonical URL (including its path) that was being processed at the time of the error.

## Supporting Code Changes:

*   **New Data Structures**: Introduced `canonical_domain_journey_data` in `main_pipeline.py` to aggregate all domain-centric information.
*   **New Helper Function (`_determine_final_domain_outcome_and_fault`)**: Created to systematically determine the final outcome and fault category for each unique canonical domain based on its aggregated processing data.
*   **Updated Reporting Functions**:
    *   [`write_canonical_domain_summary_report()`](main_pipeline.py:2050) created.
    *   [`write_row_attrition_report()`](main_pipeline.py:1667) updated to include new columns and use `canonical_domain_journey_data`.
    *   [`write_run_metrics()`](main_pipeline.py:1755) updated to include the new canonical domain summary.
    *   [`log_row_failure()`](main_pipeline.py:71) updated to include the associated pathful canonical URL.

These enhancements collectively aim to make the pipeline's operations more transparent, easier to debug, and provide richer insights into why contacts are, or are not, found for given inputs, especially at the crucial canonical domain processing level.