# tests/test_smoke.py
def test_smoke():
    """Basic smoke test to verify the testing setup works."""
    assert 1 + 1 == 2

def test_environment():
    """Test that the test environment is properly set up."""
    import os
    # Just verify we can access environment variables
    assert 'PATH' in os.environ
    print("\nEnvironment variables are accessible")
