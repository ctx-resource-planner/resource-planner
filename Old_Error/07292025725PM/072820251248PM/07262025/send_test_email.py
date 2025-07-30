# send_test_email.py
import os
from flask import Flask
from flask_mail import Mail, Message
from dotenv import load_dotenv # IMPORT load_dotenv

# Load environment variables from .env file
load_dotenv() # CALL load_dotenv

# Minimal Flask App setup
app = Flask(__name__)

# Configure Flask-Mail from environment variables
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
# Ensure port is int, default to 587 if not set or invalid
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587)) if os.getenv('MAIL_PORT') and os.getenv('MAIL_PORT').isdigit() else 587
# Default to False if not set or not 'true' ignoring case
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD') # This will come from the PS script
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))

mail = Mail(app)

# --- Test Email Configuration ---
# Replace with a recipient email you can check
TEST_RECIPIENT = "Ravindra.Sonakiya@clovertex.com" # <-- PUT A REAL EMAIL HERE
TEST_SUBJECT = "Resource Planner Test Email"
TEST_BODY = "This is a test email sent from the Resource Planner Flask-Mail configuration."

# --- Send Test Email ---
with app.app_context():
    # Print mail configuration being used for debugging
    print("-" * 30)
    print("Flask-Mail Configuration Check:")
    print(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
    print(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
    print(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
    print(f"MAIL_USE_SSL: {app.config.get('MAIL_USE_SSL')}")
    print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"MAIL_PASSWORD: {'SET' if app.config.get('MAIL_PASSWORD') else 'NOT SET'}") # Print if set, not the password itself
    print(f"MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")
    print(f"TEST_RECIPIENT: {TEST_RECIPIENT}")
    print("-" * 30)

    # Validate essential configuration before attempting to send
    if not app.config.get('MAIL_SERVER') or not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        print("ERROR: Missing essential mail configuration (MAIL_SERVER, MAIL_USERNAME, or MAIL_PASSWORD is not set).")
    else:
        try:
            print(f"Attempting to send test email to {TEST_RECIPIENT}...")
            msg = Message(TEST_SUBJECT,
                          sender=app.config['MAIL_DEFAULT_SENDER'],
                          recipients=[TEST_RECIPIENT],
                          body=TEST_BODY)
            mail.send(msg)
            print("Test email sent SUCCESSFULLY!")

        except Exception as e:
            print(f"ERROR: Failed to send test email. Exception: {e}")
            # Print more specific SMTP errors if available
            if hasattr(e, 'smtp_code'):
                print(f"SMTP Code: {e.smtp_code}")
            if hasattr(e, 'smtp_error'):
                 # Decode byte string error messages
                 error_message = e.smtp_error.decode('utf-8') if isinstance(e.smtp_error, bytes) else e.smtp_error
                 print(f"SMTP Error: {error_message}")
            if hasattr(e, 'sender'):
                 print(f"Sender was: {e.sender}")
            if hasattr(e, 'recipients'):
                 print(f"Recipients were: {e.recipients}")