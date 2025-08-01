# Create cleanup script
@"
# cleanup_test_data.py
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def cleanup_old_test_data(days_old=1):
    \"\"\"Clean up test data older than specified days\"\"\"
    test_db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'test_resource_planner.db')
    engine = create_engine(f'sqlite:///{test_db_path}')
    Session = sessionmaker(bind=engine)
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    
    print(f\"Cleaning up test data older than {cutoff}\")
    
    with Session() as session:
        try:
            # Delete test employees
            session.execute(
                text(\"DELETE FROM employee WHERE email LIKE :pattern AND created_at < :cutoff\"),
                {'pattern': 'test_%@example.com', 'cutoff': cutoff}
            )
            
            # Add more cleanup as needed
            
            session.commit()
            print(\"Cleanup completed successfully\")
            return True
        except Exception as e:
            session.rollback()
            print(f\"Error during cleanup: {e}\")
            return False

if __name__ == \"__main__\":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cleanup_old_test_data(days)
"@ | Out-File -FilePath "$testDir\cleanup_test_data.py" -Encoding utf8

Write-Host "✅ Cleanup script created!" -ForegroundColor Green
Write-Host "Run the next script: .\setup_run_script.ps1"