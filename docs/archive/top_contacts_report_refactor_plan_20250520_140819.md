# Plan: Refactor `Top_Contacts_Report` Generation

**Date:** 2025-05-20
**Status:** Approved

## 1. Overall Goal

To ensure the `Top_Contacts_Report_{run_id}.xlsx` (referred to in code as the "Tertiary Report") correctly handles scenarios where multiple input company names map to the same canonical base URL. The report should present a single, consolidated entry per canonical base URL, with aggregated information and clearly prioritized phone numbers.

## 2. Background

The current pipeline was recently updated to consolidate phone number data by canonical URL, de-duplicating numbers and aggregating their sources. However, the `Top_Contacts_Report` still generates one row per original input entry. The new requirement is to change this specific report to be "one row per unique canonical base URL."

## 3. Target Report for Major Change

*   **`Top_Contacts_Report_{run_id}.xlsx`** (Generated from `tertiary_report_file_name_template` in `app_config`, referred to as "Tertiary Report" in `main_pipeline.py`)

## 4. Detailed Plan for `Top_Contacts_Report_{run_id}.xlsx`

### 4.1. Structure
*   The report will have **one row per unique canonical base URL**.

### 4.2. Column Definitions and Population Logic:

*   **`CompanyName`**:
    *   Format: `[Canonical Base URL] - OriginalCompanyA - OriginalCompanyB - ...`
    *   (Where `OriginalCompanyA/B` are all unique company names from the input file that mapped to this canonical base URL, joined by " - ").
*   **`GivenURL`**:
    *   Content: All unique original `GivenURL`s from the input file that mapped to this canonical base URL, joined by a comma and space (e.g., ", ").
*   **`CanonicalEntryURL`**:
    *   Content: The unique canonical base URL itself.
*   **`Description`**:
    *   Action: This column will be **dropped** from the `Top_Contacts_Report`. The `tertiary_report_columns_order` list in `main_pipeline.py` will be updated accordingly.
*   **`ScrapingStatus`**:
    *   Content: The scraper status associated with the processing of the canonical base URL (e.g., "Success", "Scrape_Failed_NoContactPage").
*   **`PhoneNumber_1`, `PhoneNumber_2`, `PhoneNumber_3`**:
    *   Selection: Top 1 to 3 unique phone numbers for the canonical base URL, selected from the `consolidated_numbers` list (which is already sorted by LLM classification: Primary > Secondary > Support, etc.).
    *   Format: `[Number] (Aggregated Types) [AllInputCompaniesForThisCanonicalURL]`
        *   `[Number]`: The E.164 formatted phone number.
        *   `(Aggregated Types)`: A comma-separated string of unique LLM-determined types for that number (e.g., "(Main Line, Sales)").
        *   `[AllInputCompaniesForThisCanonicalURL]`: A comma-separated string of all unique original company names from the input file that mapped to this canonical base URL (e.g., "[Adolf Best, Tristar]").
*   **`SourceURL_1`, `SourceURL_2`, `SourceURL_3`**:
    *   Content: For the corresponding `PhoneNumber_X`, this will be a comma-separated list of ALL unique `original_full_url`s (from any input company that mapped to this canonical base URL) where this specific phone number was found.

## 5. Impact on Other Reports

*   **`phone_validation_output_{run_id}.xlsx`** (Summary Report): Will **remain as is** (i.e., one row per original input row from the source file).
*   **`All_LLM_Extractions_Report_{run_id}.xlsx`** (Detailed Flattened Report): Will **remain as is** (i.e., listing all LLM extractions, typically tied back to the input row that triggered the processing for a canonical URL).

## 6. Code Implementation Steps (in `main_pipeline.py`)

### 6.1. Data Aggregation for `Top_Contacts_Report` (New Step)
*   Location: Before the current "Tertiary Report" generation loop (currently around line `main_pipeline.py:543`).
*   Logic:
    1.  Create an empty dictionary: `top_contacts_aggregation_map = {}`.
    2.  Iterate through `canonical_site_consolidated_data.items()`:
        *   For each `(canonical_url, company_contact_details_object)`:
            *   If `company_contact_details_object` is None, skip or handle as an error case for this canonical URL.
            *   Find all original input rows from `df` that map to this `canonical_url`. This can be done by checking `df['CanonicalEntryURL'] == canonical_url`.
            *   Collect unique original `CompanyName` values from these matching input rows.
            *   Collect unique original `GivenURL` values from these matching input rows.
            *   Format the new `report_company_name = f"{canonical_url} - {' - '.join(sorted(list(unique_original_company_names)))}"`.
            *   Format `report_given_urls = ", ".join(sorted(list(unique_original_given_urls)))`.
            *   Store in the map:
                ```python
                top_contacts_aggregation_map[canonical_url] = {
                    "report_company_name": report_company_name,
                    "report_given_urls": report_given_urls,
                    "canonical_entry_url": canonical_url,
                    "scraper_status": canonical_site_scraper_status.get(canonical_url, "Unknown"),
                    "contact_details": company_contact_details_object,
                    "all_input_companies_for_canonical": sorted(list(unique_original_company_names)) # For PhoneNumber_X formatting
                }
                ```

### 6.2. Modify `Top_Contacts_Report` Row Generation Loop
*   The loop that populates `all_tertiary_rows` (currently starts around `main_pipeline.py:496`, specifically section "C. Tertiary Report") will now iterate `top_contacts_aggregation_map.values()`.
*   Inside the loop, for each `aggregated_entry`:
    *   `new_tertiary_row['CompanyName'] = aggregated_entry["report_company_name"]`
    *   `new_tertiary_row['GivenURL'] = aggregated_entry["report_given_urls"]`
    *   `new_tertiary_row['CanonicalEntryURL'] = aggregated_entry["canonical_entry_url"]`
    *   `new_tertiary_row['ScrapingStatus'] = aggregated_entry["scraper_status"]`
    *   Populate `PhoneNumber_1/2/3` and `SourceURL_1/2/3`:
        *   Access `consolidated_numbers = aggregated_entry["contact_details"].consolidated_numbers`. This list is already sorted.
        *   For each `consolidated_number_item` in `consolidated_numbers` (up to 3):
            *   `number_str = consolidated_number_item.number`
            *   `types_str = ", ".join(sorted(list(set(s.type for s in consolidated_number_item.sources))))`
            *   `companies_for_number_str = ", ".join(aggregated_entry["all_input_companies_for_canonical"])`
            *   `PhoneNumber_X_value = f"{number_str} ({types_str}) [{companies_for_number_str}]"`
            *   `SourceURL_X_value = ", ".join(sorted(list(set(s.original_full_url for s in consolidated_number_item.sources))))`
            *   Assign these to the respective `new_tertiary_row` keys.

### 6.3. Update `tertiary_report_columns_order`
*   Remove `'Description'` from this list in `main_pipeline.py`.

## 7. Code Cleanup

*   Remove the initialization of the unused `'AllCompanyContacts'` column from the `required_cols` dictionary in `main_pipeline.py` (around line 138).

## 8. Diagram of Planned `Top_Contacts_Report` Generation

```mermaid
graph TD
    %% Pass 1 - Data Collection and Consolidation (Existing)
    InputDataFrame[Input DataFrame (df)] --> LoopPass1{For each row in df (Original Input)};
    LoopPass1 --> ScrapeAndLLM[Scrape & LLM Process for row's GivenURL];
    ScrapeAndLLM --> ConsolidateDataFunction{data_handler.process_and_consolidate_contact_data};
    ConsolidateDataFunction --> CachedConsolidatedData[canonical_site_consolidated_data (Map: CanonicalURL -> CompanyContactDetails)];

    %% New Aggregation Step for Top_Contacts_Report
    CachedConsolidatedData --> AggregateLoop{For each CanonicalURL in CachedConsolidatedData};
    InputDataFrame -- Used by --> AggregateLoop; %% To find all original CompanyNames/GivenURLs for a CanonicalURL
    AggregateLoop --> BuildAggregatedEntry[Build Aggregated Entry for Top Contacts Report];
    BuildAggregatedEntry --> TopContactsAggMap[top_contacts_aggregation_map (Map: CanonicalURL -> AggregatedInfo)];

    %% Generation of Top_Contacts_Report (Modified)
    TopContactsAggMap --> GenReportLoop{For each AggregatedInfo in TopContactsAggMap};
    GenReportLoop --> FormatRow[Format ONE row for Top_Contacts_Report.xlsx];
    FormatRow --> FinalReportList[all_tertiary_rows list];
    FinalReportList --> WriteFile[Write Top_Contacts_Report.xlsx];
```

This plan aims to deliver the `Top_Contacts_Report` in the desired "one row per canonical URL" format with aggregated company and source information.