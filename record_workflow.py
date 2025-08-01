from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(record_video_dir="videos/")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    
    page = context.new_page()
    
    # This will save the recording to recorded_script.py
    print("Recording started...")
    print("1. Go to http://localhost:5000")
    print("2. Log in and navigate to Reports")
    print("3. Perform the actions you want to record")
    print("4. Close the browser when done")
    
    # Start recording
    page.goto("http://localhost:5000")
    
    # Keep the browser open until you close it
    page.wait_for_close()
    
    # Save the trace
    context.tracing.stop(path="trace.zip")
    browser.close()
    
    print("\nRecording saved to trace.zip")
    print("To view the recording, run: playwright show-trace trace.zip")
