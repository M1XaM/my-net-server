"""
Tests for two_factor.py router endpoints:
- POST /2fa/setup
- POST /2fa/enable
- POST /2fa/disable
"""

import time

from utils import TestRunner, Colors


def test_2fa_unauthorized(runner: TestRunner):
    """Test 2FA endpoints without authentication"""
    runner.print_header("TWO FACTOR AUTH TESTS (UNAUTHENTICATED)")
    
    endpoints = [
        ("POST", "/2fa/setup", None),
        ("POST", "/2fa/enable", {"token": "123456"}),
        ("POST", "/2fa/disable", {"token": "123456"}),
    ]
    
    for method, endpoint, data in endpoints:
        start = time.time()
        status, response = runner.make_request(method, endpoint, data, auth=False)
        duration = time.time() - start
        
        passed = status in [401, 403, 422]
        runner.add_result(
            f"{method} {endpoint} - Unauthorized rejected",
            passed,
            f"Status: {status}, Response: {response}",
            duration
        )


def test_2fa_authenticated(runner: TestRunner):
    """Test 2FA endpoints with authentication"""
    runner.print_header("TWO FACTOR AUTH TESTS (AUTHENTICATED)")
    
    # Test 2FA setup (should return QR code)
    start = time.time()
    status, data = runner.make_request("POST", "/2fa/setup", auth=True)
    duration = time.time() - start
    
    passed = status == 200 and ("qr_code" in data or "secret" in data)
    runner.add_result(
        "POST /2fa/setup - Returns QR code and secret",
        passed,
        f"Status: {status}, Response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}",
        duration
    )
    
    # Test 2FA enable validation
    validation_cases = [
        ("Empty token", {"token": ""}, 400, "required"),
        ("Short token", {"token": "12345"}, 400, "6 digits"),
        ("Long token", {"token": "1234567"}, 400, "6 digits"),
        ("Non-digit token", {"token": "abcdef"}, 400, "6 digits"),
    ]
    
    for test_name, data, expected_status, expected_error in validation_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/2fa/enable", data, auth=True)
        duration = time.time() - start
        
        passed = status == expected_status
        if expected_error:
            passed = passed and expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /2fa/enable - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )
    
    # Test 2FA disable validation
    for test_name, data, expected_status, expected_error in validation_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/2fa/disable", data, auth=True)
        duration = time.time() - start
        
        passed = status == expected_status
        if expected_error:
            passed = passed and expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /2fa/disable - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )


# ============================================================================
# RUN ALL 2FA TESTS
# ============================================================================

def run_unauthenticated_tests(runner: TestRunner):
    """Run all unauthenticated 2FA tests"""
    test_2fa_unauthorized(runner)


def run_authenticated_tests(runner: TestRunner):
    """Run all authenticated 2FA tests"""
    test_2fa_authenticated(runner)
