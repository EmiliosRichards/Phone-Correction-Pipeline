# Row Outcome Reasons & Fault Categories

This document defines the granular status reasons (`Final_Row_Outcome_Reason`) used to explain why an input row might not yield a final extracted contact, and the "Fault Categories" used to attribute these outcomes in the Row Attrition Report.

## `Final_Row_Outcome_Reason` Definitions

These statuses are assigned to each input row in the `phone_validation_output.csv` (or a similar designated output column) and are used in the `row_attrition_report_{run_id}.csv`. They provide specific explanations for non-extraction.

*   **`Input_URL_Invalid`**: The `GivenURL` provided in the input row was determined to be invalid (e.g., malformed, unparseable) by initial validation.
*   **`Input_URL_UnsupportedScheme`**: The `GivenURL` uses an unsupported URL scheme (e.g., `ftp://`, `mailto:`).
*   **`Scraping_AllAttemptsFailed_Network`**: All scraping attempts for all relevant URLs derived from the input row failed due to network-related issues (e.g., DNS lookup failure, connection timeout, unreachable server).
*   **`Scraping_AllAttemptsFailed_AccessDenied`**: All scraping attempts for all relevant URLs derived from the input row failed due to access restrictions (e.g., HTTP 403 Forbidden, consistent robots.txt disallowance across all relevant domains).
*   **`Scraping_ContentNotFound_AllAttempts`**: All scraping attempts for all relevant URLs derived from the input row resulted in content not found errors (e.g., HTTP 404 Not Found).
*   **`Scraping_Success_NoRelevantContentPagesFound`**: Scraping was successful for sites related to the input row, but no pages typically containing contact information (e.g., contact, imprint, privacy, about us) were identified or successfully scraped.
*   **`Canonical_Duplicate_SkippedProcessing`**: A canonical URL derived from this input row was already processed (or slated for processing) via a previous input row due to deduplication logic, so this input row's specific processing path was short-circuited to avoid redundant work.
*   **`Canonical_NoRegexCandidatesFound`**: For all successfully scraped canonical sites associated with the input row, no phone-like patterns (regex candidates) were found in their content.
*   **`LLM_NoInput_NoRegexCandidates`**: The LLM was not run for any relevant canonical sites associated with the input row because no regex candidates were available to form the LLM prompt.
*   **`LLM_Output_NoNumbersFound_AllAttempts`**: The LLM was run for relevant canonical sites, but it returned no phone numbers (or no parsable phone number structures) from any of them.
*   **`LLM_Output_NumbersFound_NoneRelevant_AllAttempts`**: The LLM found phone number candidates, but all of them were filtered out as low relevance (e.g., fax numbers, non-geographic service numbers, internal extensions) by the `data_handler.py` logic, across all relevant canonical sites.
*   **`LLM_Processing_Error_AllAttempts`**: An unrecoverable error occurred during all LLM call attempts for the relevant canonical sites associated with the input row (e.g., API errors, content generation failures).
*   **`DataConsolidation_Error_ForRow`**: A critical error occurred during the final data handling or consolidation phase specifically for this input row, preventing output.
*   **`Pipeline_Skipped_MaxRedirects_ForInputURL`**: The initial `GivenURL` for the input row resulted in exceeding the maximum allowed redirects during initial URL canonicalization or scraping.
*   **`Pipeline_Skipped_PreviouslyFailedInput`**: (If applicable in future re-run logic) The input row was intentionally skipped because it was marked as a known, persistent failure from a previous run.
*   **`Unknown_Processing_Gap_NoContact`**: A fallback status indicating that an input row completed processing without critical errors being logged for it, yet no contact information was extracted, and no other specific `Final_Row_Outcome_Reason` was met. This may indicate a gap in logic or an unhandled edge case.

## `Determined_Fault_Category` Definitions

These categories are used in the `row_attrition_report_{run_id}.csv` and `run_metrics.md` to provide a higher-level attribution for why an input row did not yield a contact.

*   **`Website Issue`**:
    *   *Applies to statuses like:* `Scraping_AllAttemptsFailed_Network`, `Scraping_AllAttemptsFailed_AccessDenied`, `Scraping_ContentNotFound_AllAttempts`, `Scraping_Success_NoRelevantContentPagesFound`, `Pipeline_Skipped_MaxRedirects_ForInputURL`.
    *   *Description:* The inability to extract a contact is primarily due to issues with the target website(s) (e.g., site is down, blocks scraping, has no contact information, content is missing or irrelevant).

*   **`LLM Issue`**:
    *   *Applies to statuses like:* `LLM_Output_NoNumbersFound_AllAttempts`, `LLM_Output_NumbersFound_NoneRelevant_AllAttempts`, `LLM_Processing_Error_AllAttempts`.
    *   *Description:* The LLM was involved, but either failed to process, found no numbers, or all numbers found were deemed not relevant by the pipeline's filtering logic.

*   **`Input Data Issue`**:
    *   *Applies to statuses like:* `Input_URL_Invalid`, `Input_URL_UnsupportedScheme`.
    *   *Description:* The problem originated from the input data provided to the pipeline (e.g., a malformed or unusable URL).

*   **`Pipeline Logic/Configuration`**:
    *   *Applies to statuses like:* `Canonical_Duplicate_SkippedProcessing`, `Canonical_NoRegexCandidatesFound`, `LLM_NoInput_NoRegexCandidates`, `Pipeline_Skipped_PreviouslyFailedInput`.
    *   *Description:* The non-extraction is a result of the pipeline's designed logic, configuration, or pre-processing steps (e.g., deduplication, lack of initial candidates for LLM, intentional skipping).

*   **`Pipeline Error`**:
    *   *Applies to statuses like:* `DataConsolidation_Error_ForRow`.
    *   *Description:* An internal error within the pipeline's data processing or consolidation steps prevented contact extraction for this specific row.

*   **`Unknown`**:
    *   *Applies to statuses like:* `Unknown_Processing_Gap_NoContact`.
    *   *Description:* The reason for non-extraction could not be specifically attributed to the above categories, indicating a potential need for further investigation into the pipeline's logic for this case.

This list will be maintained and updated as the pipeline evolves.