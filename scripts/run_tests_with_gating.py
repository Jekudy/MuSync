#!/usr/bin/env python3
"""
Test runner with gating mechanisms.

Runs tests with timeout protection and validates acceptance criteria.
Exits with appropriate codes for CI/CD integration.
"""

import argparse
import subprocess
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any


class TestGating:
    """Test gating with timeout and acceptance criteria validation."""

    def __init__(self, timeout: int = 300):
        """Initialize test gating."""
        self.timeout = timeout
        self.project_root = Path(__file__).parent.parent
        self.test_results = {}

    def run_tests_with_timeout(self, test_path: str = None) -> int:
        """Run tests with timeout protection."""
        cmd = [
            'python3', '-m', 'pytest',
            '--timeout', str(self.timeout),
            '--timeout-method', 'thread',
            '--cov=app',
            '--cov-report=term-missing',
            '--cov-report=html:htmlcov',
            '-v'
        ]
        
        if test_path:
            cmd.append(test_path)
        else:
            cmd.append('app/tests/')

        print(f"🚀 Running tests with timeout {self.timeout}s...")
        print(f"Command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                timeout=self.timeout + 30,  # Extra buffer
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"⏱️  Tests completed in {duration:.2f}s")
            print(f"Exit code: {result.returncode}")
            
            if result.stdout:
                print("📋 Test output:")
                print(result.stdout)
            
            if result.stderr:
                print("⚠️  Test errors:")
                print(result.stderr)
            
            return result.returncode
            
        except subprocess.TimeoutExpired:
            print(f"⏰ Tests timed out after {self.timeout}s")
            return 124
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return 1

    def validate_acceptance_criteria(self) -> bool:
        """Validate acceptance criteria from test results."""
        print("🔍 Validating acceptance criteria...")
        
        # Check if acceptance data exists
        acceptance_file = self.project_root / 'acceptance' / 'acceptance_data.json'
        if not acceptance_file.exists():
            print("⚠️  Acceptance data file not found")
            return False
        
        # Run E2E tests specifically
        e2e_result = self.run_e2e_tests()
        if e2e_result != 0:
            print("❌ E2E tests failed")
            return False
        
        print("✅ Acceptance criteria validation passed")
        return True

    def run_e2e_tests(self) -> int:
        """Run E2E tests specifically."""
        print("🧪 Running E2E tests...")
        
        cmd = [
            'python3', '-m', 'pytest',
            'app/tests/e2e/test_simple_e2e.py',
            '-v',
            '--timeout', '120'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                timeout=150,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                print("✅ E2E tests passed")
            else:
                print("❌ E2E tests failed")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            
            return result.returncode
            
        except subprocess.TimeoutExpired:
            print("⏰ E2E tests timed out")
            return 124
        except Exception as e:
            print(f"❌ Error running E2E tests: {e}")
            return 1

    def check_coverage_threshold(self, threshold: int = 80) -> bool:
        """Check if test coverage meets threshold."""
        print(f"📊 Checking coverage threshold ({threshold}%)...")
        
        cmd = [
            'python3', '-m', 'pytest',
            '--cov=app',
            '--cov-report=term-missing',
            '--cov-fail-under', str(threshold),
            'app/tests/'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                timeout=300,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                print(f"✅ Coverage threshold met ({threshold}%)")
                return True
            else:
                print(f"❌ Coverage threshold not met ({threshold}%)")
                if result.stdout:
                    print(result.stdout)
                return False
                
        except Exception as e:
            print(f"❌ Error checking coverage: {e}")
            return False

    def run_with_gating(self, 
                       check_acceptance: bool = True,
                       check_coverage: bool = True,
                       coverage_threshold: int = 80) -> int:
        """Run tests with full gating validation."""
        print("🎯 Running tests with gating validation...")
        
        # Step 1: Run all tests
        test_result = self.run_tests_with_timeout()
        if test_result != 0:
            print(f"❌ Tests failed with exit code {test_result}")
            return test_result
        
        # Step 2: Check coverage threshold
        if check_coverage:
            if not self.check_coverage_threshold(coverage_threshold):
                print("❌ Coverage threshold not met")
                return 1
        
        # Step 3: Validate acceptance criteria
        if check_acceptance:
            if not self.validate_acceptance_criteria():
                print("❌ Acceptance criteria validation failed")
                return 1
        
        print("🎉 All gating checks passed!")
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run tests with gating")
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Timeout in seconds for test execution (default: 300)'
    )
    parser.add_argument(
        '--no-acceptance',
        action='store_true',
        help='Skip acceptance criteria validation'
    )
    parser.add_argument(
        '--no-coverage',
        action='store_true',
        help='Skip coverage threshold check'
    )
    parser.add_argument(
        '--coverage-threshold',
        type=int,
        default=80,
        help='Coverage threshold percentage (default: 80)'
    )
    parser.add_argument(
        '--test-path',
        help='Specific test path to run'
    )
    
    args = parser.parse_args()
    
    gating = TestGating(timeout=args.timeout)
    
    exit_code = gating.run_with_gating(
        check_acceptance=not args.no_acceptance,
        check_coverage=not args.no_coverage,
        coverage_threshold=args.coverage_threshold
    )
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
