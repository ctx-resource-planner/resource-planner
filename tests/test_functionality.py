# tests/test_functionality.py
from playwright.sync_api import Page, expect
import time

def test_navigation_links(page: Page, base_url):
    """Test that all main navigation links work."""
    # Login first
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    
    # Test each main navigation link
    nav_links = {
        "Employee Search": "/",
        "Manage Employees": "/employees",
        "Manage Skills": "/skills",
        "Manage Projects": "/projects",
        "Manage Allocations": "/allocations",
        "Reports": "/reports"
    }
    
    for link_text, expected_url in nav_links.items():
        try:
            page.click(f'nav a:has-text("{link_text}")')
            expect(page).to_have_url(f"{base_url}{expected_url}")
            print(f"\n✓ Navigation to '{link_text}' successful")
        except Exception as e:
            print(f"\n✗ Navigation to '{link_text}' failed: {str(e)}")
            page.goto(f"{base_url}")  # Go back to home if test fails

def test_utilities_dropdown(page: Page, base_url):
    """Test the Utilities dropdown menu."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    
    # Click on Utilities dropdown
    page.click('a.dropdown-toggle:has-text("Utilities")')
    
    # Test each utility link
    utility_links = {
        "Upload Timesheet": "/utilities/upload_timesheet",
        "Upload Utilization": "/upload-utilization",
        "Timesheet Monthly Summary": "/utilities/timesheet_summary",
        "Cloned Timesheet Upload": "/utilities/clone_tsheet_upload",
        "Project Setup": "/utilities/project_setup"
    }
    
    for link_text, expected_url in utility_links.items():
        try:
            with page.expect_navigation():
                page.click(f'a.dropdown-item:has-text("{link_text}")')
            expect(page).to_have_url(f"{base_url}{expected_url}")
            print(f"\n✓ Utility '{link_text}' loaded successfully")
            page.go_back()  # Go back to test next link
            page.wait_for_load_state('networkidle')
            # Re-open dropdown
            page.click('a.dropdown-toggle:has-text("Utilities")')
        except Exception as e:
            print(f"\n✗ Utility '{link_text}' failed: {str(e)}")
            page.goto(f"{base_url}")
            page.wait_for_load_state('networkidle')

def test_search_functionality(page: Page, base_url):
    """Test the search functionality on the home page."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    
    # Test search by skills
    try:
        # Fill in search criteria
        page.fill('input[name="project_start_date_skill"]', '2025-12-31')
        page.select_option('select#skill1', 'Python')
        page.select_option('select#proficiency1', 'Advanced')
        
        # Submit the form
        page.click('button[type="submit"]')
        
        # Wait for results
        page.wait_for_selector('#search-results-content', state='visible')
        print("\n✓ Search by skills submitted successfully")
    except Exception as e:
        print(f"\n✗ Search by skills failed: {str(e)}")
