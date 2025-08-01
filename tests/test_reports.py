# tests/test_reports.py
from playwright.sync_api import Page, expect
import time

def test_reports_page_loads(page: Page, base_url):
    """Test that the reports page loads correctly."""
    # Login
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    
    try:
        # Navigate to Reports
        page.click('a:has-text("Reports")')
        page.wait_for_load_state('networkidle')
        
        # Verify we're on the reports page
        expect(page).to_have_url(f"{base_url}/reports")
        print("\n✓ Reports page loaded successfully")
    except Exception as e:
        print(f"\n✗ Reports page failed to load: {str(e)}")
        raise

def test_utilization_report_download(page: Page, base_url):
    """Test downloading the Utilization Report."""
    # Login and navigate to reports
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    page.click('a:has-text("Reports")')
    page.wait_for_load_state('networkidle')
    
    try:
        # Find and click the Utilization Report link
        utilization_report = page.locator('a:has-text("Employee Monthly Utilization Report")')
        expect(utilization_report).to_be_visible()
        print("\nFound Utilization Report link")
        
        # Click the link and wait for download
        with page.expect_download() as download_info:
            utilization_report.click()
        
        download = download_info.value
        # Check if the downloaded file is an Excel file
        assert download.suggested_filename.endswith(('.xlsx', '.xls')), "Expected Excel file"
        print(f"\n✓ Utilization Report downloaded: {download.suggested_filename}")
        
    except Exception as e:
        print(f"\n✗ Utilization Report download failed: {str(e)}")
        raise

def test_skills_report_download(page: Page, base_url):
    """Test downloading the Skills Report."""
    # Login and navigate to reports
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    page.click('a:has-text("Reports")')
    page.wait_for_load_state('networkidle')
    
    try:
        # Find and click the Skills Report link
        skills_report = page.locator('a:has-text("Employee Skills Proficiency")')
        expect(skills_report).to_be_visible()
        print("\nFound Skills Report link")
        
        # Click the link and wait for download
        with page.expect_download() as download_info:
            skills_report.click()
        
        download = download_info.value
        # Check if the downloaded file is an Excel file
        assert download.suggested_filename.endswith(('.xlsx', '.xls')), "Expected Excel file"
        print(f"\n✓ Skills Report downloaded: {download.suggested_filename}")
        
    except Exception as e:
        print(f"\n✗ Skills Report download failed: {str(e)}")
        raise

def test_ytd_hours_report_download(page: Page, base_url):
    """Test downloading the YTD Hours Report."""
    # Login and navigate to reports
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[type="password"]', 'W00dward20$$')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    page.click('a:has-text("Reports")')
    page.wait_for_load_state('networkidle')
    
    try:
        # Find and click the YTD Hours Report link
        ytd_report = page.locator('a:has-text("YTD Employee Hours Report")')
        expect(ytd_report).to_be_visible()
        print("\nFound YTD Hours Report link")
        
        # Click the link and wait for download
        with page.expect_download() as download_info:
            ytd_report.click()
        
        download = download_info.value
        # Check if the downloaded file is an Excel file
        assert download.suggested_filename.endswith(('.xlsx', '.xls')), "Expected Excel file"
        print(f"\n✓ YTD Hours Report downloaded: {download.suggested_filename}")
        
    except Exception as e:
        print(f"\n✗ YTD Hours Report download failed: {str(e)}")
        raise
