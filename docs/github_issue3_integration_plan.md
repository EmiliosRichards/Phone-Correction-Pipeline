# GitHub Issue: Integrate Enhanced Extraction Workflow (Issue #3 Follow-up)

## Background

Following the completion of drafting tasks in Issue #3 ("Enhance Extraction Workflow with Metadata Enrichment and Homepage Summarization"), we now have the foundational components for an improved extraction pipeline:

*   **Updated Pydantic Schemas:** `MinimalExtractionOutput` and `EnrichedExtractionOutput` (with `AdditionalInformation`) defined in [`src/core/schemas.py`](src/core/schemas.py:1).
*   **Summarization Prompt:** [`prompts/summarization_prompt.txt`](prompts/summarization_prompt.txt:1) for generating website summaries.
*   **Enriched Extraction Prompt (Profile 2):** [`prompts/profile_2.txt`](prompts/profile_2.txt:1) designed to use the website summary and extract detailed contact information.
*   **Guidance Document:** [`docs/enhanced_extraction_workflow_guide.md`](docs/enhanced_extraction_workflow_guide.md) outlining these features.

This issue outlines the necessary implementation tasks to fully integrate these components into the main phone extraction pipeline.

## Objective

To implement the end-to-end logic required to utilize the new Pydantic schemas and prompt profiles, including homepage summarization, within the existing `Phone-Correction-Pipeline` project. This involves modifying the main application flow to support these enhancements.

## Key Implementation Tasks

1.  **Homepage Content Fetching Mechanism:**
    *   Implement robust logic to fetch the HTML content of a given website's homepage.
    *   Consider error handling for network issues, timeouts, and invalid URLs.

2.  **LLM Service Integration for Summarization (Profile 2):**
    *   Develop or adapt an LLM service module to:
        *   Take homepage HTML content as input.
        *   Utilize the [`prompts/summarization_prompt.txt`](prompts/summarization_prompt.txt:1).
        *   Call the LLM to generate the `website_summary`.
        *   Parse and store this summary effectively.

3.  **Profile Switching and Configuration Logic:**
    *   Implement a system for selecting the active extraction profile (e.g., "profile\_1" for minimal, "profile\_2" for enriched).
    *   This could be driven by:
        *   A `config.yaml` setting.
        *   Command-line arguments (e.g., `python main_pipeline.py --profile enriched`).
        *   Environment variables.
    *   The system must dynamically load the correct prompt file based on the selected profile.

4.  **LLM Service Integration for Main Extraction:**
    *   Extend the LLM service module to:
        *   Accept the target text snippet for extraction.
        *   For Profile 2:
            *   Accept the `website_summary` generated in step 2.
            *   Inject both the summary and the text snippet into the [`prompts/profile_2.txt`](prompts/profile_2.txt:1) template.
        *   For Profile 1:
            *   Use [`prompts/profile_1.txt`](prompts/profile_1.txt) (this prompt needs to be formally created or an existing one designated if not already done, based on current minimal extraction logic).
        *   Instruct the LLM to return its output in a structured JSON format corresponding to the active profile's Pydantic schema.

5.  **Output Validation and Processing:**
    *   Implement logic to parse the JSON response from the LLM.
    *   Validate the parsed data against the appropriate Pydantic schema:
        *   `MinimalExtractionOutput` for Profile 1.
        *   `EnrichedExtractionOutput` for Profile 2.
    *   Handle validation errors gracefully.
    *   Integrate the validated data into the downstream processes of the pipeline (e.g., reporting, database storage).

6.  **Formalize `profile_1.txt`:**
    *   If not already explicitly created, define `prompts/profile_1.txt`. This prompt should reflect the current/previous minimal phone number extraction logic and its output should align with the `MinimalExtractionOutput` schema.

7.  **Comprehensive Error Handling and Logging:**
    *   Implement robust error handling for all new components and integration points (LLM calls, file I/O, data parsing, validation).
    *   Enhance logging to provide clear insights into the new workflow steps, including profile selection, summarization results, and extraction outcomes.

## Design and Architectural Considerations

Integrating these new features is not merely about adding new scripts; it requires careful consideration of the existing application architecture (`main_pipeline.py` and related modules).

*   **Modularity:** Evaluate how to best structure the new functionalities. Consider dedicated modules for:
    *   Website content fetching.
    *   LLM interaction (potentially a more generic service that can handle different prompts and expected output structures).
    *   Prompt management and templating.
    *   Configuration management for profiles.
*   **Data Flow:** Clearly map out the data flow for the enriched profile: URL -> Homepage HTML -> Summarization Prompt -> LLM -> Website Summary -> Enriched Prompt (with snippet) -> LLM -> JSON Output -> Pydantic Validation -> Processed Data.
*   **Modification of Existing Code:** Be prepared for necessary modifications to `main_pipeline.py` and other core components to accommodate the new workflow paths, configuration, and data structures.
*   **Configuration Management:** How will settings related to LLM (API keys, model choices) and the new features be managed? Ensure consistency with existing configuration practices.
*   **Testing Strategy:** Define a testing strategy that covers unit tests for new modules and integration tests for the end-to-end workflows of both Profile 1 and Profile 2.

## Potential Challenges

*   **LLM Reliability:** Ensuring consistent and accurate generation of both website summaries and structured JSON for extraction. This may require iterative prompt tuning.
*   **Performance:** The Profile 2 workflow introduces an additional LLM call for summarization, which will impact overall processing time and cost per item. This trade-off needs to be acceptable.
*   **Complexity:** Managing multiple prompt versions, corresponding Pydantic schemas, and conditional logic for different profiles adds complexity to the codebase.

## Next Steps

1.  **Team Discussion:** Review this integration plan, particularly the design and architectural considerations.
2.  **Detailed Design:** Create a more detailed technical design for the new modules and modifications to existing ones.
3.  **Task Breakdown:** Break down the implementation tasks into smaller, manageable sub-tasks or user stories.
4.  **Prioritization:** Prioritize implementation based on project needs.
5.  **Iterative Development and Testing:** Implement features iteratively with thorough testing at each stage.

This integration will significantly enhance the capabilities of the Phone Correction Pipeline, providing richer data and more context-aware extractions. Collaboration on design and careful implementation will be key to success.