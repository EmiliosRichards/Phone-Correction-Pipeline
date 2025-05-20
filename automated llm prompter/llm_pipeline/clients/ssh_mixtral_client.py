import json
import subprocess
import shlex
import logging
import uuid
from typing import Dict, Any, List, Optional

import paramiko

from llm_pipeline.common.llm_client_base_v2 import LLMBaseClientV2 # Updated import
from llm_pipeline.common.metrics import MetricsLogger # For type hinting
from llm_pipeline import config # For DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

class SSHMixtralClient(LLMBaseClientV2): # Updated base class
    """
    LLM Client for interacting with a Mixtral model running on a remote server
    accessed via an SSH tunnel.
    """

    def __init__(self, client_config: Dict[str, Any], metrics_logger: MetricsLogger = None):
        super().__init__(client_config, metrics_logger)
        self.ssh_host = self.client_config.get("ssh_host")
        self.ssh_user = self.client_config.get("ssh_user")
        self.ssh_key_path = self.client_config.get("ssh_key_path")
        self.remote_command_template = self.client_config.get("remote_command_template")

        if not all([self.ssh_host, self.ssh_user, self.ssh_key_path, self.remote_command_template]):
            missing_keys = [
                key for key, value in {
                    "ssh_host": self.ssh_host,
                    "ssh_user": self.ssh_user,
                    "ssh_key_path": self.ssh_key_path,
                    "remote_command_template": self.remote_command_template
                }.items() if not value
            ]
            raise ValueError(f"Missing required SSH configuration keys: {', '.join(missing_keys)}")

    def _prepare_request(self, prompt_content: str, input_text: str, **kwargs) -> str:
        """
        Formats the prompt_content template with input_text.
        This will be written to a remote temp file.
        """
        try:
            formatted_prompt = prompt_content.format(webpage_text=input_text)
        except KeyError as e:
            logger.error(f"KeyError during prompt formatting: {e}. Prompt content: '{prompt_content}', Input text: '{input_text}'")
            raise ValueError(f"Missing key in prompt_content for formatting: {e}. Ensure 'webpage_text' or other placeholders are correctly used.") from e
        return formatted_prompt

    def _execute_request(self, prepared_prompt_text: str, **kwargs) -> str:
        """
        Executes the remote command via SSH after writing the prompt to a remote temp file.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        remote_temp_prompt_path = f"/tmp/prompt_{uuid.uuid4()}.txt"

        try:
            client.connect(
                hostname=self.ssh_host,
                username=self.ssh_user,
                key_filename=self.ssh_key_path,
                timeout=self.client_config.get("ssh_timeout", 10)
            )

            # Write prompt to remote temporary file
            sftp = None
            try:
                sftp = client.open_sftp()
                with sftp.file(remote_temp_prompt_path, 'w') as remote_file:
                    remote_file.write(prepared_prompt_text)
            except Exception as e:
                logger.error(f"SFTP operation failed: {e}")
                raise ConnectionError(f"Failed to write prompt to remote server via SFTP: {e}") from e
            finally:
                if sftp:
                    sftp.close()

            # Construct final remote command
            final_remote_command = self.remote_command_template.format(
                remote_prompt_file_path=remote_temp_prompt_path,
                temperature=self.client_config.get("temperature", 0.2),
                max_tokens=self.client_config.get("max_tokens", 1500),
                model_name=self.client_config.get("model_name", "mixtral-8x7b-instruct")
            )
            logger.debug(f"Executing remote command: {final_remote_command}")

            # Execute remote command
            stdin, stdout, stderr = client.exec_command(
                final_remote_command,
                timeout=self.client_config.get("command_timeout", config.DEFAULT_TIMEOUT)
            )

            stdout_data = stdout.read().decode('utf-8').strip()
            stderr_data = stderr.read().decode('utf-8').strip()
            exit_status = stdout.channel.recv_exit_status() # Get exit status

            if stderr_data:
                logger.warning(f"Remote command stderr: {stderr_data}")
            if exit_status != 0:
                logger.error(f"Remote command failed with exit status {exit_status}. Stderr: {stderr_data}, Stdout: {stdout_data}")
                raise subprocess.CalledProcessError(exit_status, final_remote_command, output=stdout_data, stderr=stderr_data)

            return stdout_data

        except paramiko.AuthenticationException as e:
            logger.error(f"SSH Authentication failed for {self.ssh_user}@{self.ssh_host}: {e}")
            raise ConnectionRefusedError(f"SSH Authentication failed: {e}") from e
        except paramiko.SSHException as e:
            logger.error(f"SSH connection error to {self.ssh_host}: {e}")
            raise ConnectionError(f"SSH connection error: {e}") from e
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred during SSH command execution: {e}")
            raise RuntimeError(f"Unexpected error during SSH execution: {e}") from e
        finally:
            # Cleanup: Delete the remote temporary prompt file
            if client.get_transport() and client.get_transport().is_active(): # Check if client is connected
                sftp_cleanup = None
                try:
                    sftp_cleanup = client.open_sftp()
                    sftp_cleanup.remove(remote_temp_prompt_path)
                    logger.debug(f"Successfully deleted remote temp file: {remote_temp_prompt_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete remote temporary file {remote_temp_prompt_path}: {e}")
                finally:
                    if sftp_cleanup:
                        sftp_cleanup.close()
            client.close()

    def _parse_response(self, llm_output_str: str, **kwargs) -> Dict[str, Any]:
        """
        Parses the JSON string output from the LLM.
        """
        llm_output_str = llm_output_str.strip()
        # Strip potential markdown code block fences
        if llm_output_str.startswith("```json"):
            llm_output_str = llm_output_str[7:]
        if llm_output_str.endswith("```"):
            llm_output_str = llm_output_str[:-3]
        llm_output_str = llm_output_str.strip()

        try:
            if not llm_output_str: # Handle empty string case
                logger.error("Received empty string from LLM output.")
                return {"error": "Received empty string from Mixtral", "raw_stdout": ""}

            parsed_json_output = json.loads(llm_output_str)
            return parsed_json_output
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Mixtral JSON output: {e}. Raw stdout: '{llm_output_str}'")
            return {"error": "Failed to parse Mixtral JSON response", "raw_stdout": llm_output_str}

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Returns an empty dictionary as default config.
        Specific configurations are expected from the 'mixtral_ssh_json' profile.
        """
        return {}

    def invoke(self, prompt_content: str, input_text: str, **kwargs) -> Dict[str, Any]:
        """
        Main method to invoke the LLM.
        Orchestrates preparing the request, executing it, and parsing the response.
        """
        if self.metrics_logger:
            self.metrics_logger.log_request(self.client_config.get("model_name", "ssh_mixtral"), len(prompt_content) + len(input_text))

        prepared_request = self._prepare_request(prompt_content, input_text, **kwargs)
        
        try:
            raw_response = self._execute_request(prepared_request, **kwargs)
            parsed_response = self._parse_response(raw_response, **kwargs)

            if self.metrics_logger:
                self.metrics_logger.log_response(self.client_config.get("model_name", "ssh_mixtral"), len(raw_response))
            
            return parsed_response
        except (subprocess.CalledProcessError, ConnectionError, ConnectionRefusedError, RuntimeError) as e:
            # These are exceptions from _execute_request that indicate a failure in execution
            if self.metrics_logger:
                self.metrics_logger.log_error(self.client_config.get("model_name", "ssh_mixtral"))
            # Return a structured error, similar to _parse_response
            return {"error": f"LLM request execution failed: {str(e)}", "details": str(e)}
        except Exception as e: # Catch-all for other unexpected errors during the process
            if self.metrics_logger:
                self.metrics_logger.log_error(self.client_config.get("model_name", "ssh_mixtral"))
            self.logger.error(f"Unexpected error during LLM invocation: {e}")
            return {"error": f"Unexpected error during LLM invocation: {str(e)}", "details": str(e)}