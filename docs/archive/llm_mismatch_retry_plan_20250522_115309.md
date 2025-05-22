# Plan: LLM Number Mismatch Handling with Prompt Refinement and Configurable Retry

This document outlines the plan to address occasional mismatches where the LLM alters an input number instead of returning it exactly as provided. The solution involves refining the LLM prompt and implementing a configurable, targeted retry mechanism.

## Phase 1: LLM Prompt Refinement

*   **File to Modify**: `prompts/gemini_phone_validation_v1.txt`
*   **Objective**: Make the instructions for returning the candidate number even more explicit to minimize the chance of the LLM altering it.
*   **Proposed Changes**:
    1.  **Modify Line 24** (under "EVERY item in the "extracted_numbers" list MUST be an object containing exactly three fields:"):
        *   **Current**: `1. "number": The original E.164 formatted candidate_number.`
        *   **Proposed**: `1. "number": This MUST be the exact, unmodified 'number' string that was provided to you in the corresponding input candidate object. Do not alter it in any way.`
    2.  **Modify Line 71**:
        *   **Current**: `For EVERY candidate number provided in the input list, you MUST include a corresponding entry in the 'extracted_numbers' list. Assign a 'type' and 'classification' to each.`
        *   **Proposed**: `For EVERY candidate number provided in the input list, you MUST include a corresponding entry in the 'extracted_numbers' list, **in the SAME order as the input**. The 'number' field in your output for each item MUST be identical to the 'number' field from the corresponding input candidate. Assign a 'type' and 'classification' to each.`

## Phase 2: Implement Configurable Targeted Retry Logic in `GeminiLLMExtractor`

*   **File to Modify**: `src/llm_extractor_component.py`
*   **Method to Modify**: `extract_phone_numbers`
*   **Core Logic**:
    1.  Perform the initial LLM call.
    2.  Identify mismatched numbers by comparing LLM output numbers against the original input numbers, assuming the LLM maintains the order of items.
    3.  If mismatches exist and the configured number of retries is greater than 0:
        *   Iteratively retry *only* the still-mismatched items up to the configured maximum number of attempts (defaulting to 1).
        *   If a number is corrected during a retry, it's removed from the set of items needing further retries.
    4.  If mismatches persist after all retries (or if retries are disabled), create a default/error-flagged `PhoneNumberLLMOutput` object for those candidates, using the original input number.
    5.  Combine all successfully processed and error-flagged results.

*   **Detailed Steps within `extract_phone_numbers`**:
    1.  **Add Configuration**:
        *   In `src/core/config.py` (`AppConfig` class), add:
            ```python
            self.llm_max_retries_on_number_mismatch: int = int(os.getenv('LLM_MAX_RETRIES_ON_NUMBER_MISMATCH', '1'))
            ```
        *   Add `LLM_MAX_RETRIES_ON_NUMBER_MISMATCH=1` to `.env.example`.
    2.  **Initial LLM Call**: Perform the LLM call as currently implemented to get `validated_numbers_pass1`.
    3.  **Mismatch Detection and Segregation (after first pass)**:
        *   Initialize `final_processed_outputs: List[PhoneNumberLLMOutput] = [None] * len(candidate_items)`.
        *   Initialize `items_needing_retry: List[Tuple[int, Dict[str, Any]]] = []` (to store `original_index`, `input_item`).
        *   **Crucial Assumption**: `len(validated_numbers_pass1) == len(candidate_items)`. If not, log a severe error as the LLM didn't follow a key instruction, and the retry logic might be compromised.
        *   Loop `i` from `0` to `len(candidate_items) - 1`:
            *   `input_item = candidate_items[i]`
            *   `llm_output_item = validated_numbers_pass1[i]`
            *   If `llm_output_item.number == input_item['number']`:
                *   Enrich `llm_output_item` (source_url, company name), normalize its number, and store it in `final_processed_outputs[i]`.
            *   Else (mismatch):
                *   Log the initial mismatch (e.g., "Initial mismatch for input 'number': {input_item['number']}, LLM returned: {llm_output_item.number}").
                *   Add `(i, input_item)` to `items_needing_retry`.
    4.  **Iterative Retry Loop**:
        *   `current_retry_attempt = 0`
        *   While `items_needing_retry` is not empty AND `current_retry_attempt < self.config.llm_max_retries_on_number_mismatch`:
            *   `current_retry_attempt += 1`
            *   Log: "Attempting LLM retry pass #{current_retry_attempt} for {len(items_needing_retry)} mismatched items."
            *   Extract `inputs_for_this_retry_pass` (list of dicts) and `original_indices_for_this_pass` (list of ints) from `items_needing_retry`.
            *   Perform a new LLM call using `inputs_for_this_retry_pass`. Let the result be `validated_numbers_current_retry`.
            *   **Assumption for Retry**: `len(validated_numbers_current_retry) == len(inputs_for_this_retry_pass)`. Log error if not.
            *   Initialize `still_mismatched_after_this_retry: List[Tuple[int, Dict[str, Any]]] = []`.
            *   Loop `j` from `0` to `len(inputs_for_this_retry_pass) - 1`:
                *   `original_input_index = original_indices_for_this_pass[j]`
                *   `retried_input_item = inputs_for_this_retry_pass[j]`
                *   `retried_llm_output = validated_numbers_current_retry[j]`
                *   If `retried_llm_output.number == retried_input_item['number']`:
                    *   Log: "Retry pass #{current_retry_attempt} successful for input 'number': {retried_input_item['number']}".
                    *   Enrich, normalize `retried_llm_output`, and store in `final_processed_outputs[original_input_index]`.
                *   Else (still mismatched in this retry pass):
                    *   Log: "Mismatch persists after retry pass #{current_retry_attempt} for input 'number': {retried_input_item['number']}, LLM returned: {retried_llm_output.number}".
                    *   Add `(original_input_index, retried_input_item)` to `still_mismatched_after_this_retry`.
            *   `items_needing_retry = still_mismatched_after_this_retry`.
    5.  **Handle Persistently Mismatched Items**:
        *   If `items_needing_retry` is still not empty after all retry attempts:
            *   For each `(original_index, input_item)` in `items_needing_retry`:
                *   Log: "Persistent mismatch after all {self.config.llm_max_retries_on_number_mismatch} retries for input 'number': {input_item['number']}".
                *   Create an error-flagged `PhoneNumberLLMOutput` (using `input_item['number']`, type "Error_PersistentMismatch", classification "Non-Business", etc.) and store in `final_processed_outputs[original_index]`.
    6.  **Handle Initial Mismatches if Retries Disabled/Skipped**:
        *   If `self.config.llm_max_retries_on_number_mismatch == 0` and there were initial mismatches (or if any `final_processed_outputs[i]` is still `None` for an item that was initially mismatched but not retried):
            *   For each such `(original_index, input_item)`:
                *   Log: "Mismatch occurred, retries disabled/skipped for input 'number': {input_item['number']}".
                *   Create and store an error-flagged `PhoneNumberLLMOutput` in `final_processed_outputs[original_index]`.
    7.  **Return Value**: The `extracted_numbers` list will be `final_processed_outputs`. Ensure all `None` placeholders have been appropriately filled.

## Visual Flow (Mermaid Diagram)

```mermaid
graph TD
    A[Start extract_phone_numbers] --> B{Load AppConfig (incl. llm_max_retries_on_number_mismatch)};
    B --> C[Initial LLM Call with all candidate_items];
    C --> D[Parse LLM Response (validated_numbers_pass1)];
    D --> E{Iterate validated_numbers_pass1 vs candidate_items (assuming order & same length)};
    E -- For each item --> F{llm_output_item.number == input_item.number?};
    F -- Yes --> G[Enrich/Normalize llm_output_item, Store in final_processed_outputs[original_index]];
    G --> E;
    F -- No --> H[Log Initial Mismatch, Add (original_index, input_item) to items_needing_retry];
    H --> E;
    E -- Loop Done --> I{items_needing_retry not empty AND config.llm_max_retries > 0?};
    I -- Yes --> J_RetryLoop[Initialize current_retry_attempt = 0];
    J_RetryLoop --> K_CheckRetryLoop{current_retry_attempt < config.llm_max_retries AND items_needing_retry not empty?};
    K_CheckRetryLoop -- Yes --> L_DoRetry[Increment current_retry_attempt, Prepare inputs_for_this_retry_pass];
    L_DoRetry --> M_RetryCall[Retry LLM Call with inputs_for_this_retry_pass];
    M_RetryCall --> N_ParseRetry[Parse Retry Response (validated_numbers_current_retry)];
    N_ParseRetry --> O_IterateRetry{Iterate validated_numbers_current_retry vs retried_input_item};
    O_IterateRetry -- For each retried item --> P_CheckMatchRetry{retried_llm_output.number == retried_input_item.number?};
    P_CheckMatchRetry -- Yes --> Q_RetrySuccess[Log Success, Enrich/Normalize, Store in final_processed_outputs[original_index]];
    Q_RetrySuccess --> O_IterateRetry;
    P_CheckMatchRetry -- No --> R_RetryMismatch[Log Mismatch, Add (original_index, input_item) to still_mismatched_after_this_retry];
    R_RetryMismatch --> O_IterateRetry;
    O_IterateRetry -- Loop Done --> S_UpdateRetryList[items_needing_retry = still_mismatched_after_this_retry];
    S_UpdateRetryList --> K_CheckRetryLoop;
    K_CheckRetryLoop -- No --> T_HandlePersistent[Handle any remaining items in items_needing_retry: Create/Store Error-Flagged Output];
    I -- No --> U_HandleNoRetry[If initial mismatches and retries were 0 (or items in final_processed_outputs still None): Create/Store Error-Flagged Output for them];
    T_HandlePersistent --> V_EndLogic[Finalize];
    U_HandleNoRetry --> V_EndLogic;
    V_EndLogic --> W[Return final_processed_outputs, raw_response, token_stats];
```

## Summary of Benefits:
*   Addresses the rare mismatch issue effectively.
*   Minimizes unnecessary LLM calls by retrying only problematic items.
*   Allows configuration of retry attempts.
*   Improves data quality by attempting to correct errors or clearly flagging them.
*   Prompt refinement acts as a preventative measure.