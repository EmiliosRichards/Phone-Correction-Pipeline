"""
Tests for the text normalization module.
"""
import sys
import os
import unittest
import tempfile
import pytest
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.text.utils import normalize_text, clean_text, normalize_and_clean

class TestTextNormalizer(unittest.TestCase):
    """Test cases for the text normalization module."""
    
    def test_normalize_text(self):
        """Test the text normalization function."""
        # Test with string input
        text = "Test with unicode characters: é, ü, ñ"
        normalized = normalize_text(text)
        self.assertEqual(normalized, "Test with unicode characters: é, ü, ñ")
        
        # Test with bytes input (UTF-8)
        text_bytes = "Test with unicode characters: é, ü, ñ".encode('utf-8')
        normalized = normalize_text(text_bytes)
        self.assertEqual(normalized, "Test with unicode characters: é, ü, ñ")
        
        # Test with bytes input (Latin-1)
        text_bytes = "Test with unicode characters: é, ü, ñ".encode('latin-1')
        normalized = normalize_text(text_bytes, encoding='latin-1')
        self.assertEqual(normalized, "Test with unicode characters: é, ü, ñ")
        
        # Test with bytes input (auto-detection)
        text_bytes = "Test with unicode characters: é, ü, ñ".encode('utf-8')
        normalized = normalize_text(text_bytes)
        self.assertEqual(normalized, "Test with unicode characters: é, ü, ñ")
    
    def test_clean_text(self):
        """Test the text cleaning function."""
        # Test with basic text
        text = "Phone: 123-456-7890"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Phone: 123 456 7890")
        
        # Test with multiple separators
        text = "Phone: 123-456.789/0"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Phone: 123 456 789 0")
        
        # Test with unwanted characters
        text = "Phone: 123-456-7890 <script>alert('test')</script>"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Phone: 123 456 7890 ")
        
        # Test with control characters
        text = "Phone: 123-456-7890\n\t\r"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Phone: 123 456 7890")
    
    def test_normalize_and_clean(self):
        """Test the combined normalize and clean function."""
        # Test with string input
        text = "Phone: 123-456-7890 with unicode: é, ü, ñ"
        result = normalize_and_clean(text)
        self.assertEqual(result, "Phone: 123 456 7890 with unicode: é, ü, ñ")
        
        # Test with bytes input
        text_bytes = "Phone: 123-456-7890 with unicode: é, ü, ñ".encode('utf-8')
        result = normalize_and_clean(text_bytes)
        self.assertEqual(result, "Phone: 123 456 7890 with unicode: é, ü, ñ")

class TestFileProcessing(unittest.TestCase):
    """Test cases for file processing functionality."""
    
    def setUp(self):
        """Set up temporary test files."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Store original environment variables
        self.original_results_dir = os.environ.get('RESULTS_DIR', None)
        self.original_processed_dir = os.environ.get('PROCESSED_DIR', None)
        
        # Set environment variables to use temporary directories
        os.environ['RESULTS_DIR'] = str(self.test_dir / "results")
        os.environ['PROCESSED_DIR'] = str(self.test_dir / "processed")
        
        # Create the directories
        Path(os.environ['RESULTS_DIR']).mkdir(parents=True, exist_ok=True)
        Path(os.environ['PROCESSED_DIR']).mkdir(parents=True, exist_ok=True)
        
        # Create a test website directory structure
        self.website_dir = self.test_dir / "pages" / "example_com"
        self.website_dir.mkdir(parents=True)
        
        # Create a test text file
        self.text_file = self.website_dir / "text.txt"
        with open(self.text_file, 'w', encoding='utf-8') as f:
            f.write("Phone: 123-456-7890 with unicode: é, ü, ñ")
    
    def tearDown(self):
        """Clean up temporary test files."""
        # Restore original environment
        if self.original_results_dir:
            os.environ['RESULTS_DIR'] = self.original_results_dir
        else:
            os.environ.pop('RESULTS_DIR', None)
            
        if self.original_processed_dir:
            os.environ['PROCESSED_DIR'] = self.original_processed_dir
        else:
            os.environ.pop('PROCESSED_DIR', None)
        
        # Clean up temporary directory
        self.temp_dir.cleanup()
    
    def test_process_scraped_texts(self):
        """Test the process_scraped_texts function."""
        from src.text.normalizer import process_scraped_texts
        
        # Create a custom output directory
        output_dir = str(self.test_dir / "custom_processed")
        
        # Process the test directory
        stats = process_scraped_texts(str(self.test_dir), output_dir=output_dir)
        
        # Check that the files were processed
        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(stats["processed_files"], 2)
        self.assertEqual(len(stats["failed_files"]), 0)
        
        # Check that the backup file was created
        backup_file = self.text_file.with_suffix('.txt.bak')
        self.assertTrue(backup_file.exists())
        
        # Check that the original file was NOT updated (preserved)
        with open(self.text_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, "Phone: 123-456-7890 with unicode: é, ü, ñ")
        
        # Check that the processed file was created with normalized content
        timestamp = self.test_dir.name
        processed_file = Path(output_dir) / timestamp / "pages" / "example_com" / "text.txt"
        self.assertTrue(processed_file.exists())
        with open(processed_file, 'r', encoding='utf-8') as f:
            processed_content = f.read()
        self.assertEqual(processed_content, "Phone: 123 456 7890 with unicode: é, ü, ñ")

if __name__ == '__main__':
    unittest.main()