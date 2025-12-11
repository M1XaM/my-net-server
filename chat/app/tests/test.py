#!/usr/bin/env python3
"""
Comprehensive API Test Suite for MyNet Chat API

Run with: python3 test.py

Make sure the API server is running before executing tests.
Default API URL: https://localhost/api

This test suite runs in two phases:
1. Unauthenticated tests (stranger) - tests validation and auth endpoints
2. Authenticated tests (logged in user) - tests protected endpoints

Test modules:
- test_auth.py: Authentication endpoints (register, login, logout, token refresh)
- test_users.py: Users endpoint
- test_messages.py: Messages and run-code endpoints
- test_google_auth.py: Google OAuth endpoints
- test_two_factor.py: 2FA endpoints
"""

import sys

from utils import TestRunner, Colors, interactive_setup, BASE_URL

# Import test modules
import test_auth
import test_users
import test_messages
import test_google_auth
import test_two_factor


# ============================================================================
# TEST RUNNER
# ============================================================================

def print_summary(runner: TestRunner):
    """Print test summary"""
    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.passed)
    failed = total - passed
    
    runner.print_header("TEST SUMMARY")
    
    print(f"  Total Tests:  {total}")
    print(f"  {Colors.GREEN}Passed:       {passed}{Colors.RESET}")
    print(f"  {Colors.RED}Failed:       {failed}{Colors.RESET}")
    print(f"  Pass Rate:    {(passed/total*100):.1f}%" if total > 0 else "  Pass Rate:    N/A")
    
    if failed > 0:
        print(f"\n{Colors.RED}Failed Tests:{Colors.RESET}")
        for result in runner.results:
            if not result.passed:
                print(f"  - {result.name}")
                
    print()


def main():
    """Main entry point"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          MyNet Chat API - Test Suite                     ║")
    print("║          Running against: " + BASE_URL.ljust(31) + "║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    
    runner = TestRunner(BASE_URL)
    
    # Check if server is running
    print(f"{Colors.YELLOW}Checking if server is running...{Colors.RESET}")
    status, data = runner.make_request("GET", "/health")
    if status == 0:
        print(f"\n{Colors.RED}ERROR: Cannot connect to server at {BASE_URL}")
        print(f"Make sure the API server is running.{Colors.RESET}\n")
        sys.exit(1)
    print(f"{Colors.GREEN}Server is running!{Colors.RESET}")
    
    try:
        # ================================================================
        # PHASE 1: UNAUTHENTICATED TESTS
        # ================================================================
        runner.print_phase("PHASE 1: UNAUTHENTICATED TESTS (STRANGER)")
        
        test_auth.run_unauthenticated_tests(runner)
        test_users.run_unauthenticated_tests(runner)
        test_messages.run_unauthenticated_tests(runner)
        test_google_auth.run_unauthenticated_tests(runner)
        test_two_factor.run_unauthenticated_tests(runner)
        
        # ================================================================
        # INTERACTIVE AUTHENTICATION
        # ================================================================
        authenticated = interactive_setup(runner)
        
        # ================================================================
        # PHASE 2: AUTHENTICATED TESTS
        # ================================================================
        if authenticated:
            runner.print_phase("PHASE 2: AUTHENTICATED TESTS (LOGGED IN)")
            
            test_auth.run_authenticated_tests(runner)
            test_users.run_authenticated_tests(runner)
            test_messages.run_authenticated_tests(runner)
            test_google_auth.run_authenticated_tests(runner)
            test_two_factor.run_authenticated_tests(runner)
        else:
            print(f"\n{Colors.YELLOW}Skipping Phase 2 (authenticated tests).{Colors.RESET}")
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test run interrupted by user.{Colors.RESET}")
    except Exception as e:
        import traceback
        print(f"\n\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        traceback.print_exc()
    
    # Print summary
    print_summary(runner)
    
    # Exit with appropriate code
    failed = sum(1 for r in runner.results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
