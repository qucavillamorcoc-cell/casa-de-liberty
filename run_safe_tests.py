#!/usr/bin/env python
"""
Safe test runner with automatic database backup.
Usage: python run_safe_tests.py [test_path] [options]
Examples:
  python run_safe_tests.py                          # Run all tests
  python run_safe_tests.py core.tests               # Run core app tests
  python run_safe_tests.py core.tests.DashboardViewTests  # Run specific test class
"""
import subprocess
import sys
import os
from backup_db import backup

def run_safe_tests():
    """Backup database, then run Django tests."""
    # Backup production database first
    print("=" * 60)
    print("SAFE TEST RUNNER - Protecting your production database")
    print("=" * 60)
    
    if not backup():
        print("\n✗ Backup failed. Aborting tests to protect your data.")
        sys.exit(1)
    
    print("\n✓ Database backed up successfully.")
    print("Proceeding with tests...\n")
    
    # Build test command
    cmd = [sys.executable, 'manage.py', 'test', '--keepdb']
    
    # Add any additional arguments passed by user
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    print(f"Running: {' '.join(cmd)}\n")
    
    # Run tests
    result = subprocess.run(cmd)
    
    print("\n" + "=" * 60)
    if result.returncode == 0:
        print("✓ Tests passed!")
    else:
        print(f"✗ Tests failed with exit code {result.returncode}")
        print("\nTo restore your database, run:")
        print("  python backup_db.py restore")
    print("=" * 60)
    
    sys.exit(result.returncode)

if __name__ == '__main__':
    run_safe_tests()
