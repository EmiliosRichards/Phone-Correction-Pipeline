# Enhanced Extraction Workflow: Features and Usage Guide

This document provides a summary of the newly added features to the phone extraction pipeline, as per GitHub Issue #3, and offers guidance on how to set up and use them.

## 1. Overview of New Features

The recent enhancements focus on enriching the extracted data, providing more contextual information, and improving the LLM's understanding through prompt profiling and homepage summarization.

### a. Enriched Data Extraction

*   **`additional_info` Field:** A significant addition is the `additional_info` field in the extraction output. This field is designed to capture supplementary contact details found alongside or contextually related to phone numbers.
    *   **Captured Data:** Includes email addresses, names of individuals, job titles, departments, or other relevant notes.
    *   **Schema:** This is part of the `EnrichedExtractionOutput` Pydantic schema located in [`src/core/schemas.py`](src/core/schemas.py:1). The `additional_info` field typically holds a list of `AdditionalInformation` objects, each detailing the type of information, its value, and context.

### b. Prompt Profiles

To cater to different extraction needs and complexities, the system now supports prompt profiles:

*   **Profile 1 (Minimal):**
    *   **Purpose:** Handles basic phone number extraction with minimal enrichment, reflecting the previous default behavior.
    *   **Prompt File (Convention):** It's recommended to use or create `prompts/profile_1.txt` for this profile.
    *   **Output Schema:** Uses the `MinimalExtractionOutput` Pydantic schema ([`src/core/schemas.py`](src/core/schemas.py:1)).
*   **Profile 2 (Enriched):**
    *   **Purpose:** Performs comprehensive extraction, including phone numbers and the `additional_info` discussed above. It also incorporates a website summary for better context.
    *   **Prompt File:** Uses [`prompts/profile_2.txt`](prompts/profile_2.txt:1).
    *   **Output Schema:** Uses the `EnrichedExtractionOutput` Pydantic schema ([`src/core/schemas.py`](src/core/schemas.py:1)).

### c. Homepage Summarization for Context Injection

*   **Purpose:** To provide the LLM with a better understanding of the business or service offered by a website before attempting to classify or extract contact information.
*   **Workflow:**
    1.  The content of the target website's homepage is processed.
    2.  This content is fed to an LLM using the summarization prompt found in [`prompts/summarization_prompt.txt`](prompts/summarization_prompt.txt:1).
    3.  The LLM generates a short, neutral summary (2-3 sentences) of the website (referred to as `website_summary`).
    4.  This `website_summary` is then injected at the beginning of the Profile 2 prompt ([`prompts/profile_2.txt`](prompts/profile_2.txt:1)) before it's sent to the LLM for the main extraction task.
*   **Benefit:** This contextual priming helps the LLM make more accurate inferences, especially when classifying numbers or disambiguating information based on industry or service type.

## 2. Setup and Configuration

### a. Pydantic Schemas

*   The necessary Pydantic models (`MinimalExtractionOutput`, `EnrichedExtractionOutput`, `AdditionalInformation`, etc.) are defined in [`src/core/schemas.py`](src/core/schemas.py:1).
*   Your application logic will need to import these schemas to validate LLM outputs and structure the data.
    ```python
    # This is a conceptual example of how you might import the schemas
    # from src.core.schemas import EnrichedExtractionOutput, MinimalExtractionOutput 
    ```

### b. Prompt Files

*   Ensure the following prompt files are correctly placed in your `prompts/` directory:
    *   [`prompts/summarization_prompt.txt`](prompts/summarization_prompt.txt:1)
    *   [`prompts/profile_2.txt`](prompts/profile_2.txt:1)
    *   For Profile 1, create or designate `prompts/profile_1.txt` containing your existing minimal extraction prompt.

### c. Configuration for Profile Switching (Conceptual)

The mechanism for selecting a profile (e.g., Profile 1 vs. Profile 2) needs to be implemented in your main application pipeline. The GitHub issue suggests options like:

*   **`config.yaml`:**
    ```yaml
    # In your config.yaml (example configuration)
    extraction_profile: "profile_2" # or "profile_1"
    ```
*   **CLI Flags:**
    ```bash
    # Example command-line usage
    python main_pipeline.py --profile profile_2
    ```
*   **Environment Variables.**

Your application will need to read this configuration and dynamically load the appropriate prompt file and expect the corresponding Pydantic schema for output validation.

## 3. Using the New Features (Workflow Example for Profile 2)

This outlines the conceptual flow when using the enriched Profile 2.

### Step 1: Homepage Summarization

*   **Action:** Fetch the HTML content of the target website's homepage.
*   **Process:**
    *   Load the summarization prompt from [`prompts/summarization_prompt.txt`](prompts/summarization_prompt.txt:1).
    *   Send the homepage content and the prompt to the LLM.
    *   Receive the `website_summary` from the LLM.
*   **Conceptual Python Code:**
    ```python
    # Conceptual Python code for homepage summarization
    # Assume you have functions like:
    # - fetch_website_homepage(url_string) -> str (returns HTML content)
    # - load_text_file(file_path_string) -> str (returns file content)
    # - llm_service_generate(prompt_string, input_text_string) -> str (returns LLM response)

    # target_url = "http://example.com"
    # homepage_html_content = fetch_website_homepage(target_url) 
    
    # summarization_prompt_template = load_text_file("prompts/summarization_prompt.txt")
    # # Assuming summarization_prompt.txt contains "[Paste Website Content Here]"
    # summarization_prompt_filled = summarization_prompt_template.replace("[Paste Website Content Here]", homepage_html_content)
    
    # website_summary = llm_service_generate(prompt=summarization_prompt_filled, input_text_string=homepage_html_content) 
    # print(f"Website Summary: {website_summary}")
    ```

### Step 2: Enriched Data Extraction

*   **Action:** Process a specific text snippet (e.g., from a contact page or footer) using the enriched prompt.
*   **Process:**
    *   Load the Profile 2 prompt template from [`prompts/profile_2.txt`](prompts/profile_2.txt:1).
    *   Inject the `website_summary` (obtained in Step 1) into this template.
    *   Send the combined prompt and the target text snippet to the LLM.
    *   The LLM should return data. It's highly recommended to instruct the LLM in the prompt to return a JSON string that directly maps to the `EnrichedExtractionOutput` schema.
*   **Conceptual Python Code:**
    ```python
    # Conceptual Python code for enriched data extraction
    # from src.core.schemas import EnrichedExtractionOutput # Ensure this is imported

    # text_snippet_to_analyze = "Some text from a webpage containing contact details..." 
    # enriched_prompt_template = load_text_file("prompts/profile_2.txt")

    # # Inject the summary and the text snippet into the Profile 2 prompt
    # # Assuming profile_2.txt has placeholders like "[Insert Website Summary Here]"
    # # and "[Insert Text Snippet for Extraction Here]"
    # final_enriched_prompt = enriched_prompt_template.replace("[Insert Website Summary Here]", website_summary)
    # final_enriched_prompt = final_enriched_prompt.replace("[Insert Text Snippet for Extraction Here]", text_snippet_to_analyze)

    # # Assuming your LLM service can be instructed to return JSON
    # llm_response_json_str = llm_service_generate(prompt=final_enriched_prompt, input_text_string=text_snippet_to_analyze) 

    # try:
    #     # Validate the JSON string against the Pydantic model
    #     validated_data = EnrichedExtractionOutput.model_validate_json(llm_response_json_str)
    #     print("Successfully extracted and validated data using Profile 2.")
    #     # You can now access validated_data.extracted_numbers, validated_data.additional_info etc.
    #     # For example: print(validated_data.model_dump_json(indent=2))
    # except Exception as e: # Catch Pydantic's ValidationError or JSONDecodeError
    #     print(f"Error validating LLM output for Profile 2: {e}")
    ```

### Step 3: Utilizing the Output

*   Once the data is validated into an `EnrichedExtractionOutput` object (`validated_data` in the example above), you can access its fields:
    *   `validated_data.extracted_numbers`
    *   `validated_data.additional_info` (list of `AdditionalInformation` objects)
    *   `validated_data.homepage_summary`
    *   Other fields like `overall_confidence`, `processing_notes`, etc.

## 4. Important Considerations

*   **LLM Integration:** The core logic for making LLM calls, handling API keys, managing request/response cycles, and parsing LLM outputs (ideally structured as JSON) is a crucial part of your application that needs to be robust.
*   **Error Handling:** Implement comprehensive error handling for network issues, LLM API errors, data validation failures (Pydantic's `ValidationError`), JSON decoding issues, and file I/O.
*   **Profile 1 Usage:** If using Profile 1 (minimal), the workflow simplifies:
    1.  Load prompt from `prompts/profile_1.txt` (once created/named).
    2.  Send to LLM with the text snippet.
    3.  Validate output against `MinimalExtractionOutput`. (No summarization step needed).
*   **Iterative Prompt Refinement:** Prompts are rarely perfect on the first try. Be prepared to test and refine the contents of [`prompts/summarization_prompt.txt`](prompts/summarization_prompt.txt:1) and [`prompts/profile_2.txt`](prompts/profile_2.txt:1) based on the LLM's performance and the quality of the extracted data.
*   **Cost and Latency:** The enriched workflow (Profile 2) involves an additional LLM call for summarization, which will add to the cost and latency of processing each item. Consider this trade-off based on the value of the enriched data.

This guide should help you integrate and utilize the new features effectively. Remember that the conceptual code snippets will need to be adapted into your existing pipeline's structure and utilities.