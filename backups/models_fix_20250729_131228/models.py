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

# --- User Model ---
class User(UserMixin, db.Model):
    __tablename__ = 'app_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def __repr__(self):
        return f'<User {self.username}>'

# --- Skill Model ---
class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    employee_associations = db.relationship("EmployeeSkill", back_populates="skill", cascade="all, delete-orphan")
    project_associations = db.relationship("ProjectSkillRequirement", back_populates="skill", cascade="all, delete-orphan")
    def __repr__(self):
        return f'<Skill {self.name}>'

# --- Employee Model ---
class Employee(db.Model):
    __tablename__ = 'employees'
    
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

# --- EmployeeSkill Model ---
class EmployeeSkill(db.Model):
    __tablename__ = 'employee_skills'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False)
    proficiency = db.Column(db.String(50), nullable=True)
    employee = db.relationship("Employee", back_populates="skill_associations")
    skill = db.relationship("Skill", back_populates="employee_associations")
    __table_args__ = (db.UniqueConstraint('employee_id', 'skill_id', name='uq_employee_skill'),)
    def __repr__(self):
        return f'<EmployeeSkill EmpID:{self.employee_id} SkillID:{self.skill_id} Prof:{self.proficiency}>'

# --- Project Model ---
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('project_name', db.String(200), unique=True, nullable=False)
    service_line = db.Column(db.String(100), nullable=True)
    project_type = db.Column(db.String(100), nullable=True)
    sow_start_date = db.Column(db.Date, nullable=True)
    sow_end_date = db.Column(db.Date, nullable=True)
    actual_start_date = db.Column(db.Date, nullable=True)
    actual_end_date = db.Column(db.Date, nullable=True)
    po_amount = db.Column(Numeric(15, 2), nullable=True)
    sow_allocation_fte = db.Column(Numeric(15, 2), nullable=True)
    actual_allocation_fte = db.Column(Numeric(15, 2), nullable=True)
    allocations = db.relationship('Allocation', back_populates='project', cascade="all, delete-orphan")
    skill_requirements = db.relationship("ProjectSkillRequirement", back_populates="project", cascade="all, delete-orphan")
    setup_json = db.relationship("ProjectSetupJSON", back_populates="project", uselist=False, cascade="all, delete-orphan")
    
    def get_active_allocations(self):
        """Get allocations for active employees only."""
        return self.allocations.join(Employee).filter(Employee.is_active == True).all()
    
    def __repr__(self):
        return f'<Project {self.name}>'

    # Status property to check if project is active or closed
or 'Closed' based on project end date"""
        from datetime import date
        if hasattr(self, 'sow_end_date') and self.sow_end_date:
            return 'Active' if self.sow_end_date >= date.today() else 'Closed'
        return 'Active'

# --- ProjectSkillRequirement Model ---
class ProjectSkillRequirement(db.Model):
    __tablename__ = 'project_skill_requirements'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False)
    proficiency = db.Column(db.String(50), nullable=True)
    requirement_type = db.Column(db.String(50), nullable=False)
    project = db.relationship("Project", back_populates="skill_requirements")
    skill = db.relationship("Skill", back_populates="project_associations")
    __table_args__ = (
        db.UniqueConstraint('project_id', 'skill_id', name='uq_project_skill_requirement'),
        CheckConstraint("requirement_type IN ('Must', 'Good to have')", name='chk_requirement_type')
    )
    def __repr__(self):
        return f'<ProjectSkillReq ProjID:{self.project_id} SkillID:{self.skill_id} Type:{self.requirement_type} Prof:{self.proficiency}>'

# --- Allocation Model ---
class Allocation(db.Model):
    __tablename__ = 'allocations'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    billable_allocation_percentage = db.Column('billable_allocation_percentage', db.SmallInteger, nullable=False)
    sow_allocation_percentage = db.Column('sow_allocation_percentage', db.SmallInteger, nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    employee = db.relationship("Employee", back_populates="allocations")
    project = db.relationship("Project", back_populates="allocations")
    __table_args__ = (
        CheckConstraint('billable_allocation_percentage >= 0 AND billable_allocation_percentage <= 100', name='chk_billable_alloc_perc'),
        CheckConstraint('end_date >= start_date', name='chk_allocation_dates')
    )
    def __repr__(self):
        return f'<Allocation EmpID:{self.employee_id} ProjID:{self.project_id} Billable:{self.billable_allocation_percentage}%>'

# --- EmployeeMonthlyUtilization Model ---
class EmployeeMonthlyUtilization(db.Model):
    __tablename__ = 'employee_monthly_utilization'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    service_line = db.Column(db.String, nullable=False)
    month = db.Column(db.String, nullable=False)  # Format: 'YYYY-MM'
    billable_hours = db.Column(db.Integer, nullable=False)
    billable_percent = db.Column(db.String, nullable=False)
    non_billable_hours = db.Column(db.Integer, nullable=False)
    non_billable_percent = db.Column(db.String, nullable=False)
    location = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- TimesheetEntry Model ---
class TimesheetEntry(db.Model):
    __tablename__ = 'timesheet_entries'
    id = db.Column(db.Integer, primary_key=True)
    employee_email = db.Column(db.String(255), nullable=False)    # increased length for safety
    employee_name = db.Column(db.String(255))
    service_line = db.Column(db.String(255))
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    client_name = db.Column(db.String(255))
    project_name = db.Column(db.String(255))                      # removed nullable=False for flexibility
    billable = db.Column(db.Boolean, nullable=False)
    service_item = db.Column(db.String(255))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- ProjectRate Model ---
class ProjectRate(db.Model):
    __tablename__ = 'project_rates'
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(120), nullable=False)
    service_item = db.Column(db.String(120), nullable=False)
    rate_type = db.Column(db.String(50), nullable=False)  # e.g., 'T&M', 'Fixed', 'Milestone'
    rate_value = db.Column(db.Float, nullable=False)

# --- ProjectInvoice Model ---
class ProjectInvoice(db.Model):
    __tablename__ = 'project_invoices'
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(120), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- TimesheetUpload Model ---
class TimesheetUpload(db.Model):
    __tablename__ = 'timesheet_uploads'

    id = Column(Integer, primary_key=True)
    username = Column(String(100))
    payroll_id = Column(String(50))
    first_name = Column(String(100))
    last_name = Column(String(100))
    employee_number = Column(String(50))
    group_name = Column(String(100))
    local_date = Column(Date)
    local_day = Column(String(20))
    local_start_time = Column(String(20))     # robust for any time format or empty
    local_end_time = Column(String(20))
    timezone = Column(String(50))
    hours = Column(Float)
    client_name = Column(String(200))
    project_name = Column(String(200))
    is_billable = Column(Boolean, default=False)
    job_class = Column(String(100))
    department = Column(String(100))
    description = Column(String(255))
    service_item = Column(String(100))
    location = Column(String(100))
    notes = Column(String(255))
    approved_status = Column(String(50))
    has_flags = Column(Boolean, default=False)
    flag_types = Column(String(100))
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(String(100))
    comments = Column(String(255))  # for any extra comments or admin notes

    def __repr__(self):
        return f"<TimesheetUpload {self.username} {self.local_date} {self.project_name}>"

# --- Customer Model ---
class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_abbreviation = db.Column(db.String(50))
    customer_address_1 = db.Column(db.String(200))
    customer_address_2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    
    # Contact Information
    bill_contact_name = db.Column(db.String(200))
    bill_contact_email = db.Column(db.String(200))
    bill_contact_phone = db.Column(db.String(50))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Customer {self.customer_name}>'

# --- BusinessUnit Model ---
class BusinessUnit(db.Model):
    __tablename__ = 'business_units'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(20), unique=True, nullable=False)
    practice_manager = db.Column(db.String(100))
    
    def __repr__(self):
        return f"<BusinessUnit {self.short_name}>"

# --- ProjectSetup Model ---
class ProjectSetup(db.Model):
    __tablename__ = 'project_setups'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Section A: Project & Customer Details
    company_name = db.Column(db.String(200))
    customer_name = db.Column(db.String(200))
    customer_abbreviation = db.Column(db.String(50))
    project_name_quickbooks = db.Column(db.String(200), unique=True)  # Added unique constraint
    customer_address = db.Column(db.Text)
    customer_bill_contact_name = db.Column(db.String(200))
    customer_bill_contact_email = db.Column(db.String(200))
    customer_bill_contact_phone = db.Column(db.String(50))
    customer_po_number = db.Column(db.String(100))
    project_type = db.Column(db.String(100))
    project_start_date = db.Column(db.Date)
    estimated_end_date = db.Column(db.Date)
    project_status = db.Column(db.String(50))
    as_bid_gross_margin = db.Column(db.String(50))
    project_estimating_sheet_link = db.Column(db.String(500))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    customer = db.relationship("Customer")
    business_unit_id = db.Column(db.Integer, db.ForeignKey('business_units.id'), nullable=True)
    business_unit = db.relationship("BusinessUnit")
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    project_rel = db.relationship("Project", backref="project_setup")
    
    # Section B: Employee/Contractor Details (JSON field for multiple entries)
    employee_contractor_details = db.Column(db.JSON)
    
    # Section C: Fixed Price & Managed Service Details (JSON field)
    fixed_price_details = db.Column(db.JSON)
    
    # Audit fields
    created_by = db.Column(db.String(200), nullable=False)
    updated_by = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp(), nullable=False)
    
    # Metadata
    submitted_by = db.Column(db.String(200))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    email_recipients = db.Column(db.Text)  # Comma-separated emails
    
    def __repr__(self):
        return f'<ProjectSetup {self.project_name_quickbooks}>'

# --- ProjectSetupJSON Model ---
class ProjectSetupJSON(db.Model):
    __tablename__ = 'project_setup_json'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    json_data = db.Column(JSONB, nullable=False)  # Using JSONB for PostgreSQL
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to Project
    project = db.relationship("Project", back_populates="setup_json")
    
    def __repr__(self):
        return f'<ProjectSetupJSON {self.project_id}>'

# Add relationship to Project model
Project.setup_json = db.relationship("ProjectSetupJSON", 
                                   back_populates="project", 
                                   uselist=False,  # One-to-one relationship
                                   cascade="all, delete-orphan")

# Add event listener for filtering inactive employees
@event.listens_for(Query, 'before_compile', retval=True)
def filter_inactive_employees(query):
    """Filter out inactive employees from all queries by default."""
    if getattr(query._execution_options, 'include_inactive', False):
        return query  # Skip filtering if explicitly included
    
    for desc in query.column_descriptions:
        if desc['type'] is Employee or (hasattr(desc['type'], 'class_') and desc['type'].class_ is Employee):
            # Add the is_active filter to the query
            query = query.enable_assertions(False).filter(Employee.is_active == True)
            break
    return query

# Add a method to include inactive employees when needed
def include_inactive(query):
    """Use this when you need to include inactive employees."""
    return query.execution_options(include_inactive=True)

    return query.execution_options(include_inactive=True)


# Quick fix for project status - Add this at the bottom of models.py
Project.status = property(lambda self: 'Active' if not self.sow_end_date or self.sow_end_date >= __import__('datetime').date.today() else 'Closed')





