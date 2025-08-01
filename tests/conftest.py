# tests/conftest.py
import pytest
from playwright.sync_api import Playwright, sync_playwright
from app import app as flask_app
import os

@pytest.fixture(scope='session')
def app():
    """Configure the Flask app for testing."""
    # Set testing configuration
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
    })
    
    # Set up any other test configuration here
    
    yield flask_app

@pytest.fixture(scope='session')
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()

@pytest.fixture(scope='session')
def base_url():
    """Return the base URL for the test server."""
    return "http://localhost:5000"

@pytest.fixture(scope='function')
def page(playwright: Playwright, base_url):
    """Create a new browser page for each test."""
    browser = playwright.chromium.launch(headless=True)  # Set to False to see the browser
    context = browser.new_context()
    page = context.new_page()
    
    yield page
    
    # Clean up
    context.close()
    browser.close()

@pytest.fixture(scope='session')
def playwright():
    with sync_playwright() as p:
        yield p
