# tests/conftest.py
import pytest
import tempfile
import os
import shutil
from pathlib import Path

@pytest.fixture(scope="session")
def test_output_dir():
    """Create a temporary directory for test output that persists for the entire test session."""
    temp_dir = tempfile.TemporaryDirectory()
    original_results_dir = os.environ.get('RESULTS_DIR', None)
    original_processed_dir = os.environ.get('PROCESSED_DIR', None)
    
    os.environ['RESULTS_DIR'] = os.path.join(temp_dir.name, "results")
    os.environ['PROCESSED_DIR'] = os.path.join(temp_dir.name, "processed")
    
    Path(os.environ['RESULTS_DIR']).mkdir(parents=True, exist_ok=True)
    Path(os.environ['PROCESSED_DIR']).mkdir(parents=True, exist_ok=True)
    
    yield temp_dir.name
    
    # Cleanup after all tests
    if original_results_dir:
        os.environ['RESULTS_DIR'] = original_results_dir
    else:
        os.environ.pop('RESULTS_DIR', None)
        
    if original_processed_dir:
        os.environ['PROCESSED_DIR'] = original_processed_dir
    else:
        os.environ.pop('PROCESSED_DIR', None)
    
    temp_dir.cleanup()

@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for individual test use."""
    temp_dir = tempfile.TemporaryDirectory()
    yield Path(temp_dir.name)
    temp_dir.cleanup()