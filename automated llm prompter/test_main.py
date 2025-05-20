import pytest
import asyncio
from pathlib import Path
import json
from main import UnifiedPipeline
from scraper.main import ScrapingError

# Test URLs - using example.com as it's a stable test site
TEST_URLS = [
    "https://example.com",
    "https://example.org"
]

@pytest.fixture
def pipeline():
    """Create a pipeline instance for testing."""
    return UnifiedPipeline(run_name="test_run")

@pytest.mark.asyncio
async def test_single_url_processing(pipeline):
    """Test processing a single URL through the pipeline."""
    url = TEST_URLS[0]
    await pipeline.process_url(url)
    
    # Verify scraping results
    hostname = "example.com"
    text_files = list(Path("pages") / hostname / "**" / "text.txt")
    assert len(text_files) > 0, "No text files were created during scraping"
    
    # Verify LLM output
    output_files = list(pipeline.llm_run_dir.glob(f"{hostname}/**/*.json"))
    assert len(output_files) > 0, "No LLM output files were created"
    
    # Verify output structure
    with open(output_files[0]) as f:
        output = json.load(f)
        assert isinstance(output, dict), "Output should be a dictionary"
        assert "phone_numbers" in output, "Output should contain phone_numbers field"

@pytest.mark.asyncio
async def test_multiple_url_processing(pipeline):
    """Test processing multiple URLs concurrently."""
    await pipeline.process_urls(TEST_URLS)
    
    # Verify results for each URL
    for url in TEST_URLS:
        hostname = url.split("//")[1]
        output_files = list(pipeline.llm_run_dir.glob(f"{hostname}/**/*.json"))
        assert len(output_files) > 0, f"No output files found for {hostname}"

@pytest.mark.asyncio
async def test_error_handling(pipeline):
    """Test error handling with invalid URL."""
    invalid_url = "https://this-is-an-invalid-url-that-does-not-exist.com"
    await pipeline.process_url(invalid_url)
    
    # Verify the URL was added to failed_urls
    assert len(pipeline.failed_urls) > 0, "Failed URL should be recorded"
    assert any(invalid_url in failed[0] for failed in pipeline.failed_urls), "Invalid URL should be in failed_urls"

def test_summary_generation(pipeline):
    """Test summary generation after processing."""
    pipeline.save_summary()
    
    summary_file = pipeline.llm_run_dir / "summary.json"
    assert summary_file.exists(), "Summary file should be created"
    
    with open(summary_file) as f:
        summary = json.load(f)
        assert "timestamp" in summary
        assert "run_name" in summary
        assert "scraping" in summary
        assert "llm_pipeline" in summary
        assert "failed_urls" in summary 