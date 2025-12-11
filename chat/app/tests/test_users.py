"""
Tests for users.py router endpoints:
- GET /users
"""

import time
import uuid

from utils import TestRunner, Colors


def test_users_unauthorized(runner: TestRunner):
    """Test users endpoint without authentication"""
    runner.print_header("USERS ENDPOINT TESTS (UNAUTHENTICATED)")
    
    start = time.time()
    status, data = runner.make_request("GET", "/users", auth=False)
    duration = time.time() - start
    
    passed = status in [401, 403, 422]
    runner.add_result(
        "GET /users - Unauthorized request rejected",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )
    
    # Test with invalid token
    old_token = runner.access_token
    runner.access_token = "invalid.token.here"
    
    start = time.time()
    status, data = runner.make_request("GET", "/users", auth=True)
    duration = time.time() - start
    
    runner.access_token = old_token
    
    passed = status in [401, 403, 422]
    runner.add_result(
        "GET /users - Invalid token rejected",
        passed,
        f"Status: {status}, Response: {data}",
        duration
    )


def test_users_authenticated(runner: TestRunner):
    """Test users endpoint with authentication"""
    runner.print_header("USERS ENDPOINT TESTS (AUTHENTICATED)")
    
    start = time.time()
    status, data = runner.make_request("GET", "/users", auth=True)
    duration = time.time() - start
    
    passed = status == 200 and isinstance(data, list)
    runner.add_result(
        "GET /users - Returns list of users",
        passed,
        f"Status: {status}, Response: {runner.truncate_response(data)}",
        duration
    )
    
    # Verify current user is in list
    if passed and runner.test_user_id:
        user_found = any(u.get("id") == runner.test_user_id for u in data)
        runner.add_result(
            "GET /users - Current user in list",
            user_found,
            f"Looking for user_id: {runner.test_user_id}",
            0.0
        )


# ============================================================================
# RUN ALL USER TESTS
# ============================================================================

def run_unauthenticated_tests(runner: TestRunner):
    """Run all unauthenticated user tests"""
    test_users_unauthorized(runner)


def run_authenticated_tests(runner: TestRunner):
    """Run all authenticated user tests"""
    test_users_authenticated(runner)
