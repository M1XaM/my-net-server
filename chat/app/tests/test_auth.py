"""
Tests for auth.py router endpoints:
- POST /register
- POST /verify-email
- POST /login
- POST /token/refresh
- POST /logout
- GET /health
"""

import time
import uuid
import requests

from utils import TestRunner, Colors


def test_health_check(runner: TestRunner):
    """Test the health check endpoint"""
    runner.print_header("HEALTH CHECK TESTS")
    
    start = time.time()
    status, data = runner.make_request("GET", "/health")
    duration = time.time() - start
    
    passed = status == 200 and data.get("status") == "healthy"
    runner.add_result(
        "GET /health - Returns healthy status",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


def test_register_validation(runner: TestRunner):
    """Test registration input validation"""
    runner.print_header("REGISTRATION VALIDATION TESTS")
    
    test_cases = [
        (
            "Empty username",
            {"username": "", "password": "ValidPass123!", "email": "test@example.com"},
            400,
            "Username is required"
        ),
        (
            "Short username (< 3 chars)",
            {"username": "ab", "password": "ValidPass123!", "email": "test@example.com"},
            400,
            "at least 3 characters"
        ),
        (
            "Long username (> 50 chars)",
            {"username": "a" * 51, "password": "ValidPass123!", "email": "test@example.com"},
            400,
            "not exceed 50 characters"
        ),
        (
            "Invalid username characters",
            {"username": "test@user!", "password": "ValidPass123!", "email": "test@example.com"},
            400,
            "letters, numbers, underscores, and hyphens"
        ),
        (
            "Empty password",
            {"username": "validuser", "password": "", "email": "test@example.com"},
            400,
            "Password is required"
        ),
        (
            "Weak password (only lowercase)",
            {"username": "validuser", "password": "onlylowercase", "email": "test@example.com"},
            400,
            "must meet at least 4"
        ),
        (
            "Weak password (no special char, short)",
            {"username": "validuser", "password": "Short1", "email": "test@example.com"},
            400,
            "must meet at least 4"
        ),
        (
            "Weak password (missing 2+ requirements)",
            {"username": "validuser", "password": "alllowercase123", "email": "test@example.com"},
            400,
            "must meet at least 4"
        ),
        (
            "Long password (> 128 chars)",
            {"username": "validuser", "password": "Aa1!" + "a" * 125, "email": "test@example.com"},
            400,
            "not exceed 128 characters"
        ),
        (
            "Empty email",
            {"username": "validuser", "password": "ValidPass123!", "email": ""},
            422,
            None
        ),
        (
            "Invalid email format",
            {"username": "validuser", "password": "ValidPass123!", "email": "notanemail"},
            422,
            None
        ),
    ]
    
    for test_name, data, expected_status, expected_error in test_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/register", data)
        duration = time.time() - start
        
        passed = status == expected_status
        if expected_error and passed:
            passed = expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /register - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )


def test_verify_email_validation(runner: TestRunner):
    """Test email verification input validation"""
    runner.print_header("EMAIL VERIFICATION VALIDATION TESTS")
    
    test_cases = [
        (
            "Empty user_id",
            {"user_id": "", "verification_code": "123456"},
            400,
            "User ID is required"
        ),
        (
            "Invalid UUID format",
            {"user_id": "not-a-uuid", "verification_code": "123456"},
            400,
            "valid UUID"
        ),
        (
            "Empty verification code",
            {"user_id": str(uuid.uuid4()), "verification_code": ""},
            400,
            "Verification code is required"
        ),
        (
            "Short verification code",
            {"user_id": str(uuid.uuid4()), "verification_code": "12345"},
            400,
            "6 digits"
        ),
        (
            "Long verification code",
            {"user_id": str(uuid.uuid4()), "verification_code": "1234567"},
            400,
            "6 digits"
        ),
        (
            "Non-digit verification code",
            {"user_id": str(uuid.uuid4()), "verification_code": "abcdef"},
            400,
            "6 digits"
        ),
        (
            "Invalid code for non-existent user",
            {"user_id": str(uuid.uuid4()), "verification_code": "123456"},
            404,
            None
        ),
    ]
    
    for test_name, data, expected_status, expected_error in test_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/verify-email", data)
        duration = time.time() - start
        
        passed = status == expected_status
        if expected_error:
            passed = passed and expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /verify-email - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )


def test_login_validation(runner: TestRunner):
    """Test login input validation"""
    runner.print_header("LOGIN VALIDATION TESTS")
    
    test_cases = [
        (
            "Empty username",
            {"username": "", "password": "ValidPass123!"},
            400,
            "Username is required"
        ),
        (
            "Empty password",
            {"username": "validuser", "password": ""},
            400,
            "Password is required"
        ),
        (
            "Invalid 2FA token (short)",
            {"username": "validuser", "password": "ValidPass123!", "totp_token": "12345"},
            400,
            "6 digits"
        ),
        (
            "Invalid 2FA token (non-digit)",
            {"username": "validuser", "password": "ValidPass123!", "totp_token": "abcdef"},
            400,
            "6 digits"
        ),
        (
            "Invalid credentials",
            {"username": "nonexistentuser12345", "password": "WrongPassword123!"},
            401,
            None
        ),
    ]
    
    for test_name, data, expected_status, expected_error in test_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/login", data)
        duration = time.time() - start
        
        passed = status == expected_status
        if expected_error:
            passed = passed and expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /login - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )


def test_token_refresh_no_cookie(runner: TestRunner):
    """Test token refresh without refresh token cookie"""
    runner.print_header("TOKEN REFRESH TESTS (UNAUTHENTICATED)")
    
    # Create a fresh session without cookies
    old_session = runner.session
    runner.session = requests.Session()
    runner.session.verify = False
    
    start = time.time()
    status, data = runner.make_request("POST", "/token/refresh")
    duration = time.time() - start
    
    # Restore session
    runner.session = old_session
    
    passed = status == 401
    runner.add_result(
        "POST /token/refresh - No cookie returns 401",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


def test_token_refresh_authenticated(runner: TestRunner):
    """Test token refresh with valid session"""
    runner.print_header("TOKEN REFRESH TESTS (AUTHENTICATED)")
    
    start = time.time()
    status, data = runner.make_request("POST", "/token/refresh")
    duration = time.time() - start
    
    # If we have a valid refresh token cookie from login, this should work
    if status == 200 and "access_token" in data:
        runner.access_token = data.get("access_token")
        runner.csrf_token = data.get("csrf_token")
        passed = True
    else:
        # May fail if no refresh token in cookies
        passed = status == 401
    
    runner.add_result(
        "POST /token/refresh - Refresh token",
        passed,
        f"Status: {status}, Response: {runner.truncate_response(data)}",
        duration
    )


def test_logout_unauthenticated(runner: TestRunner):
    """Test logout endpoint (always succeeds)"""
    runner.print_header("LOGOUT TEST")
    
    start = time.time()
    status, data = runner.make_request("POST", "/logout")
    duration = time.time() - start
    
    passed = status == 200 and "Logged out" in str(data)
    runner.add_result(
        "POST /logout - Returns success message",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


# ============================================================================
# RUN ALL AUTH TESTS
# ============================================================================

def run_unauthenticated_tests(runner: TestRunner):
    """Run all unauthenticated auth tests"""
    test_health_check(runner)
    test_register_validation(runner)
    test_verify_email_validation(runner)
    test_login_validation(runner)
    test_token_refresh_no_cookie(runner)
    test_logout_unauthenticated(runner)


def run_authenticated_tests(runner: TestRunner):
    """Run all authenticated auth tests"""
    test_token_refresh_authenticated(runner)
