# app.py - Resource Planner Web Application
# =======================================

# Standard Library Imports
import os
from functools import wraps
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO

# Third-party Imports
import keyring
import pandas as pd
from flask import (Flask, render_template, request, redirect, url_for, 
                  flash, session, send_file, jsonify, get_flashed_messages)
from flask_login import (LoginManager, login_user, logout_user, 
                        login_required, current_user)
from flask_mail import Mail, Message
from flask_migrate import Migrate
from sqlalchemy import func, exc, desc, asc, and_, or_
from sqlalchemy.orm import selectinload, joinedload
from dotenv import load_dotenv

# Local Application Imports
from models import (db, Employee, Skill, Project, Allocation, 
                   EmployeeSkill, User, ProjectSkillRequirement, 
                   ProjectSetup, TimesheetUpload)

# =======================================
# Application Setup & Configuration
# =======================================

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Database Configuration
db_url = os.getenv('DATABASE_URL')
if not db_url:
    raise ValueError("No DATABASE_URL set in environment variables")
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = keyring.get_password("resource_planner_smtp", 
                                                 app.config['MAIL_USERNAME'])
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 
                                            app.config.get('MAIL_USERNAME'))

# Security Configuration
app.config['WTF_CSRF_ENABLED'] = False
app.config['WTF_CSRF_CHECK_DEFAULT'] = False

# Initialize Extensions
mail = Mail()
db.init_app(app)
mail.init_app(app)
migrate = Migrate(app, db)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = "warning"
login_manager.login_message = "You must be logged in to access this page."

# =======================================
# Helper Functions & Decorators
# =======================================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))

def admin_required(f):
    """Decorator to restrict access to admin users only."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access is required for this action.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# =======================================
# Context Processors & Template Filters
# =======================================

@app.context_processor
def inject_now():
    """Inject current datetime into all templates."""
    return {'now': datetime.now(timezone.utc)}

@app.template_filter('format_date')
def format_date_filter(value):
    """Format date to YYYY-MM-DD string, handles None."""
    if value is None:
        return 'N/A'
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    return value

# =======================================
# Blueprint Registration
# =======================================

# Import and register blueprints
from reports.views import reports_bp
from utilities.views import utilities_bp

# Register blueprints with appropriate URL prefixes
app.register_blueprint(reports_bp, url_prefix='/reports')
app.register_blueprint(utilities_bp, url_prefix='/utilities')

# =======================================
# Authentication Routes
# =======================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated: 
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow users to change their password."""
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')
        
        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'danger')
        elif not new_pw or len(new_pw) < 8:
            flash('New password must be at least 8 characters long.', 'warning')
        elif new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
        else:
            try:
                current_user.set_password(new_pw)
                db.session.commit()
                flash('Password changed successfully!', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash('Error changing password. Please try again.', 'danger')
                app.logger.error(f"Error changing password: {e}", exc_info=True)
                
    return render_template('change_password.html')

# =======================================
# Main Application Routes
# =======================================

@app.route('/')
@login_required
def index():
    """Main dashboard/landing page with search functionality."""
    # ... (existing index route code remains the same) ...
    pass

# =======================================
# Project Management Routes
# =======================================

@app.route('/projects')
@login_required
def projects_list():
    """List all projects with sorting and filtering options."""
    # ... (existing projects_list code) ...
    pass

@app.route('/projects/combined/<int:project_id>')
@login_required
def combined_project_view(project_id):
    """
    COMBINED PROJECT VIEW
    ---------------------
    This route provides a comprehensive view of a project, combining data from:
    - Project table (basic info)
    - Allocations (team members)
    - Skill requirements
    - Project setup details
    
    The view is designed to be a one-stop-shop for all project-related information.
    """
    try:
        # Eager load all related data to avoid N+1 queries
        project = Project.query.options(
            joinedload(Project.allocations).joinedload(Allocation.employee),
            joinedload(Project.skill_requirements).joinedload(ProjectSkillRequirement.skill),
            joinedload(Project.project_setup)
        ).get_or_404(project_id)
        
        # Prepare team members data
        team_members = []
        for alloc in project.allocations:
            member = {
                'name': alloc.employee.name if alloc.employee else 'Unknown',
                'email': alloc.employee.email if alloc.employee else '',
                'allocation': alloc.billable_allocation_percentage,
                'start_date': alloc.start_date,
                'end_date': alloc.end_date
            }
            team_members.append(member)
        
        # Get required skills
        required_skills = [{
            'name': req.skill.name if req.skill else 'Unknown',
            'type': req.requirement_type,
            'proficiency': req.proficiency
        } for req in project.skill_requirements]
        
        # Get project setup details if they exist
        project_setup = project.project_setup
        fixed_price_items = []
        
        if (project_setup and hasattr(project_setup, 'employee_contractor_details') 
            and isinstance(project_setup.employee_contractor_details, dict)):
            fixed_price_items = project_setup.employee_contractor_details.get('fixed_price_items', [])
        
        return render_template(
            'combined_project_view.html',
            project=project,
            project_setup=project_setup,
            team_members=team_members,
            fixed_price_items=fixed_price_items,
            required_skills=required_skills
        )
        
    except Exception as e:
        app.logger.error(f"Error in combined project view: {str(e)}", exc_info=True)
        flash("An error occurred while loading project details.", "danger")
        return redirect(url_for('projects_list'))

# ... (rest of your routes remain the same, just ensure they're properly organized) ...

# =======================================
# Application Entry Point
# =======================================

if __name__ == '__main__':
    with app.app_context():
        try:
            # Initialize database if needed
            # Note: In production, use migrations instead of create_all()
            # db.create_all()
            app.logger.info("Database connection established successfully.")
            
        except exc.OperationalError as e:
            app.logger.error(f"Database connection failed: {e}")
            app.logger.error(f"Check if database server is running and DATABASE_URL is correct: {app.config['SQLALCHEMY_DATABASE_URI']}")
        except Exception as e:
            app.logger.error(f"Unexpected error during startup: {e}", exc_info=True)
    
    # Configure host and port
    is_debug = os.environ.get("FLASK_ENV", "production").lower() == "development"
    port = int(os.environ.get("HTTP_PLATFORM_PORT", 
                             os.environ.get("FLASK_RUN_PORT", 
                                          os.environ.get("PORT", 5000))))
    host = '127.0.0.1' if any(k in os.environ for k in ["HTTP_PLATFORM_PORT", "PORT"]) else '0.0.0.0'
    
    # Security checks
    if not is_debug:
        if not app.config.get('MAIL_DEFAULT_SENDER'):
            app.logger.warning("MAIL_DEFAULT_SENDER is not set. Email functionality may fail.")
        if app.config.get('SECRET_KEY') == os.urandom(24):
            app.logger.warning("SECRET_KEY is not set via environment variable. Using a temporary key. INSECURE FOR PRODUCTION.")
    
    # Start the application
    app.run(host=host, port=port, debug=is_debug)
    
    
