# Enhanced Logging Plan for Phone Validation Pipeline

## 1. Overall Goal

To implement a comprehensive logging strategy that provides clear visibility into the inputs, outputs, and decision-making processes of various components within the phone validation pipeline. This will facilitate easier review, debugging, and understanding of the pipeline's behavior for each run.

## 2. Key Logging Requirements

*   **Primary Focus on File-Based Logging:** Generate a human-readable main log file for each pipeline run, stored in the run-specific output directory.
*   **Clean Console Output:** Keep command-line interface (CLI) output minimal, primarily showing high-level progress or critical errors. The default `INFO` level for console should be relatively clean.
*   **Configurable Log Levels:** Allow the verbosity of the file log to be configured via an environment variable (`LOG_LEVEL`), defaulting to `INFO`, with `DEBUG` available for more detailed troubleshooting.
*   **Dedicated File Dumps for Key Data:** Critical intermediate data points (raw scraped content, cleaned text, regex-extracted snippets, full LLM input prompts, and raw LLM responses) should be saved to dedicated files for every run, ensuring they are always available for detailed inspection.
*   **Main Log as a Narrative:** The main log file should provide a high-level narrative of the pipeline's execution for a given company, including references (file paths) to the dedicated data dump files.

## 3. Detailed Plan

### Phase 1: Core Logging Setup & Dedicated Data Dumps

#### A. Modify `logging_config.py` (`phone_validation_pipeline/src/core/logging_config.py`)

1.  **Update `setup_logging` Function:**
    *   Accept `log_file_path: Optional[str] = None` and `file_log_level=logging.INFO`, `console_log_level=logging.WARNING` arguments.
    *   **File Handler:**
        *   If `log_file_path` is provided, add a `logging.FileHandler` to the root logger.
        *   Set its level according to `file_log_level`.
        *   Use the existing `Formatter` (`%(asctime)s - %(name)s - %(levelname)s - %(message)s`).
    *   **Console Handler (`StreamHandler`):**
        *   Continue to use `sys.stdout`.
        *   Set its level according to `console_log_level` (e.g., `WARNING` by default to keep console clean).
        *   Use the same formatter.
    *   Ensure existing handlers are cleared before adding new ones to prevent duplication if called multiple times.

#### B. Update `AppConfig` (`phone_validation_pipeline/src/core/config.py`)

1.  **Add New Configuration Variables:**
    *   `LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO').upper()`
    *   `CONSOLE_LOG_LEVEL: str = os.getenv('CONSOLE_LOG_LEVEL', 'WARNING').upper()`
2.  **Update `.env.example`:**
    *   Add `LOG_LEVEL="INFO"`
    *   Add `CONSOLE_LOG_LEVEL="WARNING"`

#### C. Integrate in `main_pipeline.py`

1.  **Early Initialization:**
    *   In the `main()` function, after `run_id` and `run_output_dir` are determined:
        *   Construct `log_file_name = f"pipeline_run_{run_id}.log"`.
        *   Construct `log_file_path = os.path.join(run_output_dir, log_file_name)`.
        *   Call `setup_logging(level=getattr(logging, app_config.log_level, logging.INFO), log_file_path=log_file_path, console_log_level=getattr(logging, app_config.console_log_level, logging.WARNING))`. This will reconfigure the root logger with the file handler and appropriate levels.

#### D. Implement Dedicated File Dumps for Key Data Points

1.  **Raw Scraped Data:**
    *   **Component:** `scraper_logic.py`
    *   **Action:** Already saves individual page contents (e.g., to `individual_pages/{company_name}__{sanitized_url}.txt`).
    *   **Logging:** `main_pipeline.py` will log the paths or a summary of these files in the main run log.
2.  **Cleaned Scraped Data (Post-HTML Extraction):**
    *   **Component:** `scraper_logic.py` (within `scrape_website`, after `text = extract_text_from_html(html_content)`)
    *   **Action:** For each scraped page, save the `text` (cleaned content) to a new file.
        *   **Location:** e.g., `run_output_dir/scraped_content/cleaned_pages/`
        *   **Filename:** e.g., `{company_name_or_id}__{sanitized_sub_page_url_or_hash}_cleaned.txt`
    *   **Logging:** `main_pipeline.py` (or `scraper_logic.py`) will log the path to this cleaned text file in the main run log.
3.  **Regex Extracted Snippets:**
    *   **Component:** `main_pipeline.py`
    *   **Action:** After aggregating `all_candidate_items_for_llm` (list of `{"number": ..., "snippet": ..., "source_url": ...}` dicts) for a company.
    *   **Location:** e.g., `run_output_dir/intermediate_data/`
    *   **Filename:** e.g., `{company_name}_Row{index}_regex_snippets.json`
    *   **Content:** JSON dump of the `all_candidate_items_for_llm` list.
    *   **Logging:** `main_pipeline.py` will log the path to this JSON file.
4.  **LLM Prompt Input (Full Formatted Prompt):**
    *   **Component:** `llm_extractor_component.py` (within `extract_phone_numbers` method)
    *   **Action:** Before making the API call, save the complete `formatted_prompt` string (which includes the JSON list of candidate items).
    *   **Location:** `llm_context_subdir` (e.g., `run_output_dir/llm_context/`)
    *   **Filename:** e.g., `{company_name}_Row{index}_llm_prompt_input.txt` (using a consistent naming pattern with the LLM raw output).
    *   **Logging:** `main_pipeline.py` (or `llm_extractor_component.py`) will log the path to this file.
5.  **LLM Raw Output:**
    *   **Component:** `llm_extractor_component.py` / `main_pipeline.py`
    *   **Action:** Already saved to `{company_name}_Row{index}_llm_context.json`. This behavior will be maintained.
    *   **Logging:** `main_pipeline.py` already logs the path to this file.

### Phase 2: Adding Specific Log Messages to the Main Log File (`pipeline_run_{run_id}.log`)

These messages will primarily be at the `INFO` level for a standard run overview, with more detailed data logged at `DEBUG` if `LOG_LEVEL` is set accordingly.

1.  **`scraper_logic.py`:**
    *   `INFO`: Start of scraping for a `given_url` and `company_name_or_id`.
    *   `INFO`: URL of each page being fetched (`current_url`).
    *   `INFO`: Path to saved raw HTML content file and cleaned text file for each successfully scraped page.
    *   `INFO`: Summary of scraping results (e.g., "Scraped X pages for {company_name}, details: {list of (saved_file_path, source_url)}").
    *   `DEBUG`: Details of internal links found and queued.
2.  **`regex_extractor_component.py` (`extract_numbers_with_snippets_from_text`):**
    *   `INFO`: Starting extraction for a given `source_url`.
    *   `INFO`: Number of candidate snippets found for the `source_url`.
    *   `DEBUG`: Each extracted `(number, snippet, source_url)` item.
3.  **`llm_extractor_component.py` (`extract_phone_numbers`):**
    *   `INFO`: Number of `candidate_items` received for LLM processing.
    *   `INFO`: Path to the saved full LLM prompt input file.
    *   `INFO`: Number of classified items returned by the LLM.
    *   `DEBUG`: The `candidate_items` list (as JSON string).
    *   `DEBUG`: The list of parsed `PhoneNumberLLMOutput` objects (as list of dicts).
4.  **`main_pipeline.py` (within the row processing loop):**
    *   `INFO`: Start processing for row X, company Y, URL Z.
    *   `INFO`: Path to the aggregated regex snippets JSON file for the company.
    *   `INFO`: Path to the LLM raw output JSON file.
    *   `INFO`: Summary of LLM classification (e.g., "LLM classified: X Best Match, Y Other Relevant, Z Low Value").
    *   `INFO`: Final `VerificationStatus`, `BestMatchedPhoneNumbers`, `OtherRelevantNumbers`, `ConfidenceScore` for the row.
    *   `WARNING`/`ERROR`: For any exceptions or operational failures during the processing of a row.

## 4. Mermaid Diagram (Updated Flow with Logging/Data Dumps)

```mermaid
graph TD
    A[Start: Input Excel] --> B(Load & Preprocess Data);
    B --> C{For Each Company Row};
    C --> D_Config[Read AppConfig: LOG_LEVEL, CONSOLE_LOG_LEVEL etc.];
    D_Config --> LogSetup[Initialize Logging: File & Console Handlers];
    LogSetup --> D[Scrape Website (Multi-Page)];
    D -- List of (RawPageContentFilePath, SourceURL) --> Log1[Log: Scraped Page Paths to Main Log];
    D --> E[Iterate Scraped Pages];
    E --> F{For Each Scraped Page};
    F -- RawPageContent, SourceURL --> F1[Clean HTML to Text];
    F1 -- CleanedText, SourceURL --> F2[Save CleanedText to File (e.g., ..._cleaned.txt)];
    F2 -- CleanedTextFilePath --> Log2[Log: Cleaned Text File Path to Main Log];
    F2 -- CleanedText, SourceURL --> G[Extract Nums & Snippets: regex_extractor.py];
    G -- List of (Num, Snippet, SourceURL) --> H[Collect All Snippets for Company];
    F --> H;
    E --> H;
    H -- AllSnippetsList --> H1[Save AllSnippetsList to JSON File (e.g., ..._regex_snippets.json)];
    H1 --> Log3[Log: Regex Snippets File Path to Main Log];
    H1 -- AllSnippetsList --> I_Prep[Prepare LLM Input Prompt];
    I_Prep -- FullLLMPromptString --> I_SavePrompt[Save LLM Prompt Input to File (e.g., ..._llm_prompt_input.txt)];
    I_SavePrompt --> Log4[Log: LLM Prompt Input File Path to Main Log];
    I_SavePrompt -- FullLLMPromptString --> I[Invoke LLM: llm_extractor.py];
    I -- LLMRawResponse --> I_SaveRaw[Save LLM Raw Response to JSON File (e.g., ..._llm_context.json - existing)];
    I_SaveRaw --> Log5[Log: LLM Raw Response File Path to Main Log];
    I -- LLM Classified Output --> J[Process LLM Results];
    J --> Log6[Log: LLM Classification Summary to Main Log];
    J --> K[Populate DataFrame: BestMatched, OtherRelevant, Status, Confidence];
    K --> Log7[Log: Final Row Decision to Main Log];
    K --> L[Save Output Excel];
    C -.-> L;

    subgraph "Run Output Directory"
        direction LR
        LogFile["pipeline_run_{run_id}.log"]
        subgraph "scraped_content"
            direction LR
            subgraph "individual_pages"
                RawPage1["{comp}__{url1}.txt"]
                RawPage2["{comp}__{url2}.txt"]
            end
            subgraph "cleaned_pages"
                CleanedPage1["{comp}__{url1}_cleaned.txt"]
                CleanedPage2["{comp}__{url2}_cleaned.txt"]
            end
        end
        subgraph "intermediate_data"
            direction LR
            SnippetsFile["{comp}_Row{idx}_regex_snippets.json"]
        end
        subgraph "llm_context"
            direction LR
            LLMPromptFile["{comp}_Row{idx}_llm_prompt_input.txt"]
            LLMOutputFile["{comp}_Row{idx}_llm_context.json"]
        end
        ExcelOutput["final_output_{run_id}.xlsx"]
    end
```

This plan should provide a robust logging framework that meets your requirements for detailed review and debugging.