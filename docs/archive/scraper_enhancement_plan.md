# Scraper Enhancement Plan: Advanced Link Prioritization and Control

**Version:** 1.0
**Date:** 2025-05-20

## 1. Overall Objective

Enhance the web scraper to more intelligently select and prioritize internal links for scraping. The goal is to focus on pages most likely to contain contact, legal, and company information, while avoiding excessive scraping of less relevant content (e.g., blog articles, extensive help video sections). This will be achieved through a multi-tier scoring system for links, configurable keyword lists, path analysis, hard exclusions, and domain-specific page limits.

## 2. Phase 1: User Configuration (via `.env` file or similar)

The user will define the following settings to control the scraper's behavior:

1.  **`TARGET_LINK_KEYWORDS`**:
    *   **Description**: Comma-separated list of general keywords. A link's anchor text or its full URL (href) must contain one of these keywords for the link to be considered for further processing (after basic internal link validation).
    *   **Example**: `TARGET_LINK_KEYWORDS=contact,impressum,kontakt,legal,privacy,terms,ueber-uns,about,support,hilfe,datenschutz`

2.  **`SCRAPER_CRITICAL_PRIORITY_KEYWORDS` (New)**:
    *   **Description**: Comma-separated list of keywords that, if found as a standalone segment in a URL path, indicate a top-priority page (e.g., "Impressum", "Kontakt").
    *   **Example**: `SCRAPER_CRITICAL_PRIORITY_KEYWORDS=impressum,kontakt,contact,imprint`

3.  **`SCRAPER_HIGH_PRIORITY_KEYWORDS` (New)**:
    *   **Description**: Comma-separated list of keywords that, if found as a standalone segment in a URL path, indicate a high-priority (but not critical) page (e.g., "Legal", "Privacy").
    *   **Example**: `SCRAPER_HIGH_PRIORITY_KEYWORDS=legal,privacy,terms,datenschutz,ueber-uns,about,about-us`

4.  **`SCRAPER_MAX_KEYWORD_PATH_SEGMENTS` (New)**:
    *   **Description**: An integer. If a priority keyword (critical or high) is found as a standalone segment in a URL path with *more* segments than this number, its priority score might be slightly reduced. This helps prefer shorter, more direct paths like `/legal` over `/very/long/path/to/legal`.
    *   **Default Suggestion**: 3
    *   **Example**: `SCRAPER_MAX_KEYWORD_PATH_SEGMENTS=3`

5.  **`SCRAPER_EXCLUDE_LINK_PATH_PATTERNS` (Existing, role confirmed)**:
    *   **Description**: Comma-separated list of URL path substrings. If a link's path (case-insensitive) contains any of these patterns, it will be hard-excluded from scraping, regardless of keyword matches or score.
    *   **Example**: `SCRAPER_EXCLUDE_LINK_PATH_PATTERNS=/media/,/blog/,/wp-content/,/video/,/hilfe-video/`

6.  **`SCRAPER_MAX_PAGES_PER_DOMAIN` (Existing, role confirmed)**:
    *   **Description**: An integer. Limits the total number of pages scraped from a single domain during one `scrape_website` call. A value of `0` means no limit.
    *   **Default Suggestion**: 20
    *   **Example**: `SCRAPER_MAX_PAGES_PER_DOMAIN=20`

7.  **`SCRAPER_MIN_SCORE_TO_QUEUE` (New)**:
    *   **Description**: An integer. Links scoring below this value in the `find_internal_links` function will not be added to the scraping queue.
    *   **Default Suggestion**: 40
    *   **Example**: `SCRAPER_MIN_SCORE_TO_QUEUE=40`

8.  **`SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS` (New)**:
    *   **Description**: An integer. When `SCRAPER_MAX_PAGES_PER_DOMAIN` is reached, only links scoring at or above this threshold will be processed further. This allows critical pages to be scraped even if the general limit is met.
    *   **Default Suggestion**: 80
    *   **Example**: `SCRAPER_SCORE_THRESHOLD_FOR_LIMIT_BYPASS=80`

## 3. Phase 2: Code Implementation

### 3.1. Update `AppConfig` (`src/core/config.py`)

Add attributes to the `AppConfig` class to load and store the new configuration settings from environment variables. Provide sensible defaults.

*   `self.target_link_keywords: List[str]`
*   `self.scraper_critical_priority_keywords: List[str]`
*   `self.scraper_high_priority_keywords: List[str]`
*   `self.scraper_max_keyword_path_segments: int` (e.g., default `3`)
*   `self.scraper_exclude_link_path_patterns: List[str]` (e.g., default `[]`)
*   `self.scraper_max_pages_per_domain: int` (e.g., default `0`)
*   `self.scraper_min_score_to_queue: int` (e.g., default `40`)
*   `self.scraper_score_threshold_for_limit_bypass: int` (e.g., default `80`)

### 3.2. Overhaul `find_internal_links` function (`src/scraper/scraper_logic.py`)

This function will be significantly enhanced to implement the multi-tier scoring logic.

*   **Return Type**: `List[Tuple[str, int]]` where the tuple is `(normalized_url, score)`.
*   **Processing Steps for each link found in the HTML of a page:**
    1.  **Basic Filter**: Check if the link is internal (same domain) and uses HTTP/HTTPS. If not, discard.
    2.  **Target Keyword Check (Initial Gate)**: Check if the link's anchor text (lowercase) or its full URL href (lowercase) contains any keyword from `config.target_link_keywords`. If not, discard.
    3.  **Hard Exclusion**: Check if the link's path (lowercase) contains any pattern from `config.scraper_exclude_link_path_patterns`. If yes, discard and log.
    4.  **Scoring Logic**:
        *   Initialize `score = 0`.
        *   Parse the link's path into `path_segments` (e.g., `['web', 'de', 'kontakt']`). Let `num_segments = len(path_segments)`.
        *   **Tier 1: Critical Priority Keywords (Base Score: 100)**
            *   Iterate through `config.scraper_critical_priority_keywords`.
            *   If any `crit_keyword` is an *exact match* to any `segment` in `path_segments`:
                *   Set `current_tier_score = 100`.
                *   If `num_segments > config.scraper_max_keyword_path_segments`, apply a small penalty: `current_tier_score -= (num_segments - config.scraper_max_keyword_path_segments) * 5`.
                *   `score = max(score, current_tier_score)`.
                *   If `score >= 100` (or a high portion of it), break from keyword loops (found top tier).
        *   **Tier 2: High Priority Keywords (Base Score: 90)** (Only if `score < 90` from Tier 1)
            *   Iterate through `config.scraper_high_priority_keywords`.
            *   If any `high_keyword` is an *exact match* to any `segment` in `path_segments`:
                *   Set `current_tier_score = 90`.
                *   Apply similar path length penalty as Tier 1.
                *   `score = max(score, current_tier_score)`.
                *   If `score >= 90` (or high portion), break.
        *   **Tier 3: Priority Keyword (Critical or High) Early in Path (Base Score: 80)** (Only if `score < 80`)
            *   Combine `scraper_critical_priority_keywords` and `scraper_high_priority_keywords`.
            *   For each combined `p_keyword`, find its first occurrence `i` (0-indexed) as an *exact segment match* in `path_segments`.
            *   If found:
                *   `current_match_score = 80 - (i * 5)` (penalty for being deeper in path).
                *   If `num_segments > config.scraper_max_keyword_path_segments`, apply path length penalty: `current_match_score -= (num_segments - config.scraper_max_keyword_path_segments) * 5`.
                *   `score = max(score, current_match_score)`.
        *   **Tier 4: Target Keyword as Substring in Segment (Base Score: 50)** (Only if `score < 50`)
            *   Iterate through `config.target_link_keywords`.
            *   If any `target_keyword` is a *substring* of any `segment` in `path_segments`:
                *   `score = max(score, 50)`. Break.
        *   **Tier 5: Target Keyword in Link Anchor Text Only (Base Score: 40)** (Only if `score < 40`)
            *   If any `target_keyword` (from `config.target_link_keywords`) is a *substring* of the link's anchor text (lowercase):
                *   `score = max(score, 40)`.
    5.  **Final Check**: If the calculated `score >= config.scraper_min_score_to_queue`, add the `(normalized_link_url, score)` to the list of results.
*   **Return**: The list of `(url, score)` tuples for qualifying links.

### 3.3. Enhance `scrape_website` function (`src/scraper/scraper_logic.py`)

*   **Page Counter**: Initialize `pages_scraped_for_this_domain_count = 0` at the beginning of the function call.
*   **Queue Modification**: The `urls_to_scrape` list will now store tuples of `(url_string, depth_int, score_int)`.
*   **Link Processing & Queuing**:
    *   When `find_internal_links` returns a list of `(url, score)` tuples:
        *   Sort this list primarily by `score` (descending), and secondarily by URL length (ascending, as a tie-breaker to prefer shorter, cleaner URLs).
        *   For each `(url, score)` in the sorted list:
            *   Check if `url` is already in `globally_processed_urls` or already exists in the `urls_to_scrape` queue (to avoid duplicates).
            *   If not a duplicate, add `(url, current_depth + 1, score)` to the `urls_to_scrape` list.
        *   After adding all new candidates, re-sort the entire `urls_to_scrape` queue to ensure the highest score is always at the front for the next iteration. (Alternatively, use a priority queue data structure).
*   **Page Limit Enforcement**:
    *   When an item `(current_url, current_depth, current_score)` is popped from `urls_to_scrape`:
        *   Before calling `fetch_page_content`:
            *   If `config.scraper_max_pages_per_domain > 0` (i.e., limit is active) AND `pages_scraped_for_this_domain_count >= config.scraper_max_pages_per_domain`:
                *   If `current_score < config.scraper_score_threshold_for_limit_bypass`:
                    *   Log that the page limit is hit and the current page's score is below the bypass threshold.
                    *   `continue` to the next iteration of the `while urls_to_scrape:` loop (skipping the current low-score page).
    *   **Increment Counter**: After a page's content is successfully fetched and its processing begins (e.g., before text extraction or saving), increment `pages_scraped_for_this_domain_count`.

## 4. Phase 3: Future Enhancement (To be Documented Separately)

*   **"Try Root First" Logic**: Investigate and potentially implement a configurable option to attempt navigating to the domain root (`scheme + netloc`) as the initial step if the originally provided URL for a company resolves to a deep link. This could help in consistently finding site-wide main pages like "Impressum" or "Kontakt".

## 5. Mermaid Diagram (Conceptual Flow)

```mermaid
graph TD
    A[Start: Input Company/URL] --> B(Load Configs);
    B --> C{Normalize Initial URL};
    C --> D{Scrape Website (initial_url, depth=0, initial_score=100)};
    
    subgraph ScrapeWebsiteLoop
        direction LR
        E[Pop Highest Score from Queue (url, depth, score)] --> F{Globally Processed?};
        F -- Yes --> E;
        F -- No --> G{Page Limit Check (max_pages, current_count, score, bypass_threshold)};
        G -- Skip (Limit Hit, Score Too Low) --> E;
        G -- Proceed --> H[Fetch Page Content];
        H -- Success --> I[Increment Page Count for Domain];
        I --> J[Extract Text, Save Content];
        J --> K[Add Landed URL to Globally Processed Set];
        K --> L{Under Max Crawl Depth?};
        L -- Yes --> M[Call find_internal_links(current_page_html)];
        M --> N[Get List of (new_url, new_score) based on Tiered Scoring];
        N --> O[Filter by min_score_to_queue];
        O --> P[Add Valid New Links to Queue (maintain score sort)];
        P --> E;
        L -- No --> E;
        H -- Failure --> E;
    end
    D --> E;
    E -- Queue Empty --> Z[End Scrape for Company];
```

---
This plan provides a detailed roadmap for the requested enhancements.