# Plan: Enhanced URL Handling and Logging in Pipeline (2025-05-22_124815)

**Objective**: Improve the robustness and clarity of URL processing in the initial stages of the pipeline, particularly for inputs that may not be fully-formed URLs. This involves implementing a TLD probing mechanism and refining logging for better traceability.

## Phase 1: Configuration for TLD Probing

*   **Status**: Planning complete.
*   **Details**:
    *   **File 1: `src/core/config.py`**
        *   Add to `AppConfig` class docstring (Attributes):
            `url_probing_tlds (List[str]): Comma-separated list of TLDs to try appending to domain-like inputs that lack a TLD (e.g., "de,com,at,ch").`
        *   Add to `AppConfig.__init__`:
            ```python
            # --- URL Probing Configuration ---
            url_probing_tlds_str: str = os.getenv('URL_PROBING_TLDS', 'de,com,at,ch')
            self.url_probing_tlds: List[str] = [tld.strip().lower() for tld in url_probing_tlds_str.split(',') if tld.strip()]
            ```
    *   **File 2: `.env.example`**
        *   Add new entry:
            ```dotenv
            # === URL Handling Configuration ===
            # Comma-separated list of Top-Level Domains (TLDs) to try appending to domain-like inputs
            # that appear to be missing a TLD. The pipeline will attempt to probe these in order.
            # Example: "de,com,at,ch,org,net"
            URL_PROBING_TLDS="de,com,at,ch"
            ```

## Phase 2: Modify URL Preprocessing in `main_pipeline.py`

*   **Target Area**: Within the main processing loop (around lines 262-309), specifically where URLs are currently being normalized and `.de` is appended.
*   **New Imports Needed**: `import socket` at the top of `main_pipeline.py`.

*   **Detailed Logic Changes**:

    1.  **Initial URL Cleaning (Existing)**:
        *   Keep existing logic for stripping whitespace and adding `http://` if schemeless.
        *   Keep existing logic for removing spaces from the domain part.

    2.  **TLD Detection and Probing Loop (Replaces simple `.de` append)**:
        *   After basic cleaning, check if the `current_netloc` (domain part) appears to have a valid TLD (e.g., using `re.search(r'\.[a-zA-Z]{2,}$', current_netloc)`).
        *   **If NO TLD is detected AND `current_netloc` is not empty (and not 'localhost' or an IP):**
            *   Log: `INFO - __main__ - Input domain '{current_netloc}' for '{company_name}' appears to lack a TLD. Attempting TLD probing...`
            *   `successfully_probed_tld = False`
            *   `probed_netloc_base = current_netloc` (store the base netloc before appending TLDs for probing)
            *   Loop through `tld_to_try` in `app_config.url_probing_tlds`:
                *   `candidate_domain_to_probe = f"{probed_netloc_base}.{tld_to_try}"`
                *   Log: `DEBUG - __main__ - Probing TLD: Trying '{candidate_domain_to_probe}' for '{company_name}'`
                *   Try:
                    *   `socket.gethostbyname(candidate_domain_to_probe)`
                    *   If successful:
                        *   `current_netloc = candidate_domain_to_probe` # Update current_netloc with the successful one
                        *   Log: `INFO - __main__ - TLD probe successful for '{company_name}'. Using '{current_netloc}' after trying '.{tld_to_try}'.`
                        *   `successfully_probed_tld = True`
                        *   Break from the TLD probing loop.
                    *   If `socket.gaierror` (or other relevant socket errors for DNS failure):
                        *   Log: `DEBUG - __main__ - TLD probe failed for '{candidate_domain_to_probe}' for '{company_name}'.`
                        *   Continue to the next TLD in the list.
                *   Catch other potential exceptions during `gethostbyname` and log them as debug.
            *   **After the loop**:
                *   If `not successfully_probed_tld`:
                    *   Log: `WARNING - __main__ - TLD probing failed for base domain '{probed_netloc_base}' for '{company_name}'. Proceeding with original input (or last attempted if logic implies).`
                    *   // `current_netloc` would remain `probed_netloc_base` if no probe succeeded.
        *   **Else (TLD already detected or netloc was empty/localhost/IP):**
            *   Proceed as before (no TLD probing needed for this case).

    3.  **URL Reconstruction (Existing, but uses potentially modified `current_netloc`)**:
        *   Reconstruct `processed_url` using the (potentially TLD-probed) `current_netloc`.

    4.  **Logging of Final `processed_url`**:
        *   Ensure a clear log message shows the `original_given_url` and the *final* `processed_url` that is being passed to the scraper for each row.
            *   Example: `INFO - __main__ - URL for '{company_name}': Original='{given_url_original}', Processed for Scraper='{processed_url}'`

## Phase 3: Review and Refine Logging in `src.data_handler.py` (Post-Scraping)

*   **Objective**: Reduce misleading warnings during final report generation.
*   **Target Functions**: `get_canonical_base_url` and any other functions in `data_handler.py` that validate URLs and are called with original input URLs during later pipeline stages (consolidation, reporting).
*   **Action**:
    1.  Identify where these functions are called in `main_pipeline.py` during report generation or data consolidation.
    2.  **Preferred Change**: Modify the calling code in `main_pipeline.py` to pass the *final, scraped canonical URL* (`df.at[index, 'CanonicalEntryURL']`) to these `data_handler.py` functions if the purpose is to report on or use the URL that was actually processed.
    3.  **Alternative**: Modify the warning messages within `data_handler.py` functions to specify that the validation is on the *original input URL*.
        *   Example: `logger.warning(f"Original input URL '{url_string}' (from initial data) does not appear to be a valid absolute URL. This may be expected if it was transformed and processed successfully earlier in the pipeline.")`

## Phase 4: Testing Strategy (Post-Implementation)

1.  **Test with existing data**: Re-run with the current `data_to_be_inputed.xlsx`.
    *   Observe logs for `LEGALPROD`: It should now try `legalprod.de` (fail DNS), then `legalprod.com` (hopefully succeed DNS and scrape).
    *   Observe logs for other inputs like `NotarTec`: It should try `notartec.de` (succeed), and potentially not need to try `.com` if `.de` is first and successful.
    *   Check that the late-stage warnings from `src.data_handler` are either gone (if using processed URLs) or are rephrased.
2.  **Test LLM Retry Logic**: (As detailed in previous plans - create a specific test case to force a number mismatch and verify retry behavior).

## Mermaid Diagram for Enhanced URL Probing (Conceptual within `main_pipeline.py` loop)

```mermaid
graph TD
    A[Get original_given_url from input row] --> B{Is it a valid http/https URL?};
    B -- Yes --> C[processed_url = original_given_url];
    B -- No --> D{Add 'http://' if schemeless};
    D --> E{Does current_netloc have a TLD?};
    E -- Yes --> F[processed_url = schemeless_handled_url];
    E -- No --> G[Start TLD Probing (probed_netloc_base = current_netloc)];
    G --> H{For tld_to_try in AppConfig.url_probing_tlds:};
    H -- Try TLD --> I{Construct candidate_domain = probed_netloc_base + '.' + tld_to_try};
    I --> J{DNS lookup for candidate_domain successful?};
    J -- Yes --> K[current_netloc = candidate_domain, Log success, successfully_probed_tld=true, Break probing];
    J -- No --> H;
    H -- Loop exhausted or Break --> P{successfully_probed_tld?};
    P -- No --> Q[Log probing failure, current_netloc remains probed_netloc_base];
    P -- Yes --> R[current_netloc is the successfully probed domain];
    C --> S_Reconstruct[Reconstruct processed_url with final current_netloc];
    F --> S_Reconstruct;
    K --> S_Reconstruct;
    Q --> S_Reconstruct;
    R --> S_Reconstruct;
    S_Reconstruct --> Z[Log Original & Final Processed URL, Send to Scraper];