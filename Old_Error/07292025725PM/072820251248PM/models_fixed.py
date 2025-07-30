# models.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Numeric, ForeignKey, event
from sqlalchemy.orm import relationship, Query
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

# --- Base Query Class for Active-Only Filtering ---
class ActiveEmployeeQuery(db.Query):
    """Query class that filters out inactive employees by default."""
    def get(self, ident):
        return self.filter_by(id=ident, is_active=True).first()

# --- User Model ---
[Previous User Model content remains the same until Employee Model]

# --- Employee Model ---
class Employee(db.Model):
    __tablename__ = 'employees'
    query_class = ActiveEmployeeQuery  # Use our custom query class
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    skill_associations = db.relationship('EmployeeSkill', back_populates='employee', cascade="all, delete-orphan")
    allocations = db.relationship('Allocation', back_populates='employee', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Employee {self.name} (Active: {self.is_active})>'

    @classmethod
    def get_active(cls):
        """Return a query with active employees only."""
        return cls.query.filter_by(is_active=True)
    
    @classmethod
    def get_all_including_inactive(cls):
        """Get all employees including inactive ones."""
        return cls.query.execution_options(include_inactive=True).all()

[Rest of the models remain the same until the end of the file]

# Add this at the end of the file, after all model definitions
@event.listens_for(Query, 'before_compile', retval=True)
def filter_inactive_employees(query):
    """Filter out inactive employees from all queries by default."""
    if query._execution_options.get('include_inactive', False):
        return query  # Skip filtering if explicitly included
    
    for desc in query.column_descriptions:
        if desc['type'] is Employee:
            # Add the is_active filter to the query
            query = query.enable_assertions(False).filter(Employee.is_active == True)
            break
    return query

# Add a method to include inactive employees when needed
def include_inactive(query):
    """Use this when you need to include inactive employees."""
    return query.execution_options(include_inactive=True)
