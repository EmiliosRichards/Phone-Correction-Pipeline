"""
Tests for the analysis module.
"""
import sys
import os
import unittest
import json
import tempfile
import pytest
from pathlib import Path
from collections import defaultdict

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.statistics import generate_statistics, save_results

class TestAnalysis(unittest.TestCase):
    """Test cases for the analysis module."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample extraction results
        self.sample_results = [
            {
                "website": "example_com",
                "numbers": [
                    {
                        "format": "international",
                        "original": "+1 (234) 567-8900",
                        "cleaned": "+12345678900",
                        "formatted": "+1 234 567 8900"
                    },
                    {
                        "format": "local",
                        "original": "(234) 567-8901",
                        "cleaned": "2345678901",
                        "formatted": "(234) 567-8901"
                    }
                ]
            },
            {
                "website": "example_org",
                "numbers": [
                    {
                        "format": "german",
                        "original": "+49 (0) 123 456789",
                        "cleaned": "+49(0)123456789",
                        "formatted": "+49 123 456789"
                    }
                ]
            },
            {
                "website": "example_net",
                "numbers": []
            },
            {
                "website": "example_de",
                "numbers": [
                    {
                        "format": "german",
                        "original": "+49 (0) 987 654321",
                        "cleaned": "+49(0)987654321",
                        "formatted": "+49 987 654321"
                    }
                ]
            }
        ]
        
        # Create a temporary directory for test output
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
    
    def test_generate_statistics(self):
        """Test the generate_statistics function."""
        # Generate statistics from sample results
        stats = generate_statistics(self.sample_results)
        
        # Check basic statistics
        self.assertEqual(stats['total_websites'], 4)
        self.assertEqual(stats['websites_with_numbers'], 3)
        self.assertEqual(stats['total_numbers_found'], 4)
        
        # Check format counts
        self.assertEqual(stats['format_counts']['international'], 1)
        self.assertEqual(stats['format_counts']['local'], 1)
        self.assertEqual(stats['format_counts']['german'], 2)
        
        # Check country codes
        self.assertEqual(stats['country_codes']['1'], 1)
        self.assertEqual(stats['country_codes']['49'], 2)
    
    def test_save_results(self):
        """Test the save_results function."""
        # Generate statistics from sample results
        stats = generate_statistics(self.sample_results)
        
        # Save results to temporary directory
        timestamp = "20250512_000000"
        output_dir = os.path.join(self.test_dir, "custom_results")
        output_files = save_results(stats, timestamp, output_dir=output_dir)
        
        # Check that output files were created
        for file_path in output_files.values():
            self.assertTrue(Path(file_path).exists())
        
        # Check JSON file content
        with open(output_files['json'], 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        self.assertEqual(json_data['total_websites'], 4)
        self.assertEqual(json_data['websites_with_numbers'], 3)
        self.assertEqual(json_data['total_numbers_found'], 4)
        
        # Check text file content
        with open(output_files['text'], 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        self.assertIn("example_com", text_content)
        self.assertIn("+1 234 567 8900", text_content)
        self.assertIn("example_org", text_content)
        self.assertIn("+49 123 456789", text_content)
        
        # Check stats file content
        with open(output_files['stats'], 'r', encoding='utf-8') as f:
            stats_data = json.load(f)
        
        self.assertEqual(stats_data['total_websites'], 4)
        self.assertEqual(stats_data['websites_with_numbers'], 3)
        self.assertEqual(stats_data['total_numbers_found'], 4)
        self.assertNotIn('results', stats_data)

if __name__ == '__main__':
    unittest.main()