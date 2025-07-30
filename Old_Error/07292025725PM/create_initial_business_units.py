# Import the app instance and models correctly
from app import app, db
from models import BusinessUnit

def create_initial_units():
    with app.app_context():
        # Initial business units
        business_units = [
            {"name": "Database", "short_name": "DB", "practice_manager": ""},
            {"name": "DevOps", "short_name": "DevOps", "practice_manager": ""},
            {"name": "Cloud Operations", "short_name": "CloudOps", "practice_manager": ""},
            {"name": "Data Engineering", "short_name": "DTE", "practice_manager": ""},
            {"name": "AI/ML", "short_name": "AI", "practice_manager": ""},
            {"name": "Site Reliability Engineering", "short_name": "SRE", "practice_manager": ""},
        ]

        for bu_data in business_units:
            if not BusinessUnit.query.filter_by(short_name=bu_data["short_name"]).first():
                bu = BusinessUnit(**bu_data)
                db.session.add(bu)
                print(f"Added business unit: {bu.short_name}")

        try:
            db.session.commit()
            print("Business units created successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating business units: {e}")

if __name__ == "__main__":
    create_initial_units()