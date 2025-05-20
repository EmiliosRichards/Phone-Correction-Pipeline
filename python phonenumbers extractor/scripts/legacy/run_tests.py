#!/usr/bin/env python3
"""
Script to run tests with proper environment setup.
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path

def run_tests(args):
    """Run tests with proper environment setup."""
    # Create temporary test directories if they don't exist
    test_output_dir = Path(".test_output")
    test_output_dir.mkdir(exist_ok=True)
    
    results_dir = test_output_dir / "results"
    processed_dir = test_output_dir / "processed"
    
    results_dir.mkdir(exist_ok=True)
    processed_dir.mkdir(exist_ok=True)
    
    # Set environment variables
    os.environ['RESULTS_DIR'] = str(results_dir)
    os.environ['PROCESSED_DIR'] = str(processed_dir)
    
    # Build the pytest command
    cmd = ["pytest"]
    
    if args.verbose:
        cmd.append("-v")
        
    if args.test_file:
        cmd.append(args.test_file)
    
    # Run the tests
    result = subprocess.run(cmd)
    
    # Clean up if requested
    if args.cleanup:
        import shutil
        shutil.rmtree(test_output_dir)
        print(f"Cleaned up test output directory: {test_output_dir}")
    
    return result.returncode

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run tests with proper environment setup.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Run tests in verbose mode')
    parser.add_argument('--cleanup', '-c', action='store_true', help='Clean up test output directory after tests')
    parser.add_argument('test_file', nargs='?', help='Specific test file to run')
    args = parser.parse_args()
    
    sys.exit(run_tests(args))

if __name__ == "__main__":
    main()