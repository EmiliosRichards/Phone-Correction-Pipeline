# Scalability Enhancement Plan for Phone Extraction Pipeline

## 1. Introduction and Goal

This plan outlines a phased approach to re-architect the phone extraction pipeline to efficiently process a high volume of URLs (5,000-20,000) within a target timeframe of approximately 24 hours. The plan emphasizes leveraging existing infrastructure (PostgreSQL), improving concurrency, and establishing robust data management and monitoring practices, while balancing accuracy, cost, speed, ease of use, and practicality. The target success rate for URL processing is 80%+.

## 2. Current System Analysis Summary

The existing pipeline processes URLs sequentially from an input file. For each URL:
*   A new Playwright browser instance is launched and closed by the `scrape_website` function.
*   Scraping involves internal link traversal based on keyword scoring, up to configurable depth and page limits.
*   Content is saved to flat files.
*   LLM processing (Gemini API) is triggered for unique canonical sites.
*   Caching of processed URLs and LLM outputs is done in memory within a single run.

**Key Bottlenecks for High Volume:**
*   Sequential processing of input URLs.
*   High overhead of launching/closing browser instances per URL.
*   Potential for API rate limits/costs with many unique domains.
*   File system strain from numerous small intermediate files.
*   Limited error handling and state management for long-running, large batches.

## 3. Proposed Architectural Changes

### Phase 1: Core Architectural Changes (Leveraging PostgreSQL)

This phase focuses on the most critical changes to enable concurrent processing and better state management.

**3.1. Database-Driven Workflow & URL Queue Management (PostgreSQL)**

*   **Schema Design (PostgreSQL):**
    *   `urls_to_process`: Manages input URLs, their status, retries, timestamps, and association with a `run_id`.
        *   Columns: `id` (PK), `run_id`, `input_url`, `normalized_url`, `company_name`, `status` ('pending', 'processing_scrape', 'scraped', 'processing_llm', 'llm_complete', 'success', 'failed_scrape', 'failed_llm', 'failed_invalid_url', 'robots_disallowed'), `retry_count`, `last_attempt_at`, `canonical_url`, `created_at`, `updated_at`.
    *   `scraped_pages`: Stores content from individual scraped pages.
        *   Columns: `id` (PK), `url_id` (FK to `urls_to_process.id`), `page_url`, `cleaned_text_content` (TEXT), `scraped_at`.
    *   `llm_extractions`: Stores results from LLM processing.
        *   Columns: `id` (PK), `page_id` (FK to `scraped_pages.id`), `phone_number`, `llm_type`, `llm_classification`, `source_snippet`, `processed_at`.
    *   Additional tables for consolidated results and final reporting data.
*   **Ingestion Process:**
    *   Modify `main_pipeline.py` (or create a new ingestion script) to load URLs from the input Excel into `urls_to_process` with 'pending' status and a unique `run_id`.

**3.2. Worker-Based Architecture for Scraping & Processing**

*   **Scraper Workers:**
    *   Develop Python scripts for scraper workers.
    *   Workers query `urls_to_process` for 'pending' URLs (using `SELECT ... FOR UPDATE SKIP LOCKED` for concurrency).
    *   Update URL status to 'processing_scrape'.
    *   **Persistent Playwright Instance:** Each worker process initializes one Playwright browser instance (or a small pool of contexts) upon startup and reuses it for multiple URLs.
    *   Call a refactored `scrape_website` function.
    *   Store cleaned text from scraped pages into the `scraped_pages` table.
    *   Update `urls_to_process` status to 'scraped' or 'failed_scrape'.
*   **LLM Workers (Optional Separation):**
    *   Can be separate processes querying for 'scraped' items.
    *   Perform regex extraction and call the LLM extractor.
    *   Store results in `llm_extractions`.
    *   Update status to 'llm_complete' or 'failed_llm'.
    *   Alternatively, scraper workers can trigger LLM processing directly.
*   **Concurrency:**
    *   Utilize Python's `multiprocessing` for CPU-bound tasks and `asyncio` (with `ThreadPoolExecutor` if needed for blocking I/O within async code) for I/O-bound tasks within workers.
    *   Make the number of concurrent workers and tasks per worker configurable.

**3.3. Refactor `scrape_website` and `main_pipeline.py`**

*   Modify `scrape_website` (in `src/scraper/scraper_logic.py`) to accept a pre-initialized Playwright `Page` or `Context` object.
*   The main loop in `main_pipeline.py` will be replaced by worker logic. The script may become an ingestion script and/or a worker manager.
*   Adapt caching logic to use the database (e.g., check for existing successfully processed `normalized_url` or `canonical_url`).

**3.4. Data Handling & Output**

*   **Intermediate Data:** Store scraped text directly in `scraped_pages.cleaned_text_content`. LLM inputs/outputs can also be stored in the database for auditing and retries.
*   **Final Reports:** Modify report generation to query the PostgreSQL database for data associated with a specific `run_id`.

### Phase 2: Enhancements & Monitoring

**3.5. Robust Error Handling & Retries**

*   Implement retry mechanisms (e.g., with exponential backoff) for scraping and LLM API calls within worker logic.
*   Update `retry_count` and `last_attempt_at` in the database.
*   Define maximum retry limits in `src/core/config.py`.

**3.6. Configuration for Scalability**

*   Add new configuration options in `src/core/config.py` for:
    *   Number of scraper worker processes.
    *   Number of concurrent scraping/LLM tasks per worker.
    *   Database connection parameters.
    *   Batch size for fetching URLs from the queue by workers.

**3.7. Monitoring & Logging**

*   **Database Metrics:**
    *   Regularly query PostgreSQL to monitor queue size, processing rates, error rates by type.
*   **Structured Logging:**
    *   Ensure all workers use the existing logging setup (`src/core/logging_config.py`).
    *   Include worker ID/process ID in log messages for easier aggregation and debugging.
    *   Implement log rotation.
*   **Basic Dashboarding:**
    *   Consider a simple web interface (e.g., Flask/Dash) or a BI tool connected to PostgreSQL for visualizing pipeline progress and health.

### Phase 3: Advanced Scalability & Distribution (Future Considerations)

**3.8. Distributed Workers**

*   If a single server becomes a bottleneck, extend the worker model to run on multiple machines.
*   This would likely involve a dedicated task queue (e.g., Celery with RabbitMQ/Redis, AWS SQS, Google Pub/Sub) for optimal task distribution, with PostgreSQL remaining the central data store.

**3.9. Optimized LLM Usage**

*   **Selective LLM Processing:** Implement logic to bypass LLM if regex extraction is highly confident.
*   **Batch LLM Requests:** Utilize batching if supported by the LLM API.
*   **Local LLMs:** If the GPU server becomes reliably available, explore using smaller, specialized local LLMs for certain tasks to reduce costs and API dependency.

**3.10. Centralized Configuration Management**

*   For distributed setups, consider a centralized configuration service or ensure consistent deployment of configuration files.

## 4. Proposed Architecture Diagram (Mermaid)

```mermaid
graph TD
    A[Input Excel File] --> B(URL Ingestor Script);
    B -- Loads URLs with new run_id --> C[(PostgreSQL Database)];
    C -- Stores: url_queue, scraped_content, llm_results, status, config -- C;

    subgraph Worker Processes/Server
        D1[Scraper Worker 1];
        D2[Scraper Worker 2];
        Dn[Scraper Worker N...];
    end

    B -- Triggers/Notifies --> D1;
    B -- Triggers/Notifies --> D2;
    B -- Triggers/Notifies --> Dn;

    D1 -- Fetches 'pending' URLs --> C;
    D1 -- Manages Playwright Instance --> E1[Playwright Browser 1];
    E1 -- Scrapes Websites --> F[Internet];
    D1 -- Stores scraped text --> C;
    D1 -- Updates URL status to 'scraped'/'failed_scrape' --> C;

    D2 -- Fetches 'pending' URLs --> C;
    D2 -- Manages Playwright Instance --> E2[Playwright Browser 2];
    E2 -- Scrapes Websites --> F;
    D2 -- Stores scraped text --> C;
    D2 -- Updates URL status to 'scraped'/'failed_scrape' --> C;

    Dn -- Fetches 'pending' URLs --> C;
    Dn -- Manages Playwright Instance --> En[Playwright Browser N];
    En -- Scrapes Websites --> F;
    Dn -- Stores scraped text --> C;
    Dn -- Updates URL status to 'scraped'/'failed_scrape' --> C;

    subgraph LLM Processing
        G[LLM Processor/Workers];
    end

    D1 -- Optionally sends data for LLM --> G;
    D2 -- Optionally sends data for LLM --> G;
    Dn -- Optionally sends data for LLM --> G;
    
    G -- Fetches 'scraped' data from DB OR receives directly --> C;
    G -- Performs Regex Extraction --> G;
    G -- Calls Gemini API --> H[Gemini LLM API];
    G -- Stores LLM results --> C;
    G -- Updates URL status to 'llm_complete'/'failed_llm' --> C;

    I[Report Generator] -- Queries processed data for run_id --> C;
    I -- Generates Excel Reports --> J[Output Reports];

    K[Monitoring System/Dashboard] -- Queries DB for metrics & status --> C;
    K -- Reads Aggregated Logs --> L[Log Files];

    classDef db fill:#c9f,stroke:#333,stroke-width:2px;
    classDef worker fill:#f96,stroke:#333,stroke-width:2px;
    classDef process fill:#9cf,stroke:#333,stroke-width:2px;
    class C,H,F db;
    class D1,D2,Dn,G worker;
    class B,I,K,E1,E2,En process;
```

## 5. Summary of Benefits

*   **Scalability:** Concurrent workers and optimized browser management will dramatically improve throughput.
*   **Efficiency:** Reusing browser instances significantly reduces per-URL overhead.
*   **Robustness:** Database-managed state enables better error tracking, retries, and recovery for long-running batches.
*   **Data Management:** Centralized data in PostgreSQL is more manageable, queryable, and easier to back up than numerous flat files.
*   **Monitoring:** Provides better insights into the pipeline's performance, health, and progress.
*   **Maintainability:** A more modular, worker-based architecture can be easier to maintain and extend.