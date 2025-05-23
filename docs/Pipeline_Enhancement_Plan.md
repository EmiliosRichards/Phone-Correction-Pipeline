# Pipeline Enhancement Plan

This document outlines potential enhancements for the phone number extraction pipeline, based on observations during development and analysis of its error handling and reporting capabilities.

## 1. Enhanced Input Validation and Pre-processing

*   **More Granular URL Validation**:
    *   Implement more sophisticated checks for common URL typos or structural issues beyond basic scheme validation (e.g., `http:/example.com` instead of `http://example.com`).
    *   Consider a "URL health check" step that attempts a HEAD request to quickly identify dead links or immediate redirect loops before committing to full scraping.
*   **Duplicate Input Row Handling**:
    *   While duplicate input company names and URLs are now reported in `metrics.md` and `row_attrition_report.xlsx`, consider adding a configurable strategy for handling them directly (e.g., process only the first instance, flag subsequent ones, or allow processing all but link them).
*   **Configuration for Input Column Names**:
    *   Currently, input column names like "Unternehmen" are hardcoded in `src/data_handler.py`'s `rename_map`. Make these configurable via `AppConfig` or a separate mapping file for greater flexibility if input formats vary.

## 2. Improved Scraping Robustness and Strategy

*   **Smarter TLD Probing**:
    *   The current TLD probing appends common TLDs. Enhance this by:
        *   Allowing a configurable list of TLDs to try.
        *   Potentially using a service or library to suggest likely TLDs based on company name or partial domain.
*   **Dynamic Timeout Adjustments**:
    *   Consider dynamically adjusting page/navigation timeouts based on initial server response times or domain history if a domain is known to be slow.
*   **JavaScript Rendering Challenges**:
    *   For sites heavily reliant on JavaScript to render contact information, ensure Playwright's waiting strategies (`networkidle`, specific selectors) are robust.
    *   Explore options for more advanced JS-heavy site interaction if current methods prove insufficient for certain targets.
*   **Handling "Cookie Banner" / "Consent Pop-up" Obstructions**:
    *   Develop a more generic strategy to detect and attempt to dismiss common cookie banners or consent pop-ups that might overlay contact information or prevent interaction. This could involve looking for common keywords/button texts (e.g., "Accept", "Agree", "Dismiss").

## 3. Enhanced LLM Interaction and Post-processing

*   **Refined Prompt Engineering for Edge Cases**:
    *   Continuously refine the LLM prompt based on observed failure modes, especially for:
        *   Distinguishing between phone numbers and other numerical data (IDs, dates).
        *   Better type classification for ambiguous numbers.
        *   Handling numbers presented in unconventional formats.
*   **Confidence Scoring for LLM Extractions**:
    *   Explore if the LLM can provide a confidence score for each extracted number and its type. This could be used for more nuanced filtering or prioritization in reports.
*   **Feedback Loop for LLM Results**:
    *   Consider a mechanism (manual or semi-automated) to review and correct LLM outputs, potentially feeding this back to fine-tune prompts or a custom model in the future.
*   **More Sophisticated Number Consolidation**:
    *   The current consolidation logic is based on exact number matches. Explore fuzzy matching or considering number variations (e.g., with/without country code if context is clear) for more intelligent consolidation, though this needs careful handling to avoid incorrect merges.

## 4. Reporting and Traceability Improvements

*   **Interactive HTML Reports**:
    *   For `run_metrics.md` or the new `canonical_domain_processing_summary`, consider generating interactive HTML reports with sortable/filterable tables for easier analysis.
*   **Direct Hyperlinks in Excel Reports**:
    *   Where feasible, make the `Link_To_Canonical_Domain_Outcome` in `row_attrition_report.xlsx` a direct hyperlink to the corresponding domain entry within `canonical_domain_processing_summary_{run_id}.xlsx` (if Excel's capabilities allow easy cross-file linking based on sheet/named range or if both are tabs in one workbook).
*   **Visual Pipeline Flow Diagram in Metrics**:
    *   Consider embedding or linking to a visual representation (like the `reporting_Pipeline_image.png`) within `run_metrics.md` to help users understand the stages.

## 5. Error Handling and Debugging

*   **More Specific Exception Handling**:
    *   Continue to refine `try-except` blocks to catch more specific exceptions, providing even more targeted error messages in logs and reports.
*   **Centralized Error Code/Message Definition**:
    *   While `FAULT_CATEGORY_MAP_DEFINITION` exists, ensure all distinct error messages and outcome reasons are well-documented and potentially centralized for easier maintenance and understanding.
*   **"Dry Run" Mode**:
    *   Implement a "dry run" mode that simulates processing (e.g., URL validation, TLD probing, identifying pages to scrape) without actually performing network requests or LLM calls. This would be useful for quick validation of input data and pipeline logic.

## 6. Performance and Scalability

*   **Asynchronous Operations**:
    *   Review if other parts of the pipeline (beyond scraping) could benefit from asynchronous operations if I/O bound (e.g., writing multiple output files if they become very large).
*   **Memory Profiling for Large Datasets**:
    *   For very large input files, conduct memory profiling to identify and optimize potential bottlenecks in DataFrame manipulations or data aggregation.

These enhancements aim to make the pipeline more robust, user-friendly, and insightful. They can be prioritized and implemented iteratively based on evolving needs and resources.