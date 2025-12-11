"""
Test utilities and base classes for MyNet Chat API tests
"""

import requests
import uuid
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import random
import string

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "https://localhost/api"


# ============================================================================
# TEST UTILITIES
# ============================================================================

@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration: float


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class TestRunner:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        # Disable SSL verification for self-signed certificates (local dev only)
        self.session.verify = False
        # Suppress InsecureRequestWarning
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.results: list[TestResult] = []
        self.access_token: Optional[str] = None
        self.csrf_token: Optional[str] = None
        self.test_user_id: Optional[str] = None
        self.test_username: Optional[str] = None
        self.test_email: Optional[str] = None
        self.authenticated: bool = False
        
    def print_header(self, title: str):
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{title:^60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")
        
    def print_phase(self, title: str):
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'#' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}{'#'} {title:^56} {'#'}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}{'#' * 60}{Colors.RESET}\n")
        
    def print_test_result(self, result: TestResult):
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if result.passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"  {status} {result.name} ({result.duration:.3f}s)")
        if not result.passed:
            print(f"       {Colors.YELLOW}{result.message}{Colors.RESET}")
            
    def add_result(self, name: str, passed: bool, message: str, duration: float):
        result = TestResult(name, passed, message, duration)
        self.results.append(result)
        self.print_test_result(result)
        
    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with authentication token"""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        return headers
        
    def make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        auth: bool = False,
        expected_status: Optional[int] = None
    ) -> Tuple[int, Any]:
        """Make HTTP request and return status code and response data"""
        url = f"{self.base_url}{endpoint}"
        headers = self.get_auth_headers() if auth else {"Content-Type": "application/json"}
        
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, allow_redirects=False)
            elif method == "POST":
                response = self.session.post(url, json=data, headers=headers)
            elif method == "PUT":
                response = self.session.put(url, json=data, headers=headers)
            elif method == "DELETE":
                response = self.session.delete(url, headers=headers)
            else:
                return 0, {"error": f"Unknown method: {method}"}
                
            try:
                return response.status_code, response.json()
            except:
                return response.status_code, {"raw": response.text}
        except requests.exceptions.ConnectionError:
            return 0, {"error": "Connection refused - is the server running?"}
        except Exception as e:
            return 0, {"error": str(e)}
    
    def truncate_response(self, data: Any, max_len: int = 200) -> str:
        """Safely truncate response data for display"""
        text = str(data)
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text


# ============================================================================
# INTERACTIVE AUTHENTICATION
# ============================================================================

def interactive_setup(runner: TestRunner) -> bool:
    """Interactive setup to get test user credentials"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'INTERACTIVE TEST SETUP':^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")
    
    print(f"{Colors.YELLOW}This test suite requires a valid user account to test")
    print(f"authenticated endpoints. You can either:")
    print(f"  1. Register a new user (requires email verification)")
    print(f"  2. Login with an existing user{Colors.RESET}\n")
    
    while True:
        choice = input(f"{Colors.CYAN}Choose option (1=Register, 2=Login, s=Skip auth tests): {Colors.RESET}").strip().lower()
        
        if choice == 's':
            print(f"\n{Colors.YELLOW}Skipping authenticated tests.{Colors.RESET}")
            return False
            
        if choice == '1':
            return interactive_register(runner)
        elif choice == '2':
            return interactive_login(runner)
        else:
            print(f"{Colors.RED}Invalid choice. Please enter 1, 2, or s.{Colors.RESET}")


def interactive_register(runner: TestRunner) -> bool:
    """Interactive registration flow"""
    print(f"\n{Colors.CYAN}--- New User Registration ---{Colors.RESET}\n")
    
    # Get user details
    username = random_string = ''.join(random.choice(string.ascii_letters) for i in range(10))
    email = input(f"Enter email (must be valid, you'll receive a code): ").strip()
    password = "TestPass123!"
    
    # Attempt registration
    print(f"\n{Colors.YELLOW}Registering user...{Colors.RESET}")
    status, data = runner.make_request("POST", "/register", {
        "username": username,
        "password": password,
        "email": email
    })
    
    if status != 200 or data.get("status") != "pending_verification":
        print(f"{Colors.RED}Registration failed: {data}{Colors.RESET}")
        return False
    
    runner.test_user_id = data.get("user_id")
    runner.test_username = username
    runner.test_email = email
    
    print(f"{Colors.GREEN}Registration successful! Check your email for the verification code.{Colors.RESET}")
    print(f"User ID: {runner.test_user_id}")
    
    # Get verification code
    while True:
        code = input(f"\nEnter 6-digit verification code (or 'q' to quit): ").strip()
        if code.lower() == 'q':
            return False
            
        if len(code) != 6 or not code.isdigit():
            print(f"{Colors.RED}Code must be exactly 6 digits.{Colors.RESET}")
            continue
        
        # Verify email
        print(f"{Colors.YELLOW}Verifying email...{Colors.RESET}")
        status, data = runner.make_request("POST", "/verify-email", {
            "user_id": runner.test_user_id,
            "verification_code": code
        })
        
        if status == 200:
            runner.access_token = data.get("access_token")
            runner.csrf_token = data.get("csrf_token")
            runner.authenticated = True
            print(f"{Colors.GREEN}Email verified and logged in successfully!{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}Verification failed: {data}{Colors.RESET}")
            retry = input("Try again? (y/n): ").strip().lower()
            if retry != 'y':
                return False


def interactive_login(runner: TestRunner) -> bool:
    """Interactive login flow"""
    print(f"\n{Colors.CYAN}--- User Login ---{Colors.RESET}\n")
    
    username = input(f"Enter username: ").strip()
    password = input(f"Enter password: ").strip()
    
    # Check if 2FA is needed
    print(f"\n{Colors.YELLOW}Logging in...{Colors.RESET}")
    status, data = runner.make_request("POST", "/login", {
        "username": username,
        "password": password
    })
    
    # Handle 2FA required case
    if status == 200 and data.get("requires_2fa"):
        print(f"{Colors.YELLOW}2FA is enabled. Please enter your authenticator code.{Colors.RESET}")
        totp = input(f"Enter 6-digit 2FA code: ").strip()
        
        status, data = runner.make_request("POST", "/login", {
            "username": username,
            "password": password,
            "totp_token": totp
        })
    
    if status == 200 and data.get("access_token"):
        runner.access_token = data.get("access_token")
        runner.csrf_token = data.get("csrf_token")
        runner.test_user_id = data.get("id")
        runner.test_username = data.get("username")
        runner.test_email = data.get("email")
        runner.authenticated = True
        print(f"{Colors.GREEN}Login successful!{Colors.RESET}")
        return True
    else:
        print(f"{Colors.RED}Login failed: {data}{Colors.RESET}")
        return False
