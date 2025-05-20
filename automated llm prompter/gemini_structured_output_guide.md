# Understanding Gemini Structured Output with Pydantic Models

This document explains the integration of Gemini's structured output feature within our project, utilizing Pydantic models to ensure reliable and type-safe JSON responses from the Language Model (LLM).

## 1. Introduction to Gemini Structured Output

Gemini's structured output feature allows the LLM to generate responses that conform to a predefined schema, typically in JSON format. This is highly beneficial because:

*   **Reliable JSON:** It significantly increases the likelihood of receiving well-formed JSON, reducing parsing errors and making data extraction more robust.
*   **Type Safety:** When combined with schema validation (like Pydantic), it ensures that the data not only has the correct structure but also the correct data types for each field.

In our project, we leverage **Pydantic models** to define these schemas, which is a recommended approach by Google for working with Gemini's structured output.

## 2. How Schemas are Defined

The expected JSON structure for Gemini's output is defined using Pydantic models. These Python classes clearly outline the fields, types, and descriptions for the data you expect the LLM to return.

*   **Schema Definitions File:** All Pydantic models used for structured output are centralized in the new file: [`llm_pipeline/common/pydantic_schemas.py`](llm_pipeline/common/pydantic_schemas.py).

*   **Example Pydantic Model:**
    Here's a simplified example of how models like `PhoneNumberDetail` and `PhoneNumberOutput` might be defined in [`llm_pipeline/common/pydantic_schemas.py`](llm_pipeline/common/pydantic_schemas.py):

    ```python
    from pydantic import BaseModel, Field
    from typing import List, Optional

    class PhoneNumberDetail(BaseModel):
        phone_number: str = Field(description="The extracted phone number.")
        country_code: Optional[str] = Field(default=None, description="The country code, if available.")
        extension: Optional[str] = Field(default=None, description="The extension, if available.")
        notes: Optional[str] = Field(default=None, description="Any relevant notes about the phone number.")

    class PhoneNumberOutput(BaseModel):
        extracted_phone_numbers: List[PhoneNumberDetail] = Field(description="A list of all extracted phone number details.")
        summary: Optional[str] = Field(default=None, description="A brief summary of the extraction process.")
    ```

*   **Fetching Models with [`get_pydantic_model(name: str)`](llm_pipeline/common/pydantic_schemas.py):**
    The [`llm_pipeline/common/pydantic_schemas.py`](llm_pipeline/common/pydantic_schemas.py) file also contains a crucial function: [`get_pydantic_model(name: str)`](llm_pipeline/common/pydantic_schemas.py). This function acts as a registry or lookup, allowing other parts of the system to dynamically fetch a specific Pydantic model class by its string name (e.g., `"PhoneNumberOutput"`). This is achieved by looking up the name in a dictionary (e.g., `_PYDANTIC_MODELS`) that maps names to their corresponding Pydantic classes.

## 3. System Integration - How it Works

The integration of Pydantic schemas for structured output involves changes in both the LLM configuration and the client logic.

### Configuration

LLM profiles defined in [`llm_pipeline/config.py`](llm_pipeline/config.py) now support an optional `pydantic_schema_name` key specifically for Gemini models. This key tells the system which Pydantic model to use for structuring the output.

*   **Example `gemini_phone_json` Profile:**
    ```python
    # In llm_pipeline/config.py
    LLM_PROFILES = {
        # ... other profiles ...
        "gemini_phone_json": {
            "client_type": "gemini",
            "model_name": "gemini-1.5-flash-latest", # Or your preferred Gemini model
            "pydantic_schema_name": "PhoneNumberOutput", # Specifies the Pydantic model to use
            "generation_config": {
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 10,
                "max_output_tokens": 2048,
                "response_mime_type": "application/json" # Crucial for Gemini to know JSON is expected
            },
            "safety_settings": {
                "HARASSMENT": "BLOCK_NONE",
                "HATE_SPEECH": "BLOCK_NONE",
                "SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "DANGEROUS_CONTENT": "BLOCK_NONE"
            },
            "prompt_file": "prompts/gemini_phone_extraction_v3.txt" # Prompt should guide towards the schema
        },
        # ... other profiles ...
    }
    ```

### Client Logic ([`GeminiAPIClient`](llm_pipeline/clients/gemini_client.py))

The [`GeminiAPIClient`](llm_pipeline/clients/gemini_client.py) handles the interaction with the Gemini API, incorporating the Pydantic schema as follows:

1.  **Retrieve Schema Name:** When a profile with a `pydantic_schema_name` is used, the client extracts this name.
2.  **Fetch Pydantic Model:** It calls [`get_pydantic_model()`](llm_pipeline/common/pydantic_schemas.py) from [`llm_pipeline/common/pydantic_schemas.py`](llm_pipeline/common/pydantic_schemas.py) to obtain the actual Pydantic model class corresponding to the retrieved name.
3.  **Pass Schema to API:** The fetched Pydantic model class is then passed to the Gemini API within the `GenerationConfig` object, specifically under the `response_schema` parameter. This instructs Gemini to structure its output according to this model.
    ```python
    # Simplified logic in GeminiAPIClient
    # generation_config_dict = self.profile.get("generation_config", {})
    # pydantic_schema_name = self.profile.get("pydantic_schema_name")
    # if pydantic_schema_name:
    #     pydantic_model_class = get_pydantic_model(pydantic_schema_name)
    #     generation_config_dict["response_schema"] = pydantic_model_class
    #     generation_config_dict["response_mime_type"] = "application/json" # Ensure this is set
    #
    # generation_config = GenerationConfig(**generation_config_dict)
    # response = self.model.generate_content(..., generation_config=generation_config)
    ```
4.  **Parse Response:** The client first attempts to use `response.candidates[0].content.parts[0].function_call` or `response.text` (if `response_mime_type` is `application/json` and schema is provided, Gemini often populates `response.text` with the JSON string). If a Pydantic model was provided via `response_schema`, Google's SDK may also provide a `response.candidates[0].content.parts[0].parsed` attribute which directly gives the parsed Pydantic object. If direct parsing fails or is not available, it falls back to manually parsing the `response.text` as JSON and then validating/instantiating the Pydantic model.

## 4. How to Set Up and Use a New Schema

To use a new custom schema for structured output with Gemini, follow these steps:

### Step 1: Define Your Pydantic Model

1.  Open [`llm_pipeline/common/pydantic_schemas.py`](llm_pipeline/common/pydantic_schemas.py).
2.  Define your new Pydantic class, inheriting from `pydantic.BaseModel`. Use `Field` for descriptions and validation if needed.
    ```python
    # In llm_pipeline/common/pydantic_schemas.py
    from pydantic import BaseModel, Field
    from typing import List, Optional # etc.

    class MyCustomData(BaseModel):
        item_id: int = Field(description="A unique identifier for the item.")
        item_name: str = Field(description="The name of the item.")
        is_available: bool = Field(default=True, description="Availability status.")
        tags: Optional[List[str]] = Field(default=None, description="Associated tags.")
    ```
3.  Register your new model in the `_PYDANTIC_MODELS` dictionary (or the equivalent registration mechanism in the file) so that [`get_pydantic_model()`](llm_pipeline/common/pydantic_schemas.py) can find it.
    ```python
    # In llm_pipeline/common/pydantic_schemas.py
    # ... (other model definitions) ...

    _PYDANTIC_MODELS = {
        "PhoneNumberOutput": PhoneNumberOutput,
        "PhoneNumberDetail": PhoneNumberDetail,
        "MyCustomData": MyCustomData,  # Add your new model here
        # ... other existing models
    }

    def get_pydantic_model(name: str) -> Type[BaseModel]:
        # ... (implementation) ...
    ```

### Step 2: Configure an LLM Profile

1.  Open [`llm_pipeline/config.py`](llm_pipeline/config.py).
2.  Create a new LLM profile for Gemini or modify an existing one.
3.  Add the `pydantic_schema_name` key to this profile, setting its value to the string name of your newly defined Pydantic model (e.g., `"MyCustomData"`).
4.  Ensure `response_mime_type` in `generation_config` is set to `"application/json"`.

    ```python
    # In llm_pipeline/config.py
    LLM_PROFILES = {
        # ... other profiles ...
        "gemini_custom_data_extractor": {
            "client_type": "gemini",
            "model_name": "gemini-1.5-pro-latest", # Or flash, etc.
            "pydantic_schema_name": "MyCustomData", # Name of your Pydantic model
            "generation_config": {
                "temperature": 0.3,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json" # Essential for structured output
            },
            "safety_settings": { /* ... */ },
            "prompt_file": "prompts/my_custom_data_extraction_prompt.txt" # Create a suitable prompt
        },
        # ...
    }
    ```

### Step 3: Adjust Your Prompt (Best Practice)

When using `response_schema` with Gemini, the model is already constrained to output data according to your Pydantic model. Therefore:

*   **Avoid Redundant Instructions:** Your prompt should ideally *not* contain explicit instructions to format the output as JSON, or specify the JSON keys and structure (e.g., "Return a JSON object with keys 'item_id', 'item_name'..."). The `response_schema` handles this.
*   **Focus on Content:** Instead, focus your prompt on clearly describing the information you want the LLM to extract or generate, guiding it towards fulfilling the fields defined in your Pydantic model. For example, if your schema expects an `item_name`, your prompt might say "Extract the name of the product mentioned in the text."

### Step 4: Run the Pipeline

You can now run the main pipeline script, [`llm_pipeline/main.py`](llm_pipeline/main.py), specifying your newly configured LLM profile using the `--llm-profile` argument.

Example command:
```bash
python llm_pipeline/main.py --llm-profile gemini_custom_data_extractor --input-file path/to/your/input.txt --output-dir path/to/your/output_dir
```

The pipeline will then use your Pydantic schema to request structured output from Gemini, and the results will be parsed and validated accordingly.