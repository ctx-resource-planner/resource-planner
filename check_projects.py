from datetime import date
from app import app, db
from models import Project

with app.app_context():
    projects = Project.query.all()
    for p in projects:
        status = 'Active' if not p.sow_end_date or p.sow_end_date >= date.today() else 'Closed'
        print(f"Project: {p.name:<40} | End Date: {p.sow_end_date} | Status: {status}")
