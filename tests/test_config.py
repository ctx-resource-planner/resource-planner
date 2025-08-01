# test_config.py
TEST_CONFIG = {
    "base_url": "http://localhost:5000",
    "credentials": {
        "admin_user": "admin",
        "admin_pass": "admin"  # Change to use environment variable in production
    },
    "test_data": {
        "prefix": "test_20250731_034648",
        "employee": {
            "name": "Test User",
            "email": "test_20250731_034648@example.com",
            "position": "Tester"
        }
    }
}
