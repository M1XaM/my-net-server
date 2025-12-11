"""
Tests for google_auth.py router endpoints:
- GET /auth/google/url
- POST /auth/google/callback
"""

import time

from utils import TestRunner, Colors


def test_google_oauth_url(runner: TestRunner):
    """Test Google OAuth URL generation"""
    runner.print_header("GOOGLE AUTH ENDPOINT TESTS")
    
    start = time.time()
    status, data = runner.make_request("GET", "/auth/google/url")
    duration = time.time() - start
    
    passed = status in [302, 500]
    runner.add_result(
        "GET /auth/google/url - Returns redirect or config error",
        passed,
        f"Status: {status}, Response: {runner.truncate_response(data)}",
        duration
    )


def test_google_callback_validation(runner: TestRunner):
    """Test Google OAuth callback validation"""
    
    test_cases = [
        (
            "Empty code",
            {"code": "", "state": "valid_state"},
            400,
            "code"
        ),
        (
            "Empty state",
            {"code": "valid_code", "state": ""},
            400,
            "state"
        ),
        (
            "Missing code field",
            {"state": "valid_state"},
            422,
            None
        ),
        (
            "Missing state field",
            {"code": "valid_code"},
            422,
            None
        ),
        (
            "Invalid authorization code",
            {"code": "invalid_authorization_code", "state": "some_state_value"},
            [400, 401, 500],
            None
        ),
    ]
    
    for test_name, data, expected_status, expected_error in test_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/auth/google/callback", data)
        duration = time.time() - start
        
        if isinstance(expected_status, list):
            passed = status in expected_status
        else:
            passed = status == expected_status
        if expected_error:
            passed = passed and expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /auth/google/callback - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )


# ============================================================================
# RUN ALL GOOGLE AUTH TESTS
# ============================================================================

def run_unauthenticated_tests(runner: TestRunner):
    """Run all unauthenticated Google auth tests"""
    test_google_oauth_url(runner)
    test_google_callback_validation(runner)


def run_authenticated_tests(runner: TestRunner):
    """Run all authenticated Google auth tests (none currently)"""
    pass
