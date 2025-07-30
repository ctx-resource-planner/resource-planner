# C:\apps\resource_planner_web\test_python.py
import datetime
import os

print(f"Test script started at: {datetime.datetime.now()}")
print(f"Current working directory: {os.getcwd()}")
print(f"Environment PORT: {os.environ.get('PORT')}")
print(f"Environment HTTP_PLATFORM_PORT: {os.environ.get('HTTP_PLATFORM_PORT')}")
print("Test script finished successfully.")