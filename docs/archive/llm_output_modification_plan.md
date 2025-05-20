# Plan: Modify LLM to Return Text Output (Attempting JSON Parsing)

This document outlines the plan to modify the LLM interaction within the `phone_validation_pipeline` project. The primary goal is to have the LLM return its output as plain text, while the prompt will still instruct it to format this text as JSON. The system will then attempt to parse this text as JSON and validate it against existing Pydantic schemas.

## Current Approach Summary

*   **Prompting:** A standard text prompt (from `phone_validation_pipeline/prompts/gemini_phone_validation_v1.txt`) is used. This prompt instructs the LLM on its task and asks for the output to be formatted as a JSON object.
*   **API Call:** The `GeminiLLMExtractor` in `phone_validation_pipeline/src/llm_extractor_component.py` currently uses `response_schema=LLMExtractionResult` and `response_mime_type="application/json"` in its `GenerationConfig`. This forces the Gemini API to return a well-formed JSON object conforming to the `LLMExtractionResult` Pydantic schema.
*   **Response Handling:** The received JSON is directly validated using Pydantic models (`LLMExtractionResult` and `PhoneNumberLLMOutput`).

## Desired Changes

The user wants to remove the API-level enforcement of JSON output. Instead:
1.  The LLM will be configured to return plain text.
2.  The existing prompt, which asks the LLM to format its output as JSON, will be retained.
3.  The application code will attempt to parse the LLM's raw text output as JSON.
4.  If parsing is successful, the resulting JSON structure will be validated against the existing Pydantic schemas.

## Detailed Plan

### Phase 1: Modify LLM API Call Configuration

*   **Objective:** Change the Gemini API call to stop requesting API-enforced structured JSON and instead receive plain text.
*   **File to Modify:** `phone_validation_pipeline/src/llm_extractor_component.py`
*   **Specific Changes in the `extract_phone_numbers` method:**
    1.  Locate the `GenerationConfig` instantiation (around line 178).
    2.  Remove the line: `response_schema=LLMExtractionResult`
    3.  Remove the line: `response_mime_type="application/json"`

### Phase 2: Adapt LLM Response Handling and Parsing

*   **Objective:** Modify the response handling logic to attempt parsing the LLM's raw text output (which is expected to be JSON-formatted based on the prompt) and then validate it using the existing Pydantic schemas.
*   **File to Modify:** `phone_validation_pipeline/src/llm_extractor_component.py`
*   **Specific Changes in the `extract_phone_numbers` method (around lines 224-252):**
    1.  The variable `raw_llm_response_str` (which is `response.text`) will contain the LLM's text output.
    2.  The existing logic that attempts `json.loads(raw_llm_response_str)` and then validates with `LLMExtractionResult(**parsed_json_object)` will be largely retained.
    3.  **Enhancement (Potential):** Consider adding pre-processing steps to `raw_llm_response_str` before `json.loads()`. This could involve stripping common non-JSON artifacts like leading/trailing whitespace, or markdown code fences (e.g., \`\`\`json ... \`\`\`) if the LLM tends to wrap its JSON output.
    4.  The error handling for `json.JSONDecodeError` and `PydanticValidationError` will remain crucial, as the LLM's text-based JSON might be less reliable than API-enforced JSON.

### Phase 3: Testing and Refinement

*   **Objective:** Thoroughly test the new implementation to ensure it correctly parses various LLM text outputs and handles potential errors gracefully.
*   **Actions:**
    1.  Test with a variety of inputs to observe how consistently the LLM produces parsable JSON-formatted text when requested via the prompt.
    2.  Based on observations, refine the parsing logic in Phase 2, particularly any pre-processing steps, to improve robustness.
    3.  Ensure comprehensive error logging for cases where parsing or validation fails.

## Mermaid Diagram of the Plan

\`\`\`mermaid
graph TD
    A[Start: User wants LLM to return text, prompt asks for JSON] --> B(Phase 1: Modify API Call);
    B --> B1[In \`llm_extractor_component.py\`];
    B1 --> B2[Remove \`response_schema\` from \`GenerationConfig\`];
    B2 --> B3[Remove \`response_mime_type="application/json"\`];
    B3 --> C(Phase 2: Adapt LLM Response Handling);
    C --> C1[In \`llm_extractor_component.py\`];
    C1 --> C2[LLM output (\`response.text\`) is raw text (expected to be JSON-like)];
    C2 --> C2a[Optional: Pre-process \`response.text\` to clean up potential non-JSON artifacts];
    C2a --> C3[Attempt \`json.loads()\` on (pre-processed) \`response.text\`];
    C3 --> C4[If successful, validate with Pydantic \`LLMExtractionResult\`];
    C3 -- Parsing Fails --> C5[Handle \`json.JSONDecodeError\` / malformed JSON];
    C4 -- Validation Fails --> C6[Handle \`PydanticValidationError\`];
    C4 --> C7[Convert to \`List[PhoneNumberLLMOutput]\`];
    C7 --> E(Phase 3: Testing & Refinement);
    C5 --> E;
    C6 --> E;
    E --> F[Iterate on Parsing Logic (esp. pre-processing) & Error Handling];
    F --> G[End: System uses LLM's text output, attempts to parse as JSON];
\`\`\`