# test_login.py
import pytest
from base_test import BaseTest

class TestLogin(BaseTest):
    def test_admin_login(self, page):
        self.login()
        expect(page).to_have_url(f"{self.base_url}/dashboard")
        # Add more assertions as needed

# test_employee.py
import pytest
from base_test import BaseTest

class TestEmployeeCRUD(BaseTest):
    def test_create_employee(self, page):
        self.login()
        test_email = f"test_emp_{self.test_data['prefix']}@example.com"
        
        # Navigate to add employee
        page.goto(f"{self.base_url}/employees/add")
        
        # Fill employee form
        page.fill('input[name="name"]', f"Test Employee {self.test_data['prefix']}")
        page.fill('input[name=\"email\"]', test_email)
        page.fill('input[name=\"position\"]', "Tester")
        page.click('button[type=\"submit\"]')
        
        # Verify employee was created
        page.goto(f"{self.base_url}/employees")
        expect(page).to_have_text(test_email)
