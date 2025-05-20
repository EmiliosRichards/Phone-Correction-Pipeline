# System Audit Plan

**Objective:** To thoroughly understand the current state of the three separate systems (Scraper, Phone Number Extractor, Automated LLM Prompter), their individual functionalities, how they interact, their data flows, strengths, and identify areas of misalignment or potential improvement, in preparation for future integration into a unified system.

**Scope:** The audit will cover the codebase, documentation, configuration, data storage (local and PostgreSQL), and operational workflow of the three systems.

**Audit Steps & Focus Areas:**

**I. Individual System Analysis:**

*   **A. Scraper System:**
    1.  **Functionality Review:**
        *   Confirm core scraping capabilities (Playwright usage, dynamic content handling).
        *   Assess OCR integration (Tesseract) and its effectiveness.
        *   Review local file storage structure and content (HTML, text, JSON, images).
    2.  **Database Interaction (Shared PostgreSQL):**
        *   Analyze how it populates `companies`, `scraping_logs`, and `scraped_pages` tables.
        *   Verify data consistency between local file paths stored in DB and actual files.
    3.  **Configuration:**
        *   Review `.env` setup for database connection and scraper parameters.
        *   Examine [`config.py`](scraper/src/scraper_app/config.py:1).
    4.  **Code Structure & Quality:**
        *   Review modularity (e.g., [`db_utils.py`](scraper/src/scraper_app/db_utils.py:1), [`scraper.py`](scraper/src/scraper_app/scraper.py:1), [`url_processor.py`](scraper/src/scraper_app/url_processor.py:1)).
        *   Assess logging ([`logging_utils.py`](scraper/src/scraper_app/logging_utils.py:1)) and error handling ([`exceptions.py`](scraper/src/scraper_app/exceptions.py:1)).
    5.  **Documentation:**
        *   Review [`README.md`](scraper/README.md:1), [`USAGE.md`](scraper/USAGE.md:1), [`scraper_usage.md`](scraper/scraper_usage.md:1), [`database_structure_analysis.md`](scraper/database_structure_analysis.md:1).
    6.  **Strengths:**
        *   Working scraping mechanism.
        *   Dual storage (local files + PostgreSQL).
        *   OCR capability.

*   **B. Phone Number Extractor System:**
    1.  **Functionality Review:**
        *   Analyze text normalization process ([`src/text/normalizer.py`](python%20phonenumbers%20extractor/src/text/normalizer.py:1)).
        *   Assess phone number extraction logic ([`src/phone/extractor.py`](python%20phonenumbers%20extractor/src/phone/extractor.py:1)) using `phonenumbers` library and custom patterns ([`config/patterns.json`](python%20phonenumbers%20extractor/config/patterns.json:1)).
        *   Review validation mechanisms (custom rules, optional Twilio via [`src/phone/validator.py`](python%20phonenumbers%20extractor/src/phone/validator.py:1)).
    2.  **Database Interaction (Shared PostgreSQL):**
        *   Confirm how it reads data from `companies`, `scraped_pages`, `scraping_logs`.
        *   Analyze how it populates `raw_phone_numbers`, `cleaned_phone_numbers`.
        *   Detail its update process for the `scraping_logs` table.
        *   Review the schema defined in [`scripts/legacy/init_db.py`](python%20phonenumbers%20extractor/scripts/legacy/init_db.py:1) as the likely source of truth for the shared DB.
    3.  **Configuration:**
        *   Review `.env` setup (especially DB connection, Twilio keys).
    4.  **Code Structure & Quality:**
        *   Review modularity (e.g., [`src/db/utils.py`](python%20phonenumbers%20extractor/src/db/utils.py:1), `phone/`, `text/` modules).
        *   Assess logging and error handling.
    5.  **Documentation:**
        *   Review [`README.md`](python%20phonenumbers%20extractor/README.md:1), [`docs/API.md`](python%20phonenumbers%20extractor/docs/API.md:1), [`docs/USAGE.md`](python%20phonenumbers%20extractor/docs/USAGE.md:1).
    6.  **Strengths:**
        *   Effective phone number extraction and validation.
        *   Significant PostgreSQL integration.

*   **C. Automated LLM Prompter System:**
    1.  **Functionality Review:**
        *   Assess multi-LLM support (Gemini, Llama, Mixtral) via client architecture (`llm_pipeline/clients/`).
        *   Review structured JSON output and schema validation ([`llm_pipeline/common/pydantic_schemas.py`](automated%20llm%20prompter/llm_pipeline/common/pydantic_schemas.py:1), [`llm_pipeline/common/schema_utils.py`](automated%20llm%20prompter/llm_pipeline/common/schema_utils.py:1)).
    2.  **Data Input/Output:**
        *   Confirm input is plain text files (sourced from Scraper output).
        *   Review local file storage for outputs (`data/llm_runs/`).
    3.  **Configuration:**
        *   Analyze "profile" system ([`llm_pipeline/config.py`](automated%20llm%20prompter/llm_pipeline/config.py:1)) for managing LLM models, API keys, parameters, and prompt strategies.
        *   Review externalized prompt templates (`prompts/` directory).
        *   Review `.env` setup for API keys and connection details.
    4.  **Code Structure & Quality:**
        *   Review modularity (client factory, common utilities).
        *   Assess logging ([`llm_pipeline/common/log.py`](automated%20llm%20prompter/llm_pipeline/common/log.py:1)) and metrics collection ([`llm_pipeline/common/metrics.py`](automated%20llm%20prompter/llm_pipeline/common/metrics.py:1)).
    5.  **Documentation:**
        *   Review [`README.md`](automated%20llm%20prompter/README.md:1), [`llm_pipeline/USAGE.md`](automated%20llm%20prompter/llm_pipeline/USAGE.md:1), [`gemini_structured_output_guide.md`](automated%20llm%20prompter/gemini_structured_output_guide.md:1).
    6.  **Strengths:**
        *   Highly adjustable and configurable (model, profile, prompt, Pydantic models).
        *   Working well, especially Gemini profile.
        *   Modular client design.

**II. Inter-System Analysis & Workflow:**

1.  **Overall Data Flow Diagram:**
    *   Create a visual representation (e.g., Mermaid diagram) of how data moves between the three systems and the database.
    ```mermaid
    graph LR
        A[Internet/Websites] --> B(Scraper System);
        B -- Local Files (HTML, Text, Images) --> D{Manual File Transfer};
        B -- DB Writes (companies, scraped_pages, scraping_logs) --> C[(Shared PostgreSQL DB)];
        D --> E(Phone Number Extractor System);
        C -- DB Reads (companies, scraped_pages, scraping_logs) --> E;
        E -- DB Writes (raw_phones, cleaned_phones) --> C;
        E -- DB Updates (scraping_logs) --> C;
        B -- Scraped Plain Text Files --> F{Manual File Transfer for LLM};
        F --> G(Automated LLM Prompter);
        G -- Local JSON Output --> H[LLM Results Storage];

        subgraph "Current Manual Steps"
            D
            F
        end
    ```

2.  **Database Cohesion:**
    *   Confirm shared tables are used consistently.
    *   Analyze potential impacts of the Phone Extractor updating `scraping_logs` used by the Scraper.
3.  **Data Handoff Points:**
    *   Detail the manual file transfer from Scraper output to Phone Extractor input.
    *   Detail the manual file transfer from Scraper output to LLM Prompter input.
4.  **Data Transformation/Cleaning:**
    *   Map out where text cleaning/normalization occurs in each system (Scraper, Phone Extractor).
    *   Identify potential redundancies or information loss points, as per your concern.

**III. Alignment & Improvement Opportunities:**

1.  **Misalignments & Redundancies:**
    *   Identify any conflicting assumptions or duplicated efforts (e.g., multiple text cleaning stages).
    *   Assess impact of different default DB names in configs vs. actual shared usage.
2.  **Areas for Improvement (towards unification):**
    *   Automation of manual file transfers.
    *   Streamlining data preprocessing.
    *   Potential for direct data feeds (e.g., LLM prompter reading from DB or a more integrated pipeline).
    *   Strategies for eventual PostgreSQL removal (e.g., shifting to a different data store, or more file-based interim storage).
3.  **Strengths to Leverage:**
    *   Modularity of LLM prompter's profiles.
    *   Robustness of scraper and phone extractor.
    *   Existing documentation.

**IV. Deliverables of the Audit:**

1.  A comprehensive audit report (this document, once fleshed out with findings).
2.  Updated data flow diagrams.
3.  A list of identified strengths, weaknesses/misalignments, and opportunities for improvement.
4.  Recommendations for preparing the systems for future unification and the eventual phasing out of the SQL database.