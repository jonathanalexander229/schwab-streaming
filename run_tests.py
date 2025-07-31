#!/usr/bin/env python3
"""
Simple test runner script for CI/CD
"""

import sys
import os

def main():
    """Run basic tests for CI/CD"""
    print("🚀 Starting basic test suite...")
    
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from test_integration import FlaskAppTester
        
        tester = FlaskAppTester()
        success = tester.run_basic_tests()
        
        if success:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()