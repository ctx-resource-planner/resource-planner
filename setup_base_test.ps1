# Create base test class
@"
# base_test.py
import os
import pytest
from playwright.sync_api import Page, expect
from test_config import TEST_CONFIG

class BaseTest:
    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        self.page = page
        self.base_url = TEST_CONFIG["base_url"]
        self.test_data = TEST_CONFIG["test_data"]
        
    def login(self, username=None, password=None):
        username = username or TEST_CONFIG["credentials"]["admin_user"]
        password = password or TEST_CONFIG["credentials"]["admin_pass"]
        
        self.page.goto(f"{self.base_url}/login")
        self.page.fill('input[name="username"]', username)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_selector('.dashboard')  # Update selector as needed
"@ | Out-File -FilePath "$testDir\base_test.py" -Encoding utf8

Write-Host "✅ Base test class created!" -ForegroundColor Green
Write-Host "Run the next script: .\setup_sample_tests.ps1"