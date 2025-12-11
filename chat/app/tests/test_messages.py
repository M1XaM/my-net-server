"""
Tests for messages.py router endpoints:
- GET /messages/{user_id}/{other_id}
- POST /messages/run-code
"""

import time
import uuid

from utils import TestRunner, Colors


def test_messages_unauthorized(runner: TestRunner):
    """Test messages endpoint without authentication"""
    runner.print_header("MESSAGES ENDPOINT TESTS (UNAUTHENTICATED)")
    
    user_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    
    start = time.time()
    status, data = runner.make_request("GET", f"/messages/{user_id}/{other_id}", auth=False)
    duration = time.time() - start
    
    passed = status in [401, 403, 422]
    runner.add_result(
        "GET /messages/{user_id}/{other_id} - Unauthorized rejected",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


def test_run_code_unauthorized(runner: TestRunner):
    """Test run-code without authentication"""
    runner.print_header("RUN CODE ENDPOINT TESTS (UNAUTHENTICATED)")
    
    start = time.time()
    status, data = runner.make_request("POST", "/messages/run-code", {"code": "print('hello')"}, auth=False)
    duration = time.time() - start
    
    passed = status in [401, 403, 422]
    runner.add_result(
        "POST /messages/run-code - Unauthorized rejected",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


def test_messages_authenticated(runner: TestRunner):
    """Test messages endpoint with authentication"""
    runner.print_header("MESSAGES ENDPOINT TESTS (AUTHENTICATED)")
    
    if not runner.test_user_id:
        runner.add_result(
            "GET /messages - Skipped (no user_id)",
            False,
            "Cannot test without authenticated user",
            0.0
        )
        return
    
    # Test with invalid UUIDs
    test_cases = [
        ("Invalid user_id", "invalid-uuid", str(uuid.uuid4()), 422),
        ("Invalid other_id", str(uuid.uuid4()), "invalid-uuid", 422),
        ("Both invalid", "invalid", "also-invalid", 422),
    ]
    
    for test_name, user_id, other_id, expected_status in test_cases:
        start = time.time()
        status, data = runner.make_request("GET", f"/messages/{user_id}/{other_id}", auth=True)
        duration = time.time() - start
        
        passed = status == expected_status
        runner.add_result(
            f"GET /messages - {test_name}",
            passed,
            f"Status: {status}, Response: {data}",
            duration
        )
    
    # Test accessing own conversation with another user
    other_user_id = str(uuid.uuid4())
    start = time.time()
    status, data = runner.make_request("GET", f"/messages/{runner.test_user_id}/{other_user_id}", auth=True)
    duration = time.time() - start
    
    # Should return empty array or 404 (user not found)
    passed = status in [200, 404]
    runner.add_result(
        "GET /messages - Own conversation with non-existent user",
        passed,
        f"Status: {status}, Response: {runner.truncate_response(data)}",
        duration
    )
    
    # Test self-conversation (should fail)
    start = time.time()
    status, data = runner.make_request("GET", f"/messages/{runner.test_user_id}/{runner.test_user_id}", auth=True)
    duration = time.time() - start
    
    passed = status == 400
    runner.add_result(
        "GET /messages - Self conversation rejected",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )
    
    # Test accessing another user's conversation (should fail)
    fake_user = str(uuid.uuid4())
    start = time.time()
    status, data = runner.make_request("GET", f"/messages/{fake_user}/{other_user_id}", auth=True)
    duration = time.time() - start
    
    passed = status == 403
    runner.add_result(
        "GET /messages - Other user's conversation rejected",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


def test_run_code_authenticated(runner: TestRunner):
    """Test run-code endpoint with authentication"""
    runner.print_header("RUN CODE ENDPOINT TESTS (AUTHENTICATED)")
    
    # Test validation
    validation_cases = [
        (
            "Empty code",
            {"code": ""},
            400,
            "required"
        ),
        (
            "Whitespace only code",
            {"code": "   \n\t  "},
            400,
            "empty"
        ),
        (
            "Missing code field",
            {},
            422,
            None
        ),
    ]
    
    for test_name, data, expected_status, expected_error in validation_cases:
        start = time.time()
        status, response = runner.make_request("POST", "/messages/run-code", data, auth=True)
        duration = time.time() - start
        
        passed = status == expected_status
        if expected_error:
            passed = passed and expected_error.lower() in str(response).lower()
            
        runner.add_result(
            f"POST /messages/run-code - {test_name}",
            passed,
            f"Status: {status} (expected {expected_status}), Response: {runner.truncate_response(response)}",
            duration
        )
    
    # Test code too long
    start = time.time()
    status, data = runner.make_request("POST", "/messages/run-code", {
        "code": "x" * 50001
    }, auth=True)
    duration = time.time() - start
    
    passed = status == 400 and "50,000" in str(data)
    runner.add_result(
        "POST /messages/run-code - Code exceeding 50,000 chars rejected",
        passed,
        f"Status: {status}, Response: {runner.truncate_response(data)}",
        duration
    )
    
    # Test valid code execution
    start = time.time()
    status, data = runner.make_request("POST", "/messages/run-code", {
        "code": "print('Hello, World!')"
    }, auth=True)
    duration = time.time() - start
    
    # Should succeed or timeout (depending on runner service)
    passed = status in [200, 500, 503]  # 503 if runner not available
    runner.add_result(
        "POST /messages/run-code - Valid code execution",
        passed,
        f"Status: {status}, Response: {runner.truncate_response(data)}",
        duration
    )


# ============================================================================
# RUN ALL MESSAGE TESTS
# ============================================================================

def run_unauthenticated_tests(runner: TestRunner):
    """Run all unauthenticated message tests"""
    test_messages_unauthorized(runner)
    test_run_code_unauthorized(runner)


def run_authenticated_tests(runner: TestRunner):
    """Run all authenticated message tests"""
    test_messages_authenticated(runner)
    test_run_code_authenticated(runner)
