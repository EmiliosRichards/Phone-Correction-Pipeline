# TLD Retry Enhancement Plan for Scraper

## 1. Goal

To enhance the `scrape_website` function in `src/scraper/scraper_logic.py` to implement a Top-Level Domain (TLD) retry mechanism. If an initial attempt to scrape a given URL fails, the system will systematically try alternative TLDs for the base domain. This retry logic is specifically for the *initial URL* provided to the scraper and not for subsequently discovered internal links.

## 2. Triggering Conditions for TLD Retry

The TLD retry mechanism will be triggered if the first attempt to scrape the `given_url` (i.e., the very first URL processed by `scrape_website` for a given input row) results in any `scraper_status` other than "Success".

## 3. TLD List for Retries

The list of TLDs to try will be sourced from the `app_config.url_probing_tlds` configuration, which is already defined in `src/core/config.py` (e.g., `['de', 'com', 'at', 'ch']`). The retries will attempt these TLDs in the order they are defined in this list.

## 4. Base Domain Extraction and TLD Replacement Strategy

To reliably construct alternative URLs:
*   The `tldextract` Python library will be added as a dependency.
*   When the initial scrape of `given_url` fails, `tldextract` will be used to parse `given_url` and extract its subdomain, domain, and suffix (original TLD).
*   New candidate URLs will be formed by combining: `subdomain` + `.` + `domain` + `.` + `new_tld_from_list`.
    *   Example: If `http://www.sub.example.co.uk` fails, and `.com` is next in the TLD list, the new candidate will be `http://www.sub.example.com`.
    *   Example: If `http://example.de` fails, and `.com` is next, the new candidate will be `http://example.com`.

## 5. Retry Limits and Stopping Condition

*   **Max Retries:** The system will attempt all TLDs specified in the `app_config.url_probing_tlds` list. There is no hard numerical limit other than the length of this list.
*   **Stopping Condition:** The TLD retry loop will stop immediately upon the first successful scrape of a TLD variant. The results from this successful attempt will be considered the outcome for the `given_url`.

## 6. Integration Strategy within `src/scraper/scraper_logic.py`

The `scrape_website` function will be refactored:

*   **New Internal Helper Function:** Introduce a new private helper function, tentatively named `_attempt_scrape_single_url(url_to_try: str, output_dir_for_run: str, company_name_or_id: str, globally_processed_urls: Set[str], input_row_id: Any, current_depth: int, is_initial_url_attempt: bool) -> Tuple[List[Tuple[str, str, str]], str, Optional[str], Set[str]]`.
    *   This function will encapsulate the current core logic of `scrape_website`:
        *   Playwright browser and page setup.
        *   Calling `fetch_page_content` for `url_to_try`.
        *   Processing the content (saving, text extraction).
        *   If `is_initial_url_attempt` is true and successful, it sets the `final_canonical_entry_url`.
        *   Finding internal links *only if* `is_initial_url_attempt` is false OR if it's the initial URL and it succeeded (to prevent link discovery on failed TLD variants of the initial URL).
        *   Managing `processed_urls_this_call` (which will be returned and merged by the caller).
    *   It will return the scraped page details, scraper status, the *landed URL* from this specific attempt, and the set of URLs processed during this single attempt.

*   **Modified `scrape_website` Function:**
    *   It will still be the main entry point.
    *   It will initialize `final_canonical_entry_url_for_run = None`, `overall_scraped_pages_details_for_run = []`, `final_status_for_run = "Unknown"`, and `processed_urls_for_this_entire_scrape_call = set()`.
    *   **Initial Attempt:**
        *   Call `_attempt_scrape_single_url` with the original `given_url`, `current_depth=0`, and `is_initial_url_attempt=True`.
        *   Store its results (pages, status, landed_url, processed_in_attempt).
        *   Add `processed_in_attempt` to `processed_urls_for_this_entire_scrape_call`.
        *   If successful, `final_canonical_entry_url_for_run` is set from the landed_url. `overall_scraped_pages_details_for_run` gets these pages. `final_status_for_run` is "Success".
    *   **TLD Retry Loop (if initial attempt failed):**
        *   If the status from the initial attempt is not "Success":
            *   Log that TLD retries are starting.
            *   Use `tldextract` to parse the original `given_url`.
            *   Iterate through `app_config.url_probing_tlds`:
                *   Construct the `candidate_tld_url`.
                *   If `candidate_tld_url` is the same as the original `given_url` (after normalization), skip it.
                *   Call `_attempt_scrape_single_url` with `candidate_tld_url`, `current_depth=0`, and `is_initial_url_attempt=True`.
                *   Add its `processed_in_attempt` to `processed_urls_for_this_entire_scrape_call`.
                *   If this attempt is successful:
                    *   `final_canonical_entry_url_for_run` is set from its landed_url.
                    *   `overall_scraped_pages_details_for_run` gets these pages.
                    *   `final_status_for_run` is "Success".
                    *   Break the TLD retry loop.
                *   Else (if this TLD variant also failed), store its failure status as `final_status_for_run` (so the last attempt's status is reported if all fail).
    *   **Internal Link Processing (if any initial URL attempt was successful):**
        *   If `final_status_for_run` is "Success" and `final_canonical_entry_url_for_run` is set:
            *   Initialize a queue for internal links using `final_canonical_entry_url_for_run` as the base, depth 0.
            *   The existing loop logic for processing the `urls_to_scrape` queue (from the original `scrape_website`) will now call `_attempt_scrape_single_url` for each internal link, with `is_initial_url_attempt=False` and appropriate `current_depth`.
            *   Results (pages, processed URLs) from these internal link scrapes will be aggregated into `overall_scraped_pages_details_for_run` and `processed_urls_for_this_entire_scrape_call`.
    *   **Return Value:** `scrape_website` will return `overall_scraped_pages_details_for_run`, `final_status_for_run`, and `final_canonical_entry_url_for_run`.

## 7. Scope of TLD Retry

*   The TLD retry logic applies **only** if the very first fetch of the `given_url` (or its scheme-added version) fails within `scrape_website`.
*   If the initial `given_url` is successfully scraped (e.g., the homepage loads), establishing a `final_canonical_entry_url`, then subsequent failures of *internal links* discovered from that site will **not** trigger TLD retries for those internal links. The base domain is considered validated at that point.

## 8. DNS Resolution for TLD Variants

The `_attempt_scrape_single_url` function, when calling `fetch_page_content` (which uses Playwright), will inherently handle DNS resolution for each TLD variant. No separate `socket.gethostbyname` check is needed for TLD variants *within this new retry mechanism*, as Playwright's navigation attempt will serve as the check.

## 9. Dependency Management

*   Add `tldextract` to the `requirements.txt` file.

## 10. Diagrammatic Flow (Simplified)

```mermaid
graph TD
    A[Start scrape_website(given_url)] --> B{Attempt initial scrape: _attempt_scrape_single_url(given_url, is_initial=true)};
    B -- Success --> F{Process internal links from successful URL};
    F --> G[Return aggregated results & Success status];
    B -- Failure --> C{Parse given_url with tldextract};
    C --> D{Iterate app_config.url_probing_tlds};
    D -- For each new_tld --> E{Construct candidate_url};
    E --> E_Attempt{Attempt scrape: _attempt_scrape_single_url(candidate_url, is_initial=true)};
    E_Attempt -- Success --> F;
    E_Attempt -- Failure --> D_Loop{More TLDs?};
    D_Loop -- Yes --> E;
    D_Loop -- No --> H[Return last failure status];

    subgraph _attempt_scrape_single_url
        direction LR
        S1[Setup Playwright] --> S2[fetch_page_content(url_to_try)];
        S2 -- Success --> S3[Extract text, save content];
        S3 --> S4{is_initial_url_attempt AND successful?};
        S4 -- Yes --> S5[Set final_canonical_entry_url];
        S5 --> S6[Discover internal links];
        S4 -- No --> S6;
        S6 --> S7[Return page_details, status, landed_url];
        S2 -- Failure --> S7;
    end
```

## 11. Logging

Enhance logging within `scrape_website` to clearly indicate:
*   When the initial URL scrape fails.
*   When TLD retries are being initiated.
*   Which candidate TLD URL is being attempted.
*   The success or failure of each TLD variant attempt.
*   The final URL that was successfully scraped after retries, if any.