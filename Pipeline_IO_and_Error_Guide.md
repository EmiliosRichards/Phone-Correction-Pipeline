# Pipeline Input, Output, and Error Guide

This document provides an overview of the expected inputs for the phone number extraction pipeline, the various output files it generates, and a detailed explanation of potential row-level and domain-level failure reasons and outcomes.

## 1. Pipeline Input

The primary input to the pipeline is an Excel file (typically `.xlsx`).

**Default Input File Name:** `data_to_be_inputed.xlsx` (configurable via `INPUT_EXCEL_FILE_PATH` in `.env`).

**Expected Columns:**
The pipeline expects the input Excel file to contain the following columns. The German column names are automatically mapped to the English equivalents used internally by the pipeline:

*   **`Unternehmen`** (mapped to `CompanyName`): The name of the company.
*   **`Webseite`** (mapped to `GivenURL`): The URL of the company's website. This is the primary URL used for scraping.
*   **`Telefonnummer`** (mapped to `GivenPhoneNumber`): An optional existing phone number for the company. If provided, it will be normalized and can be used for comparison.
*   **`Beschreibung`** (mapped to `Description`): An optional description of the company.
*   **`TargetCountryCodes`** (Optional): A column that can contain a list of target country codes (e.g., `["DE", "AT", "CH"]`) to help with phone number parsing for that specific row. If not provided, global defaults from the configuration are used.

The pipeline can be configured to process a specific range of rows from the input file using the `ROW_PROCESSING_RANGE` environment variable (e.g., `1-100`, `101-`, `-50`).

## 2. Pipeline Outputs

All output files are generated within a unique run-specific directory: `output_data/{run_id}/`, where `{run_id}` is a timestamp like `YYYYMMDD_HHMMSS`.

### 2.1. Log Files

*   **`pipeline_run_{run_id}.log`**:
    *   **Description**: The main log file for the entire pipeline run. It contains detailed operational messages, informational logs, warnings, and errors encountered during processing. This is the first place to look for diagnosing issues or understanding the pipeline's behavior for a specific run.
    *   **Format**: Text file.

### 2.2. Data & Report Files (Excel & CSV)

*   **`failed_rows_{run_id}.csv`**:
    *   **Description**: Logs details for input rows that encountered specific, significant failures during processing, preventing them from completing the full pipeline successfully.
    *   **Format**: CSV file.
    *   **Key Columns**:
        *   `log_timestamp`: Timestamp of the failure.
        *   `input_row_identifier`: The original index or ID of the input row.
        *   `CompanyName`: Company name from the input.
        *   `GivenURL`: Original URL from the input.
        *   `stage_of_failure`: The specific pipeline stage where the failure occurred (see Section 3.2).
        *   `error_reason`: A concise reason for the failure.
        *   `error_details`: JSON string with more detailed context about the error.
        *   `Associated_Pathful_Canonical_URL`: The canonical URL (often including a path) that was being processed when the failure occurred.

*   **`All_LLM_Extractions_Report_{run_id}.xlsx`**:
    *   **Description**: Contains all raw phone number objects extracted by the Language Model (LLM) from scraped web pages, *before* any consolidation or de-duplication. This report is useful for understanding the LLM's raw performance and the variety of numbers it identifies.
    *   **Format**: Excel file (`.xlsx`).
    *   **Key Columns**:
        *   `CompanyName`: Company name associated with the extraction.
        *   `Number`: The extracted phone number string.
        *   `LLM_Type`: The type assigned to the number by the LLM (e.g., "Main Line", "Sales").
        *   `LLM_Classification`: The classification assigned by the LLM (e.g., "Primary", "Secondary").
        *   `LLM_Source_URL`: The specific web page URL from which the number was extracted.
        *   `ScrapingStatus`: The scraping status of the `LLM_Source_URL`.
        *   `TargetCountryCodes`: Target country codes used for this row.
        *   `RunID`: The pipeline run ID.

*   **`Pipeline_Summary_Report_{run_id}.xlsx`** (Filename configurable via `OUTPUT_EXCEL_FILE_NAME_TEMPLATE`):
    *   **Description**: This is the main output file that mirrors the input rows and appends various processing results and extracted contact information. Each row corresponds to an input row.
    *   **Format**: Excel file (`.xlsx`).
    *   **Key Columns (includes input columns plus):**
        *   `NormalizedGivenPhoneNumber`: The input phone number, normalized.
        *   `ScrapingStatus`: Status of the initial scraping attempt for the `GivenURL`.
        *   `Overall_VerificationStatus`: An overall status indicating if/how contacts were verified or why not.
        *   `Original_Number_Status`: Status related to the `GivenPhoneNumber` (e.g., Verified, Corrected, Not Found).
        *   `Top_Number_1`, `Top_Type_1`, `Top_SourceURL_1`: Details for the top (highest priority) extracted phone number.
        *   `Top_Number_2`, `Top_Type_2`, `Top_SourceURL_2`: Details for the second top extracted phone number.
        *   `Top_Number_3`, `Top_Type_3`, `Top_SourceURL_3`: Details for the third top extracted phone number.
        *   `CanonicalEntryURL`: The canonical base domain derived and processed for the input row.
        *   `ScrapingStatus_Canonical`: The overall scraping status for the `CanonicalEntryURL`.
        *   `LLM_Processing_Status_Canonical`: Status of LLM processing for the `CanonicalEntryURL`.
        *   `Final_Row_Outcome_Reason`: The final outcome for this input row (see Section 3.1).
        *   `Determined_Fault_Category`: The primary fault category if the row didn't yield a contact (see Section 3.3).
        *   `RunID`: The pipeline run ID.

*   **`Final Contacts.xlsx`** (Filename configurable via `TERTIARY_REPORT_FILE_NAME_TEMPLATE`):
    *   **Description**: A contact-focused report showing up to three top phone numbers per unique canonical domain. Company names and given URLs are aggregated if multiple input rows map to the same canonical domain.
    *   **Format**: Excel file (`.xlsx`).
    *   **Key Columns**:
        *   `CompanyName`: Aggregated company names (e.g., "domain.com - Company A - Company B").
        *   `GivenURL`: Aggregated original input URLs.
        *   `CanonicalEntryURL`: The unique canonical base domain.
        *   `ScrapingStatus`: Overall scraping status for this canonical domain.
        *   `PhoneNumber_1`, `PhoneNumber_2`, `PhoneNumber_3`: Top extracted phone numbers with their types and source companies, e.g., "+49123456 (Main Line) [Company A]".
        *   `SourceURL_1`, `SourceURL_2`, `SourceURL_3`: Aggregated source URLs for the corresponding phone numbers.

*   **`Final_Processed_Contacts.xlsx`** (Filename configurable via `PROCESSED_CONTACTS_REPORT_FILE_NAME_TEMPLATE`):
    *   **Description**: A simplified and cleaned list of contacts, derived from `Final Contacts.xlsx`. This report is often used for final output or integration.
    *   **Format**: Excel file (`.xlsx`).
    *   **Key Columns**:
        *   `Company Name`: Extracted base domain name (e.g., "example" from "example.com").
        *   `URL`: The `CanonicalEntryURL`.
        *   `Number`: The extracted phone number.
        *   `Number Type`: The type of the phone number (e.g., "Main Line").
        *   `Number Found At`: The source URL where the number was found.

*   **`row_attrition_report_{run_id}.xlsx`**:
    *   **Description**: Provides details for each input row that did *not* result in a successfully extracted and consolidated contact. It explains *why* a contact wasn't found for that specific input row.
    *   **Format**: Excel file (`.xlsx`).
    *   **Key Columns**:
        *   `InputRowID`: Original identifier of the input row.
        *   `CompanyName`, `GivenURL`: Original input data.
        *   `Derived_Input_CanonicalURL`: Canonical URL derived directly from the `GivenURL`.
        *   `Final_Processed_Canonical_Domain`: The canonical domain that was actually processed for this input row (after redirects, etc.).
        *   `Link_To_Canonical_Domain_Outcome`: The `Final_Processed_Canonical_Domain`, used to link to the `canonical_domain_processing_summary` report.
        *   `Final_Row_Outcome_Reason`: The specific reason why this input row did not yield a contact (see Section 3.1).
        *   `Determined_Fault_Category`: The broader category of failure (see Section 3.3).
        *   `Relevant_Canonical_URLs`: The canonical URL(s) associated with this input row's processing.
        *   `LLM_Error_Detail_Summary`: Specific LLM error messages, if applicable.
        *   `Input_CompanyName_Total_Count`, `Input_CanonicalURL_Total_Count`: Counts of how many times the input company name/URL appeared in the entire input file.
        *   `Is_Input_CompanyName_Duplicate`, `Is_Input_CanonicalURL_Duplicate`, `Is_Input_Row_Considered_Duplicate`: Flags indicating if the input row was a duplicate based on company name or URL.
        *   `Timestamp_Of_Determination`: When the outcome was determined.

*   **`canonical_domain_processing_summary_{run_id}.xlsx`**:
    *   **Description**: A detailed report tracking the processing journey for each *unique canonical domain* encountered by the pipeline. This is key for understanding how a domain (which might be linked to multiple input rows) was processed overall.
    *   **Format**: Excel file (`.xlsx`).
    *   **Key Columns**:
        *   `Canonical_Domain`: The unique canonical base domain.
        *   `Input_Row_IDs`: Comma-separated list of input row IDs that mapped to this canonical domain.
        *   `Input_CompanyNames`: Comma-separated list of unique company names from input rows mapping to this domain.
        *   `Input_GivenURLs`: Comma-separated list of unique `GivenURL`s from input rows mapping to this domain.
        *   `Pathful_URLs_Attempted_List`: Comma-separated list of unique pathful URLs (domain + path) attempted under this canonical domain.
        *   `Overall_Scraper_Status_For_Domain`: The best scraping status achieved for any pathful URL under this domain.
        *   `Total_Pages_Scraped_For_Domain`: Total number of pages successfully scraped for this domain.
        *   `Scraped_Pages_Details_Aggregated`: JSON string showing counts of scraped pages by type (e.g., "Contact", "Imprint").
        *   `Regex_Candidates_Found_For_Any_Pathful`: Boolean, true if regex found any candidates on any page of this domain.
        *   `LLM_Calls_Made_For_Domain`: Boolean, true if any LLM calls were made for pages under this domain.
        *   `LLM_Total_Raw_Numbers_Extracted`: Total count of raw phone number objects extracted by LLM for this domain.
        *   `LLM_Total_Consolidated_Numbers_Found`: Total count of unique, consolidated phone numbers after LLM processing for this domain.
        *   `LLM_Consolidated_Number_Types_Summary`: JSON string summarizing counts of consolidated number types (e.g., "Main Line", "Fax").
        *   `LLM_Processing_Error_Encountered_For_Domain`: Boolean, true if any LLM processing error occurred for this domain.
        *   `LLM_Error_Messages_Aggregated`: Comma-separated list of LLM error messages encountered for this domain.
        *   `Final_Domain_Outcome_Reason`: The final outcome for this canonical domain (see Section 3.4).
        *   `Primary_Fault_Category_For_Domain`: The primary fault category if the domain didn't yield contacts (see Section 3.3).

### 2.3. Metrics & Temporary Files

*   **`run_metrics_{run_id}.md`**:
    *   **Description**: A Markdown file summarizing various statistics for the pipeline run, including task durations, data processing counts (input rows, duplicates, successes, failures), scraping stats, regex stats, LLM stats (call counts, token usage, errors), report generation stats, and summaries of row-level failures and canonical domain outcomes.
    *   **Format**: Markdown file (`.md`).

*   **`llm_context/` subdirectory**:
    *   **Description**: Contains JSON files related to LLM processing for each canonical URL.
        *   `CANONICAL_{url_safe_name}_llm_input_data.json`: The regex candidates sent to the LLM.
        *   `CANONICAL_{url_safe_name}_llm_raw_output.json`: The raw JSON response from the LLM.
        *   `CANONICAL_{url_safe_name}_llm_parsed_output.json`: The LLM response parsed into `PhoneNumberLLMOutput` objects.
    *   **Purpose**: Debugging LLM behavior and understanding its inputs/outputs.

*   **`scraped_content/` subdirectory**:
    *   **Description**: Contains text files (`.txt`) with the extracted textual content from each successfully scraped web page. Filenames typically include a sanitized version of the company name and a hash or counter for uniqueness.
    *   **Purpose**: Reviewing the content that was fed into the regex and LLM stages.

## 3. Failure Reasons & Outcome Explanations

This section details the various status, failure, and outcome reasons that can appear in the output reports.

### 3.1. `Final_Row_Outcome_Reason` (in `Pipeline_Summary_Report` & `row_attrition_report`)

This field in the `Pipeline_Summary_Report` and `row_attrition_report` explains the final result for each *input row*.

*   **`Contact_Successfully_Extracted`**: At least one valid, consolidated phone number was successfully extracted for the canonical domain associated with this input row.
*   **`Input_URL_Invalid`**: The `GivenURL` for this input row was fundamentally invalid (e.g., malformed, unparseable) and could not be processed.
*   **`Pipeline_Skipped_MaxRedirects_ForInputURL`**: The `GivenURL` led to too many redirects and was abandoned before scraping could effectively occur.
*   **`ScrapingFailure_InputURL_{status}`**: The initial attempt to process/scrape the `GivenURL` itself failed with the specified `{status}` before a canonical domain could be robustly determined or processed.
*   **`Unknown_NoCanonicalURLDetermined`**: A canonical URL could not be determined for the input row, and no earlier specific input URL failure was logged. This often indicates an issue with the input URL that wasn't caught by initial validation but prevented scraper from establishing a clear canonical target.
*   **`Scraping_NoPathfulURLs_ForCanonical`**: A canonical domain was identified, but no specific pages (pathful URLs) under it could be queued or attempted for scraping.
*   **`Scraping_AllAttemptsFailed_Network`**: All scraping attempts for all relevant pages under the canonical domain failed due to network-related issues (e.g., DNS lookup failure, timeouts, connection refused).
*   **`Scraping_AllAttemptsFailed_AccessDenied`**: All scraping attempts for relevant pages under the canonical domain failed due to access restrictions (e.g., HTTP 403 Forbidden, robots.txt exclusion if active).
*   **`Scraping_ContentNotFound_AllAttempts`**: All relevant pages under the canonical domain were accessed, but none yielded findable content (e.g., HTTP 404 Not Found, or pages that were technically scraped but deemed empty/irrelevant by the scraper).
*   **`ScrapingFailed_Canonical_{status}`**: A generic scraping failure occurred for the canonical domain, where `{status}` provides more detail from the scraper's perspective (e.g., `Error_Generic`, `Error_Timeout`). This is a fallback if more specific "AllAttemptsFailed" reasons don't apply.
*   **`Canonical_Duplicate_SkippedProcessing`**: The canonical domain derived from this input row had already been processed (likely due to another input row mapping to the same canonical domain), and its results were re-used. No new scraping or LLM processing was performed for this specific input row's trigger.
*   **`Canonical_NoRegexCandidatesFound`**: Scraping was successful for the canonical domain, but no potential phone number candidates were found by the regex extractor on any of its pages.
*   **`LLM_Processing_Error_AllAttempts`**: Regex found candidates, but an error occurred during the LLM processing stage for all relevant attempts related to this canonical domain (e.g., LLM API error, prompt template missing, unrecoverable LLM output parsing issue).
*   **`LLM_NoInput_NoRegexCandidates`**: This outcome typically means that while scraping might have been successful, there were no regex candidates to send to the LLM. (This might overlap with `Canonical_NoRegexCandidatesFound` and its usage should be reviewed for clarity).
*   **`LLM_Output_NoNumbersFound_AllAttempts`**: The LLM was called successfully with regex candidates, but it did not return any phone number structures in its output across all attempts for this canonical domain.
*   **`LLM_Output_NumbersFound_NoneRelevant_AllAttempts`**: The LLM returned phone number structures, but after validation, normalization, and type/classification filtering, none were deemed relevant or usable for this canonical domain.
*   **`Unknown_Processing_Gap_NoContact`**: A contact was not extracted, and the failure doesn't fit neatly into any of the above predefined categories. This indicates a potential unexpected state or a gap in the outcome determination logic that needs investigation.

### 3.2. `stage_of_failure` (in `failed_rows_{run_id}.csv`)

This field indicates the specific point in the pipeline where a row-level failure was logged.

*   **`URL_Validation_InvalidOrMissing`**: Failure during initial validation of the `GivenURL` (e.g., malformed, empty after cleaning, unsupported scheme).
*   **`Regex_Extraction_FileReadError`**: An error occurred while trying to read a scraped content file to perform regex extraction.
*   **`LLM_Setup_PromptTemplateMissing`**: The LLM prompt template file could not be found, preventing LLM processing.
*   **`LLM_Processing_GeneralError`**: A general, unhandled exception occurred during the LLM extraction and processing phase for a specific set of candidates.
*   **`Scraping_{status}`**: Failure during the scraping phase for a specific URL. `{status}` can be:
    *   `Error_Network`: Network-level issue (DNS, timeout, connection refused).
    *   `Error_AccessDenied`: Access denied (HTTP 403, robots.txt).
    *   `Error_ContentNotFound`: Page not found (HTTP 404) or no meaningful content.
    *   `Error_Timeout`: Page load or operation timed out.
    *   `Error_Generic`: Other unspecified scraping error.
    *   `Already_Processed`: The specific pathful canonical URL had already been scraped and processed in this run.
    *   `InvalidURL`: The URL passed to the scraper was deemed invalid by the scraper itself.
    *   `MaxRedirects_InputURL`: Max redirects hit for the input URL.
    *   Other statuses as defined by the scraper logic.
*   **`RowProcessing_Pass1_UnhandledException`**: An unexpected Python exception occurred during the main processing loop (Pass 1) for an input row that wasn't caught by more specific error handlers.

### 3.3. `Determined_Fault_Category` / `Primary_Fault_Category_For_Domain`

This categorizes the primary reason for failure at a higher level, based on `FAULT_CATEGORY_MAP_DEFINITION`.

*   **`Input Data Issue`**: Problem with the provided input URL (e.g., invalid, unsupported scheme).
    *   Corresponds to outcomes like: `Input_URL_Invalid`, `Domain_InputLikeFailure_InvalidURL`.
*   **`Website Issue`**: Problem with accessing or finding content on the target website.
    *   Corresponds to outcomes like: `Scraping_AllAttemptsFailed_Network`, `Scraping_AllAttemptsFailed_AccessDenied`, `Scraping_ContentNotFound_AllAttempts`, `Scraping_Success_NoRelevantContentPagesFound`, `Pipeline_Skipped_MaxRedirects_ForInputURL`, `Scraping_NoPathfulURLs_Processed_ForDomain`, `Scraping_AllPathfulsFailed_Network_ForDomain`, etc.
*   **`Pipeline Logic/Configuration`**: Failure due to internal pipeline logic, configuration, or how data is handled (e.g., skipping duplicates, no regex candidates found before LLM).
    *   Corresponds to outcomes like: `Canonical_Duplicate_SkippedProcessing`, `Canonical_NoRegexCandidatesFound`, `LLM_NoInput_NoRegexCandidates`, `Domain_NoRegexCandidatesFound_OnAnyPage`, `LLM_NotCalled_DespiteRegexCandidates_ForDomain`.
*   **`LLM Issue`**: Problem related to the Language Model's processing or output.
    *   Corresponds to outcomes like: `LLM_Output_NoNumbersFound_AllAttempts`, `LLM_Output_NumbersFound_NoneRelevant_AllAttempts`, `LLM_Processing_Error_AllAttempts`, `LLM_Processing_Error_Encountered_For_Domain`, `LLM_Output_NoRawNumbersFound_ForDomain`, `LLM_Output_RawNumbersFound_NoneConsolidated_ForDomain`.
*   **`Pipeline Error`**: An internal error or unhandled exception within the pipeline code itself.
    *   Corresponds to outcomes like: `DataConsolidation_Error_ForRow`.
*   **`Unknown`**: The cause of failure could not be determined or doesn't fit other categories.
    *   Corresponds to outcomes like: `Unknown_Processing_Gap_NoContact`, `Unknown_Domain_Processing_Gap_NoContact`, `Unknown_NoCanonicalURLDetermined`.
*   **`N/A`**: Not applicable, typically used when contacts were successfully extracted.

### 3.4. `Final_Domain_Outcome_Reason` (in `canonical_domain_processing_summary`)

This field explains the final result for each *unique canonical domain*.

*   **`Contact_Successfully_Extracted_For_Domain`**: At least one valid, consolidated phone number was successfully extracted for this canonical domain.
*   **`Domain_InputLikeFailure_{status}`**: The canonical domain itself (or all its pathful URLs) effectively failed in a way similar to an initial input URL failure (e.g., all resulted in `InvalidURL` or `MaxRedirects`). `{status}` provides more detail.
*   **`Scraping_NoPathfulURLs_Processed_ForDomain`**: Although a canonical domain was identified, no specific pages (pathful URLs) under it were actually processed by the scraper (e.g., none could be queued or all were filtered out before scraping attempts).
*   **`Scraping_AllPathfulsFailed_Network_ForDomain`**: All attempted pathful URLs under this canonical domain failed due to network issues.
*   **`Scraping_AllPathfulsFailed_AccessDenied_ForDomain`**: All attempted pathful URLs under this canonical domain failed due to access restrictions.
*   **`Scraping_AllPathfuls_ContentNotFound_ForDomain`**: All attempted pathful URLs under this canonical domain were accessed but no usable content was found (e.g., 404s, empty pages).
*   **`ScrapingFailed_Domain_{status}`**: A generic scraping failure occurred for the domain where not all pathfuls necessarily failed in the same way, but the overall scraping effort for the domain was not successful. `{status}` reflects the aggregated or most representative scraper status.
*   **`Scraping_Success_NoPagesScraped_ForDomain`**: The scraping process for the domain was marked as "Success" at a high level (e.g., no critical errors), but ultimately zero pages were actually scraped or retained content for this domain.
*   **`Domain_NoRegexCandidatesFound_OnAnyPage`**: Scraping was successful for at least one page under this domain, but no potential phone number candidates were found by regex on any of those successfully scraped pages.
*   **`LLM_NotCalled_DespiteRegexCandidates_ForDomain`**: Regex candidates were found for this domain, but for some reason (e.g., an upstream error before the LLM call for all relevant pathfuls), the LLM was not actually invoked.
*   **`LLM_Processing_Error_Encountered_For_Domain`**: An error occurred during the LLM processing stage for this domain (e.g., API error, prompt issues, output parsing failures aggregated across pathful URLs).
*   **`LLM_Output_NoRawNumbersFound_ForDomain`**: The LLM was called successfully for this domain, but it did not return any phone number structures in its raw output.
*   **`LLM_Output_RawNumbersFound_NoneConsolidated_ForDomain`**: The LLM returned raw phone number structures, but after validation, normalization, and consolidation, no usable/relevant numbers remained for this domain.
*   **`Unknown_Domain_Processing_Gap_NoContact`**: A contact was not extracted for this domain, and the reason doesn't fit other predefined categories, indicating a potential unexpected state or logic gap.

---

This guide should help in understanding the data flow and interpreting the results and errors from the pipeline.