#!/usr/bin/env python3
"""
Test runner for the distributed chat application.
This script runs all the tests for the application.
"""
import os
import sys
import unittest
import argparse
from pathlib import Path

def discover_and_run_tests(test_type=None, test_pattern=None):
    """Discover and run tests based on type and pattern."""
    loader = unittest.TestLoader()
    
    # Determine the test directory based on test type
    if test_type == 'unit':
        test_dir = Path(__file__).parent / 'unit'
    elif test_type == 'integration':
        test_dir = Path(__file__).parent / 'integration'
    else:
        test_dir = Path(__file__).parent
    
    # Apply pattern if specified
    if test_pattern:
        pattern = f'test_{test_pattern}.py'
    else:
        pattern = 'test_*.py'
    
    # Discover tests
    suite = loader.discover(str(test_dir), pattern=pattern)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return 0 if all tests passed, 1 otherwise
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run tests for the distributed chat application.')
    parser.add_argument('--type', choices=['all', 'unit', 'integration'], 
                        default='all', help='Type of tests to run')
    parser.add_argument('--pattern', type=str, help='Pattern to match test files (without test_ prefix)')
    args = parser.parse_args()
    
    sys.exit(discover_and_run_tests(args.type, args.pattern))
