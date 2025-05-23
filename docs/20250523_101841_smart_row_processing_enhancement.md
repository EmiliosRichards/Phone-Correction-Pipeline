# Smart Row Processing Enhancement

**Date:** 2025-05-23
**Author:** Roo (AI Assistant)

## Summary

This update introduces an enhancement to the data loading mechanism for CSV and Excel files. When an open-ended row processing range (e.g., "10-") is specified via the `ROW_PROCESSING_RANGE` environment variable, the system will now intelligently stop reading the input file after encountering a configurable number of consecutive empty rows. This prevents the unnecessary processing of potentially millions of blank rows in large spreadsheets, improving performance and resource efficiency.

## Key Changes

1.  **New Configuration (`.env`):**
    *   Added `CONSECUTIVE_EMPTY_ROWS_TO_STOP` to `.env.example` (defaulting to `3`). This variable controls how many consecutive empty rows trigger the stop condition. Setting it to `0` or a negative value disables this feature.

2.  **Configuration Loading (`src/core/config.py`):**
    *   `AppConfig` now reads and stores the `CONSECUTIVE_EMPTY_ROWS_TO_STOP` setting.

3.  **Data Handling Logic (`src/data_handler.py`):**
    *   The `load_and_preprocess_data` function was updated:
        *   If an open-ended range is used and `CONSECUTIVE_EMPTY_ROWS_TO_STOP` is active, the function now iterates through rows (using `openpyxl` for Excel and `csv` module for CSVs) and stops after the specified number of consecutive empty rows.
        *   The definition of an "empty row" is one where all cells are `None`, empty strings, or contain only whitespace.
        *   If the feature is disabled or a fixed row range is provided, the original pandas `read_csv`/`read_excel` behavior is maintained.