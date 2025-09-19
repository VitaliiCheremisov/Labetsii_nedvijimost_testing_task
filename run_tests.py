#!/usr/bin/env python3
"""
Test runner script for the image processing project.
"""
import subprocess
import sys
from pathlib import Path


def run_command(command: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print('='*60)
    
    result = subprocess.run(command, capture_output=False)
    return result.returncode == 0


def main():
    """Main test runner function."""
    project_root = Path(__file__).parent
    
    # Change to project directory
    import os
    os.chdir(project_root)
    
    print("Image Processing Project - Test Runner")
    print("="*60)
    
    # Install dependencies
    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      "Installing dependencies"):
        print("Failed to install dependencies")
        return 1
    
    # Run unit tests
    if not run_command([sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short"], 
                      "Running unit tests"):
        print("Unit tests failed")
        return 1
    
    # Run all tests with coverage
    if not run_command([sys.executable, "-m", "pytest", "tests/", "--cov=app", "--cov-report=html", "--cov-report=term"], 
                      "Running all tests with coverage"):
        print("Tests with coverage failed")
        return 1
    
    print("\n" + "="*60)
    print("All tests completed successfully!")
    print("Coverage report generated in htmlcov/index.html")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
