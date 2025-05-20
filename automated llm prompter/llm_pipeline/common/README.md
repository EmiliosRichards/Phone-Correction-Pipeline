# Common Utilities

This directory contains shared utilities and base classes used across different versions of the LLM pipeline. These components provide core functionality and ensure consistency between pipeline versions.

## Components

This directory provides the foundational building blocks for interacting with Large Language Models (LLMs) within the pipeline. The key components are:

### `llm_client_base.py`
Defines the `LLMBaseClient` abstract base class (ABC). This class outlines the common interface that all specific LLM clients must implement. It ensures that different LLM providers can be used interchangeably within the pipeline, promoting modularity and flexibility.

**Key aspects**:
- Abstract methods for core LLM interactions (e.g., `generate`, `get_config`).
- Common configuration handling.

### `llm_client_factory.py`
Contains the `LLMClientFactory`. This factory is responsible for creating instances of specific LLM clients based on configuration. It decouples the client creation logic from the rest of the application, making it easier to add or modify client implementations.

**Usage**:
```python
from llm_pipeline.common.llm_client_factory import LLMClientFactory
from llm_pipeline.config import load_config

# Load pipeline configuration
config = load_config("path/to/your/config.yaml") # Or your specific config loading mechanism

# Get an LLM client instance (e.g., for Gemini)
# The factory will look up the appropriate client class based on the config
llm_client = LLMClientFactory.create_llm_client(client_name="gemini", llm_config=config.llm_clients.gemini)

# Generate results
result = llm_client.generate("Your text here")
```

**Note on Specific Client Implementations:**
Specific client implementations (e.g., for Gemini, Llama, Mixtral) are located in the [`llm_pipeline/clients/`](../clients/) directory. Each of these clients inherits from `LLMBaseClient` (defined in [`llm_pipeline/common/llm_client_base.py`](llm_pipeline/common/llm_client_base.py:0)) and implements the required methods for interacting with its respective LLM service. The `LLMClientFactory` uses these implementations to provide the appropriate client instance.

### `schema_utils.py`
Utilities for validating and processing structured output according to the pipeline's schema.

**Features**:
- Schema validation for LLM outputs
- Phone number format validation
- Category validation
- Confidence score validation
- Context validation

**Usage**:
```python
from llm_pipeline.common.schema_utils import validate_output

# Validate LLM output
try:
    validate_output(output_data)
except ValueError as e:
    print(f"Validation failed: {e}")
```

### `io_utils.py`
File I/O utilities for reading and writing pipeline data.

**Features**:
- File reading and writing
- Directory management
- Path handling
- File format validation
- Batch file operations

**Usage**:
```python
from llm_pipeline.common.io_utils import read_text_file, write_json_file

# Read text file
text = read_text_file("path/to/file.txt")

# Write JSON file
write_json_file("path/to/output.json", data)
```

### `text_utils.py`
Text processing utilities for cleaning and normalizing input text.

**Features**:
- Text cleaning
- Phone number normalization
- Context extraction
- Text chunking
- Format standardization

**Usage**:
```python
from llm_pipeline.common.text_utils import clean_text, normalize_phone_number

# Clean text
cleaned_text = clean_text(raw_text)

# Normalize phone number
normalized_number = normalize_phone_number("(800) 555-1234")
```

### `log.py`
Logging utilities for consistent logging across the pipeline.

**Features**:
- Structured logging
- Log level control
- File and console output
- Error tracking
- Progress logging

**Usage**:
```python
from llm_pipeline.common.log import setup_logger, log_error

# Setup logger
logger = setup_logger("module_name")

# Log error
log_error(logger, "Error message", exception)
```

## Dependencies

- Python 3.8+
- `requests` for API calls
- `jsonschema` for schema validation
- `python-dateutil` for timestamp handling

### Core Dependencies

The following dependencies are required for the pipeline to function:

```txt
# API and HTTP
requests==2.31.0  # HTTP client with retry support
urllib3==2.1.0   # HTTP client library
certifi==2024.2.2  # Mozilla's CA Bundle

# Schema Validation
jsonschema==4.21.1  # JSON Schema validation
typing-extensions==4.9.0  # Type hints support

# Date and Time
python-dateutil==2.8.2  # Date parsing and manipulation
pytz==2024.1  # Timezone support

# Logging and Monitoring
structlog==24.1.0  # Structured logging
python-json-logger==2.0.7  # JSON log formatting

# Development Dependencies
pytest==8.0.0  # Testing framework
black==24.1.1  # Code formatting
mypy==1.8.0  # Static type checking
```

### Version Management

1. **Version Pinning**:
   - Use exact versions (`==`) for production dependencies
   - Use compatible release (`~=`) for development tools
   - Document version constraints in `requirements.txt`
   - Example:
     ```txt
     # Production dependencies (exact versions)
     requests==2.31.0
     jsonschema==4.21.1
     
     # Development dependencies (compatible versions)
     pytest~=8.0.0
     black~=24.1.0
     ```

2. **Dependency Updates**:
   - Regular update schedule (e.g., monthly)
   - Use `pip list --outdated` to check for updates
   - Test updates in development environment
   - Update `requirements.txt` with new versions
   - Example workflow:
     ```bash
     # Check for outdated packages
     pip list --outdated
     
     # Update specific package
     pip install --upgrade requests
     
     # Update requirements.txt
     pip freeze > requirements.txt
     ```

### Security Monitoring

1. **Vulnerability Scanning**:
   - Use `pip-audit` for security checks
   - Regular scanning schedule
   - Monitor security advisories
   - Example:
     ```bash
     # Install pip-audit
     pip install pip-audit
     
     # Run security audit
     pip-audit
     
     # Generate requirements with hashes
     pip freeze --require-hashes > requirements.txt
     ```

2. **Security Best Practices**:
   - Use `--require-hashes` in requirements
   - Verify package signatures
   - Monitor package maintainers
   - Example:
     ```txt
     # requirements.txt with hashes
     requests==2.31.0 \
         --hash=sha256:942c5a758f98d790eaed1a29cb6eefc7ffb0d1cf7af05c3d2791656dbd6ad1e1 \
         --hash=sha256:58cd9807b518b53d17b36d6f113ff611428192d3c0ec38688d5b0e1e6875e426
     ```

3. **Update Process**:
   - Regular security reviews
   - Automated vulnerability scanning
   - Update documentation
   - Example workflow:
     ```bash
     # 1. Check for vulnerabilities
     pip-audit
     
     # 2. Update vulnerable packages
     pip install --upgrade vulnerable-package
     
     # 3. Test the updates
     pytest
     
     # 4. Update requirements
     pip freeze > requirements.txt
     
     # 5. Document changes
     git commit -m "Update dependencies for security"
     ```

### Dependency Management Tools

1. **pip-tools**:
   - Generate deterministic requirements
   - Manage development dependencies
   - Example:
     ```bash
     # Install pip-tools
     pip install pip-tools
     
     # Generate requirements
     pip-compile requirements.in
     
     # Update requirements
     pip-compile --upgrade requirements.in
     ```

2. **poetry**:
   - Modern dependency management
   - Lock file support
   - Example:
     ```bash
     # Install poetry
     curl -sSL https://install.python-poetry.org | python3 -
     
     # Add dependency
     poetry add requests==2.31.0
     
     # Update dependencies
     poetry update
     ```

### Best Practices

1. **Version Control**:
   - Commit `requirements.txt`
   - Document version changes
   - Use dependency lock files
   - Review dependency updates

2. **Security**:
   - Regular vulnerability scans
   - Monitor security advisories
   - Use package hashes
   - Verify package sources

3. **Testing**:
   - Test after updates
   - Use virtual environments
   - Document breaking changes
   - Maintain compatibility

4. **Documentation**:
   - Document version constraints
   - Update changelog
   - Note security updates
   - Document update process

## Usage Guidelines

1. **Import Structure**:
   ```python
   from llm_pipeline.common import (
       llm_client_base,
       llm_client_factory,
       schema_utils,
       io_utils,
       text_utils,
       log
   )
   ```

2. **Error Handling**:
   - Use provided error classes
   - Implement proper error handling
   - Log errors appropriately
   - Handle validation failures

3. **Configuration**:
   - Use shared configuration
   - Follow naming conventions
   - Maintain backward compatibility
   - Document custom settings

4. **Testing**:
   - Test shared utilities
   - Validate schema compliance
   - Check error handling
   - Verify logging

## Best Practices

1. **Code Organization**:
   - Keep utilities focused
   - Maintain clear interfaces
   - Document public APIs
   - Follow naming conventions

2. **Error Handling**:
   - Use custom exceptions
   - Provide clear messages
   - Log appropriately
   - Handle edge cases

3. **Performance**:
   - Cache when appropriate
   - Optimize file operations
   - Batch when possible
   - Monitor resource usage

   - File I/O Optimization:
     - Use batch processing for large datasets (e.g., process files in chunks of 1000)
     - Implement file caching for frequently accessed data
     - Use memory-mapped files for large files
     - Compress data when storing (e.g., gzip for text files)
     - Implement incremental processing for large datasets
     - Use async I/O for non-blocking operations
     - Consider using a database for structured data storage
   
   - Rate Limiting and Scaling:
     - Implement exponential backoff for API retries
     - Use connection pooling for HTTP requests
     - Distribute scraping across multiple workers
     - Implement request queuing for large-scale operations
     - Use rate limiting tokens (e.g., 100 requests per minute)
     - Monitor API quotas and adjust accordingly
     - Implement circuit breakers for failing endpoints
     - Use proxy rotation for distributed scraping
     - Consider using a message queue for job distribution
   
   - Resource Management:
     - Monitor memory usage and implement garbage collection
     - Use generators for large data streams
     - Implement proper cleanup of resources
     - Profile code for bottlenecks
     - Use appropriate data structures for performance
     - Consider using multiprocessing for CPU-bound tasks
     - Implement proper connection pooling
     - Monitor system resources (CPU, memory, disk I/O)

4. **Maintenance**:
   - Keep dependencies updated
   - Document changes
   - Maintain tests
   - Review periodically

## Logging and Debugging Guidelines

### Log Levels

1. **DEBUG** (Level 10):
   - Use for detailed information, typically useful only for diagnosing problems
   - Examples:
     - API request/response details
     - Function entry/exit points
     - Variable values during processing
     - Performance metrics
     - Memory usage statistics
   - Enable in development and when troubleshooting

2. **INFO** (Level 20):
   - Use for general operational events
   - Examples:
     - Pipeline stage completion
     - Successful API calls
     - File operations completion
     - Progress updates
     - Configuration changes
   - Default level for production

3. **WARNING** (Level 30):
   - Use for potentially harmful situations
   - Examples:
     - Rate limit approaching
     - Retry attempts
     - Deprecated feature usage
     - Resource cleanup needed
     - Performance degradation
   - Always enabled in production

4. **ERROR** (Level 40):
   - Use for error events that might still allow the application to continue
   - Examples:
     - API call failures
     - File I/O errors
     - Validation failures
     - Resource exhaustion
     - Timeout events
   - Always enabled and monitored

5. **CRITICAL** (Level 50):
   - Use for critical events that may lead to application termination
   - Examples:
     - System resource exhaustion
     - Security breaches
     - Data corruption
     - Unrecoverable errors
   - Always enabled and requires immediate attention

### Debugging Guidelines

1. **Log Analysis**:
   - Use log aggregation tools (e.g., ELK Stack, Graylog)
   - Implement structured logging with consistent fields
   - Include correlation IDs for request tracing
   - Add timestamps in ISO format
   - Use log rotation to manage file sizes

2. **Common Issues and Solutions**:
   - API Rate Limiting:
     ```python
     logger.warning(f"Rate limit approaching: {remaining_calls} calls left")
     logger.error(f"Rate limit exceeded: {error_details}")
     ```
   - Validation Failures:
     ```python
     logger.error(f"Schema validation failed: {validation_error}")
     logger.debug(f"Invalid data: {json.dumps(data, indent=2)}")
     ```
   - Performance Issues:
     ```python
     logger.info(f"Processing time: {processing_time}ms")
     logger.warning(f"Slow operation detected: {operation_details}")
     ```

3. **Best Practices**:
   - Include context in log messages
   - Use appropriate log levels
   - Implement log rotation
   - Add stack traces for errors
   - Include request IDs for tracing
   - Log both success and failure cases
   - Use structured logging format

4. **Monitoring and Alerts**:
   - Set up log-based alerts
   - Monitor error rates
   - Track performance metrics
   - Set up dashboards for key metrics
   - Implement automated log analysis

## Schema Versioning and Migration

### Schema Evolution Guidelines

1. **Adding New Fields**:
   - Make new fields optional with default values
   - Use version-specific validation rules
   - Document field deprecation timelines
   - Example:
     ```python
     # New field with backward compatibility
     def validate_output(data: Dict[str, Any], version: str = "v2") -> bool:
         if version == "v2":
             # New field is required
             if "new_field" not in data:
                 raise SchemaValidationError("Missing required field: new_field")
         else:
             # New field is optional in v1
             data.setdefault("new_field", default_value)
     ```

2. **Adding New Categories**:
   - Extend the PhoneCategory enum
   - Maintain backward compatibility
   - Update validation rules
   - Example:
     ```python
     class PhoneCategory(str, Enum):
         # Original categories
         SALES = "Sales"
         SUPPORT = "Support"
         # New categories (v2)
         RECRUITING = "Recruiting"
         GENERAL = "General"
         LOW_VALUE = "LowValue"
         
         @classmethod
         def get_valid_categories(cls, version: str = "v2") -> Set[str]:
             if version == "v1":
                 return {"Sales", "Support"}
             return {category.value for category in cls}
     ```

3. **Maintaining Compatibility**:
   - Use version-specific schemas
   - Implement schema migration functions
   - Keep old validation rules
   - Example:
     ```python
     def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
         """Migrate v1 data to v2 format."""
         migrated = data.copy()
         # Add new required fields
         migrated.setdefault("new_field", default_value)
         # Update category if needed
         if migrated["category"] == "Other":
             migrated["category"] = "General"
         return migrated
     ```

### Migration Strategies

1. **Data Migration**:
   - Create migration scripts
   - Validate migrated data
   - Keep original data as backup
   - Example:
     ```python
     def migrate_data(input_path: Path, output_path: Path):
         # Read original data
         data = load_json(input_path)
         
         # Migrate to new schema
         migrated = migrate_v1_to_v2(data)
         
         # Validate migrated data
         validate_output(migrated, version="v2")
         
         # Save with backup
         backup_path = input_path.with_suffix(".v1.backup")
         input_path.rename(backup_path)
         save_json(output_path, migrated)
     ```

2. **Version Detection**:
   - Implement version detection logic
   - Use schema markers
   - Handle unknown versions
   - Example:
     ```python
     def detect_schema_version(data: Dict[str, Any]) -> str:
         if "schema_version" in data:
             return data["schema_version"]
         # Check for v2-specific fields
         if "new_field" in data:
             return "v2"
         return "v1"
     ```

3. **Backward Compatibility**:
   - Support multiple schema versions
   - Implement version-specific validation
   - Provide migration utilities
   - Example:
     ```python
     def process_data(data: Dict[str, Any]):
         version = detect_schema_version(data)
         if version == "v1":
             data = migrate_v1_to_v2(data)
         validate_output(data, version="v2")
         return data
     ```

### Best Practices

1. **Schema Changes**:
   - Document all schema changes
   - Provide migration scripts
   - Test with sample data
   - Maintain version history
   - Use semantic versioning

2. **Data Handling**:
   - Always backup before migration
   - Validate after migration
   - Keep original data format
   - Document migration steps
   - Test with real data

3. **Code Updates**:
   - Update all related code
   - Add version checks
   - Update tests
   - Document changes
   - Review dependencies

4. **Deployment**:
   - Plan migration timing
   - Coordinate with teams
   - Monitor migration
   - Have rollback plan
   - Verify data integrity

## Contributing

When adding new utilities to the common directory:

1. **Documentation**:
   - Add docstrings
   - Update README
   - Include examples
   - Document dependencies

2. **Testing**:
   - Add unit tests
   - Include edge cases
   - Test error handling
   - Verify performance

3. **Review**:
   - Check code style
   - Verify documentation
   - Test compatibility
   - Review security

4. **Integration**:
   - Update imports
   - Check dependencies
   - Verify functionality
   - Test with pipeline 