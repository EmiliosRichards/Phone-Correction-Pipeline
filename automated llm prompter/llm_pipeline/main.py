import argparse
import datetime
import json
import logging
import pathlib
import time

from llm_pipeline import config
from llm_pipeline.common import io_utils
from llm_pipeline.common import log as custom_log # Renamed to avoid conflict with standard logging
from llm_pipeline.common.metrics import MetricsLogger, RunMetrics
from llm_pipeline.common.schema_utils import validate_output
from llm_pipeline.common.llm_client_factory import LLMClientFactory
from llm_pipeline.common import path_utils
# from llm_pipeline.common import text_utils # Placeholder if needed

logger = logging.getLogger(__name__)

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="LLM Processing Pipeline")
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Path to the directory containing input text files.",
    )
    parser.add_argument(
        "--input-pattern",
        type=str,
        default="*.txt",
        help="Glob pattern for input files within input_dir (default: *.txt).",
    )
    parser.add_argument(
        "--llm-profile",
        type=str,
        default=None,
        help="Name of the LLM profile to use from config.LLM_PROFILES. "
             "If not provided, config.DEFAULT_LLM_PROFILE will be used.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom base directory for outputs. If not provided, "
             "config.OUTPUT_DIR_BASE will be used.",
    )
    parser.add_argument(
        "--run-description",
        type=str,
        default="llm_run",
        help="A short description for the run, used in the output directory name (default: 'llm_run').",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of files to process.",
    )
    parser.add_argument(
        "--overwrite-outputs",
        action="store_true",
        help="If set, overwrite existing output files (not implemented for now).",
    )
    parser.add_argument(
        "--save-raw-response",
        action="store_true",
        help="If set, save the raw LLM response.",
    )
    return parser.parse_args()

def setup_run_environment(args):
    """Sets up the run environment, including output directories and logging."""
    active_config = config.load_active_llm_config(args.llm_profile)
    logger.info(f"Using LLM profile: {args.llm_profile or config.DEFAULT_LLM_PROFILE}")
    logger.info(f"Loaded active LLM config: {active_config.get('type', 'unknown_llm')}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir_name = f"{timestamp}_{args.run_description}_{active_config.get('type', 'unknown_llm')}"
    
    base_output_dir = pathlib.Path(args.output_dir or config.OUTPUT_DIR_BASE)
    run_output_dir = base_output_dir / run_dir_name

    # Create subdirectories
    (run_output_dir / "results").mkdir(parents=True, exist_ok=True)
    (run_output_dir / "raw_responses").mkdir(parents=True, exist_ok=True)
    (run_output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_output_dir / "metrics").mkdir(parents=True, exist_ok=True)

    # Configure the logger instance that is used in this module (logger = logging.getLogger(__name__))
    # __name__ for this module when run is "llm_pipeline.main"
    custom_log.setup_logger(name=__name__, log_file=(run_output_dir / "logs" / "pipeline.log"))
    logger.info(f"Run output directory: {run_output_dir}") # This should now go to the file

    # Save config snapshot (consider redacting sensitive info)
    config_to_save = active_config.copy()
    # Redact sensitive keys
    sensitive_keys = ["api_key", "ssh_key_path", "api_secret", "password"] # Add other potential sensitive keys
    for key in sensitive_keys:
        if key in config_to_save:
            config_to_save[key] = "<loaded_from_env>"
        # Also check in nested dictionaries, e.g., client_config
        if "client_config" in config_to_save and isinstance(config_to_save["client_config"], dict):
            if key in config_to_save["client_config"]:
                 config_to_save["client_config"][key] = "<loaded_from_env>"


    # Convert Path objects in config_to_save to strings
    for key, value in config_to_save.items():
        if isinstance(value, pathlib.Path):
            config_to_save[key] = str(value)
        # If there could be nested dicts with Paths, a recursive approach might be needed,
        # but for the current LLM_PROFILES structure, top-level check is likely sufficient.
        # Example for one level of nesting if 'client_config' itself could contain Paths:
        # if isinstance(value, dict):
        #     for sub_key, sub_value in value.items():
        #         if isinstance(sub_value, pathlib.Path):
        #             value[sub_key] = str(sub_value)

    io_utils.save_json(run_output_dir / "config_snapshot.json", config_to_save)
    logger.info(f"Saved config snapshot to {run_output_dir / 'config_snapshot.json'}")

    return run_output_dir, active_config

def process_single_file(
    file_path: pathlib.Path, 
    llm_client, 
    prompt_template: str, 
    run_output_dir: pathlib.Path, 
    save_raw: bool
):
    """Processes a single input file using the LLM client."""
    logger.info(f"Processing file: {file_path.name}")
    try:
        input_text = io_utils.load_text(file_path)
        
        # LLM Interaction
        # The file_identifier kwarg can be used by LLMBaseClient for more specific metrics logging
        parsed_output_data, raw_llm_response = llm_client.generate(
            prompt_content=prompt_template,
            input_text=input_text,
            file_identifier=file_path.stem
        )

        # Schema Validation
        # Assuming validate_output returns (is_valid, errors_dict_or_list)
        is_valid, validation_errors = validate_output(parsed_output_data)
        if not is_valid:
            logger.warning(f"Schema validation failed for {file_path.name}: {validation_errors}")
            # Optionally, add a flag to the output data
            if isinstance(parsed_output_data, dict):
                parsed_output_data["_validation_status"] = "failed"
                parsed_output_data["_validation_errors"] = validation_errors
        else:
            logger.info(f"Schema validation successful for {file_path.name}")
            if isinstance(parsed_output_data, dict):
                parsed_output_data["_validation_status"] = "passed"


        # Output Saving
        output_filename = f"{file_path.stem}.json"
        output_file_path = run_output_dir / "results" / output_filename
        io_utils.save_json(output_file_path, parsed_output_data)
        logger.info(f"Saved structured output to {output_file_path}")

        if save_raw:
            if raw_llm_response:
                content_to_save = ""
                # Attempt to get text if it's a Gemini-like response object
                if hasattr(raw_llm_response, 'text') and isinstance(raw_llm_response.text, str):
                    content_to_save = raw_llm_response.text
                elif isinstance(raw_llm_response, str):
                    content_to_save = raw_llm_response
                elif isinstance(raw_llm_response, (dict, list)): # If raw response itself is dict/list
                    try:
                        content_to_save = json.dumps(raw_llm_response, indent=2)
                    except TypeError as e:
                        logger.warning(f"Could not serialize raw_llm_response to JSON for {file_path.name}: {e}. Falling back to str().")
                        content_to_save = str(raw_llm_response)
                else: # Fallback for other object types
                    content_to_save = str(raw_llm_response)
                
                raw_response_filename = f"{file_path.stem}_raw.txt"
                raw_response_file_path = run_output_dir / "raw_responses" / raw_response_filename
                io_utils.save_text(raw_response_file_path, content_to_save)
                logger.info(f"Saved raw LLM response to {raw_response_file_path}")
            else:
                logger.debug(f"Raw response saving enabled, but raw_llm_response was empty or None for {file_path.name}.")


        return True
    except Exception as e:
        logger.error(f"Failed to process file {file_path.name}: {e}", exc_info=True)
        return False

def main():
    """Main function to orchestrate the LLM processing pipeline."""
    args = parse_arguments()
    
    # Setup environment (logging is configured here)
    run_output_dir, active_llm_config = setup_run_environment(args)

    logger.info("Initializing MetricsLogger...")
    metrics_logger = MetricsLogger(metrics_dir=(run_output_dir / "metrics"))
    metrics_logger.start_run()
    logger.info("MetricsLogger initialized and run started.")

    logger.info("Instantiating LLM client...")
    try:
        llm_client = LLMClientFactory.create_client(active_llm_config, metrics_logger=metrics_logger)
        logger.info(f"LLM client created: {type(llm_client).__name__}")
    except Exception as e:
        logger.error(f"Failed to create LLM client: {e}", exc_info=True)
        metrics_logger.end_run(processed_items=0, successful_items=0, failed_items=0, status="ERROR_CLIENT_INIT")
        # Save partial metrics if possible
        run_summary_metrics = metrics_logger.get_current_run_metrics()
        io_utils.save_json(run_output_dir / "metrics" / "run_summary_error.json", run_summary_metrics.to_dict())
        return

    logger.info("Loading prompt template...")
    try:
        prompt_template_path = pathlib.Path(active_llm_config["prompt_file"])
        if not prompt_template_path.is_absolute():
             # Assuming prompt files are relative to a known 'prompts' dir or config base
             # For now, let's assume it's relative to the project root or a path defined in config
             # This might need adjustment based on actual project structure for prompts
            if 'PROMPTS_DIR' in config.__dict__:
                prompt_template_path = pathlib.Path(config.PROMPTS_DIR) / prompt_template_path
            else: # Fallback: try relative to config file's directory if PROMPTS_DIR not set
                # This assumes config.py is at a level where this makes sense.
                # A more robust solution would be to have config.py resolve this path.
                config_file_path = pathlib.Path(config.__file__).parent
                prompt_template_path = (config_file_path.parent / prompt_template_path).resolve()


        logger.info(f"Attempting to load prompt from: {prompt_template_path}")
        prompt_template = io_utils.load_text(prompt_template_path)
        logger.info(f"Prompt template loaded successfully from {prompt_template_path}")
    except KeyError:
        logger.error("'prompt_file' not found in LLM configuration.", exc_info=True)
        metrics_logger.end_run(processed_items=0, successful_items=0, failed_items=0, status="ERROR_PROMPT_CONFIG")
        run_summary_metrics = metrics_logger.get_current_run_metrics()
        io_utils.save_json(run_output_dir / "metrics" / "run_summary_error.json", run_summary_metrics.to_dict())
        return
    except FileNotFoundError:
        logger.error(f"Prompt template file not found at {prompt_template_path}", exc_info=True)
        metrics_logger.end_run(processed_items=0, successful_items=0, failed_items=0, status="ERROR_PROMPT_NOT_FOUND")
        run_summary_metrics = metrics_logger.get_current_run_metrics()
        io_utils.save_json(run_output_dir / "metrics" / "run_summary_error.json", run_summary_metrics.to_dict())
        return
    except Exception as e:
        logger.error(f"Failed to load prompt template: {e}", exc_info=True)
        metrics_logger.end_run(processed_items=0, successful_items=0, failed_items=0, status="ERROR_PROMPT_LOAD")
        run_summary_metrics = metrics_logger.get_current_run_metrics()
        io_utils.save_json(run_output_dir / "metrics" / "run_summary_error.json", run_summary_metrics.to_dict())
        return


    logger.info("Getting input files...")
    input_files = path_utils.discover_input_files(
        input_dir=pathlib.Path(args.input_dir),
        pattern=args.input_pattern,
        limit=args.limit
    )

    if not input_files:
        logger.warning("No input files found. Exiting.")
        metrics_logger.end_run(processed_items=0, successful_items=0, failed_items=0, status="NO_FILES")
        run_summary_metrics = metrics_logger.get_current_run_metrics()
        io_utils.save_json(run_output_dir / "metrics" / "run_summary.json", run_summary_metrics.to_dict())
        return

    logger.info(f"Starting processing of {len(input_files)} files...")
    success_count = 0
    failure_count = 0

    start_time_processing = time.time()
    for file_path in input_files:
        if process_single_file(
            file_path,
            llm_client,
            prompt_template, 
            run_output_dir, 
            args.save_raw_response
        ):
            success_count += 1
        else:
            failure_count += 1
    
    processing_duration = time.time() - start_time_processing
    logger.info(f"File processing loop completed in {processing_duration:.2f} seconds.")

    logger.info("Finalizing run and saving metrics...")
    # Ensure RunMetrics has a to_dict() method or adapt as needed.
    # The end_run method in MetricsLogger should return a RunMetrics object.
    # The end_run method calculates these internally.
    run_summary_metrics = metrics_logger.end_run()
    
    # Add overall processing time to summary if not already there
    if isinstance(run_summary_metrics, RunMetrics) and hasattr(run_summary_metrics, 'run_duration_total_seconds'):
         # Assuming end_run calculates total time. If not, we can add it.
         # For now, let's assume it's handled or we add a custom field.
         pass
    
    # Save the summary
    try:
        summary_dict = run_summary_metrics.to_dict() # Assumes RunMetrics has to_dict()
        io_utils.save_json(run_output_dir / "metrics" / "run_summary.json", summary_dict)
        logger.info(f"Run summary saved to {run_output_dir / 'metrics' / 'run_summary.json'}")
    except AttributeError:
        logger.error("Failed to save run_summary.json: RunMetrics object may not have a to_dict() method. Saving raw object.")
        # Fallback: save the object representation if to_dict is missing
        io_utils.save_json(run_output_dir / "metrics" / "run_summary_raw_object.json", vars(run_summary_metrics))
    except Exception as e:
        logger.error(f"Failed to save run_summary.json: {e}", exc_info=True)


    logger.info(f"Pipeline run completed. Processed: {len(input_files)}, Succeeded: {success_count}, Failed: {failure_count}")
    logger.info(f"Outputs in: {run_output_dir}")
    if failure_count > 0:
        logger.warning(f"{failure_count} files failed processing. Check logs for details.")

if __name__ == "__main__":
    main()