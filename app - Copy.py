# app.py

import keyring
import os
from functools import wraps
from flask import Flask,render_template,request,redirect,url_for,flash,session,send_file,get_flashed_messages
from dotenv import load_dotenv
from datetime import date, timedelta, datetime, timezone
from sqlalchemy import func, exc, desc, asc, and_
from sqlalchemy.orm import joinedload
from flask_mail import Mail, Message
import pandas as pd
from io import BytesIO
from decimal import Decimal, InvalidOperation
from models import TimesheetUpload, Project, Employee




# --- Database Models (Import first) ---

from models import db, Employee, Skill, Project, Allocation, EmployeeSkill, User
try:
    from models import ProjectSkillRequirement
except ImportError:
    class ProjectSkillRequirement:
        def __init__(self, skill=None, requirement_type=None, proficiency=None):
            self.skill = skill or type('Skill', (object,), {'name': 'Dummy Skill Name'})()
            self.requirement_type = requirement_type or 'Dummy Type'
            self.proficiency = proficiency or 'Dummy Prof'
        def __repr__(self):
             return f"<DummyProjectSkillRequirement {self.skill.name} ({self.requirement_type})>"

# --- Flask App Initialization ---
load_dotenv()
app = Flask(__name__)

# --- App Configuration ---
db_url = os.getenv('DATABASE_URL')
if not db_url: raise ValueError("No DATABASE_URL set")
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = keyring.get_password("resource_planner_smtp", app.config['MAIL_USERNAME'])
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))

app.config['WTF_CSRF_ENABLED'] = False
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
   
from flask_migrate import Migrate

# --- Initialize Extensions (BEFORE Blueprints) ---
mail = Mail()
db.init_app(app)
mail.init_app(app)
migrate = Migrate(app, db)

##app.register_blueprint(reports_bp, url_prefix='/reports')
# --- Register Blueprints ---
from reports.views import reports_bp
app.register_blueprint(reports_bp)  # NO url_prefix



from flask_login import LoginManager, login_user, logout_user, login_required, current_user
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = "warning"
login_manager.login_message = "You must be logged in to access this page."

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))



# --- Context Processors / Filters ---
@app.context_processor
def inject_now(): return {'now': datetime.now(timezone.utc)}

@app.template_filter('format_date')
def format_date_filter(value):
    """Formats a date object to YYYY-MM-DD string, handles None."""
    if value is None:
        return 'N/A'
    if isinstance(value, datetime):
         value = value.date()
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    return value


# --- Decorators ---
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access is required for this action.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


###from utilities import utilities_bp
from utilities.views import utilities_bp
app.register_blueprint(utilities_bp)

# --- Routes (Define after 'app' is created and extensions is initialized) ---

# Dummy/Placeholder route for managing project skills
# This route assumes ProjectSkillRequirement model is now in models.py
@app.route('/projects/<int:project_id>/manage_skills', methods=['GET', 'POST']) # Allow POST for management
@admin_required
def manage_project_skills(project_id):
    try:
        # Fetch the project with actual requirements
        project = Project.query.options(
            selectinload(Project.skill_requirements).joinedload(ProjectSkillRequirement.skill)
        ).get_or_404(project_id)
        all_skills = Skill.query.order_by(Skill.name).all()
        proficiency_levels = ['Basic', 'Moderate', 'Advanced']
        requirement_types = ['Must', 'Good to have']

        # *** Management Logic Needed Here ***
        # Example GET: Render a form to add/edit requirements (e.g., project_skill_form.html)
        # Example POST: Handle form submission to add/update/delete requirements

        # For now, flash message and redirect as feature is not fully implemented
        flash(f"Project skill management for project '{project.name}' is not fully implemented.", "warning")
        return redirect(url_for('edit_project', project_id_param=project.id)) # Redirect to edit project page

    except Exception as e:
        app.logger.error(f"Error accessing project skill management for ID {project_id}: {e}", exc_info=True)
        flash("Error loading project skill management page.", "danger")
        return redirect(url_for('projects_list')) # Redirect to list page on error

@app.route('/test_mail')
def test_mail():
    from flask_mail import Message
    from app import mail
    msg = Message(subject="Test Email", recipients=["ravindra.sonakiya@clovertex.com"], body="This is a test email.")
    mail.send(msg)
    return "Test email sent!"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username'); password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user); flash('Logged in successfully!', 'success')
            next_page = request.args.get('next'); return redirect(next_page or url_for('index'))
        else: flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); flash('You have been logged out.', 'info'); return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password'); new_password = request.form.get('new_password'); confirm_password = request.form.get('confirm_password')
        if not current_user.check_password(current_password): flash('Current password incorrect.', 'danger')
        elif not new_password or len(new_password) < 8: flash('New password must be at least 8 characters long.', 'warning')
        elif new_password != confirm_password: flash('New passwords do not match.', 'danger')
        else:
            try: current_user.set_password(new_password); db.session.commit(); flash('Password changed successfully!', 'success'); return redirect(url_for('index'))
            except Exception as e: db.session.rollback(); flash('Error changing password. Please try again.', 'danger'); app.logger.error(f"Error changing password for user {current_user.username}: {e}", exc_info=True)
    return render_template('change_password.html')

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    try:
        skills_for_template = Skill.query.order_by(Skill.name).all()
        employees_for_dropdown = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        projects_for_dropdown = Project.query.order_by(Project.name).all()
        proficiency_choices = ['Basic', 'Moderate', 'Advanced']

    except Exception as e:
        flash('Error loading initial data for search page.', 'danger');
        skills_for_template=[]; employees_for_dropdown=[]; projects_for_dropdown=[]; proficiency_choices=[]
        app.logger.error(f"Error fetching initial data for index: {e}", exc_info=True)

    results = []
    # Always load search_criteria from session on GET to preserve form state
    search_criteria = session.get('search_criteria', {'search_type': 'skill'})
    allocation_date_headers = {"current": "Current Alloc (%)", "plus_30d": "Alloc @+30d (%)", "plus_60d": "Alloc @+60d (%)", "plus_90d": "Alloc @+90d (%)", "plus_180d": "Alloc @+180d (%)"}
    active_project_start_date = None
    selected_project_with_skills = None

    if request.method == 'POST':
        # Read search criteria directly from the form submission
        search_type = request.form.get('search_type', 'skill')
        search_criteria['search_type'] = search_type # Update criteria for session to preserve form state

        # Update search_criteria based on the submitted form data
        # Note: request.form is immutable, so we build a mutable dict if needed later,
        # but get_search_results can directly read from request.form
        if search_type == 'skill':
             search_criteria['project_start_date_skill'] = request.form.get('project_start_date_skill')
             search_criteria['skill1_id'] = int(request.form.get('skill1')) if request.form.get('skill1') else None
             search_criteria['skill2_id'] = int(request.form.get('skill2')) if request.form.get('skill2') else None
             search_criteria['proficiency1'] = request.form.get('proficiency1') or None
             search_criteria['proficiency2'] = request.form.get('proficiency2') or None
        elif search_type == 'employee':
             search_criteria['search_employee_id'] = int(request.form.get('search_employee_id')) if request.form.get('search_employee_id') else None
             search_criteria['allocation_as_of_date_employee'] = request.form.get('allocation_as_of_date_employee')
        elif search_type == 'project':
             search_criteria['search_project_id'] = int(request.form.get('search_project_id')) if request.form.get('search_project_id') else None


        results = [] # Clear previous results
        selected_project_with_skills = None # Clear previous project results


        try:
            base_employee_query = Employee.query.filter_by(is_active=True)

            if search_type == 'skill':
                start_date_str = search_criteria.get('project_start_date_skill') # Read from collected criteria
                skill1_id = search_criteria.get('skill1_id') # Read from collected criteria

                if not start_date_str or not skill1_id:
                     flash('For Skill Search: Allocation As of Date and Skill 1 are required.', 'warning')
                     # No search is performed, results remain empty
                else:
                    active_project_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    skill2_id = search_criteria.get('skill2_id')
                    if skill1_id and skill2_id and skill1_id == skill2_id: flash('Skill 1 and Skill 2 must be different.', 'warning'); raise ValueError("Skills different")
                    query = base_employee_query
                    f1 = EmployeeSkill.skill_id == skill1_id
                    if search_criteria.get('proficiency1'): f1 = and_(f1, EmployeeSkill.proficiency == search_criteria.get('proficiency1'))
                    query = query.filter(Employee.skill_associations.any(f1))
                    if skill2_id:
                        f2 = EmployeeSkill.skill_id == skill2_id
                        if search_criteria.get('proficiency2'): f2 = and_(f2, EmployeeSkill.proficiency == search_criteria.get('proficiency2'))
                        query = query.filter(Employee.skill_associations.any(f2))
                    matching_employees = query.options(db.selectinload(Employee.allocations).selectinload(Allocation.project)).order_by(Employee.name).all()
                    # Process results for skill search (allocation summary)
                    if matching_employees:
                        today = date.today() # Use date.today() to get today's date as a date object
                        target_dates_calc = {
                            "current": today,
                            "plus_30d": active_project_start_date + timedelta(days=30),
                            "plus_60d": active_project_start_date + timedelta(days=60),
                            "plus_90d": active_project_start_date + timedelta(days=90),
                            "plus_180d": active_project_start_date + timedelta(days=180)
                        }
                        allocation_date_headers = {
                            "current": "Current Alloc (%)",
                            "plus_30d": f"Alloc ({target_dates_calc['plus_30d']:%b %Y}) %",
                            "plus_60d": f"Alloc ({target_dates_calc['plus_60d']:%b %Y}) %",
                            "plus_90d": f"Alloc ({target_dates_calc['plus_90d']:%b %Y}) %",
                            "plus_180d": f"Alloc ({target_dates_calc['plus_180d']:%b %Y}) %"
                        }
                        for emp_item in matching_employees:
                            allocs={}; emp_allocs_data = emp_item.allocations
                            for key, target_date_val in target_dates_calc.items():
                                compare_date = target_date_val.date() if isinstance(target_date_val, datetime) else target_date_val
                                allocs[key] = sum(a.billable_allocation_percentage for a in emp_allocs_data if a.start_date <= compare_date <= a.end_date)
                            results.append({'employee': emp_item, 'allocations': allocs})

            elif search_type == 'employee':
                employee_id = search_criteria.get('search_employee_id') # Read from collected criteria
                start_date_str = search_criteria.get('allocation_as_of_date_employee') # Read from collected criteria

                if not employee_id or not start_date_str:
                     flash('For Employee Search: Employee and Allocation As of Date are required.', 'warning')
                     # No search is performed, results remain empty
                else:
                    active_project_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    emp = base_employee_query.filter_by(id=employee_id).options(db.selectinload(Employee.allocations).selectinload(Allocation.project)).first()

                    if emp:
                        matching_employees = [emp]
                        today = date.today() # Use date.today() to get today's date as a date object
                        target_dates_calc = {
                            "current": today,
                            "plus_30d": active_project_start_date + timedelta(days=30),
                            "plus_60d": active_project_start_date + timedelta(days=60),
                            "plus_90d": active_project_start_date + timedelta(days=90),
                            "plus_180d": active_project_start_date + timedelta(days=180)
                        }
                        allocation_date_headers = {
                            "current": "Current Alloc (%)",
                            "plus_30d": f"Alloc ({target_dates_calc['plus_30d']:%b %Y}) %",
                            "plus_60d": f"Alloc ({target_dates_calc['plus_60d']:%b %Y}) %",
                            "plus_90d": f"Alloc ({target_dates_calc['plus_90d']:%b %Y}) %",
                            "plus_180d": f"Alloc ({target_dates_calc['plus_180d']:%b %Y}) %"
                        }
                        emp_item = emp
                        allocs = {}; emp_allocs_data = emp_item.allocations
                        for key, target_date_val in target_dates_calc.items():
                            compare_date = target_date_val.date() if isinstance(target_date_val, datetime) else target_date_val
                            allocs[key] = sum(a.billable_allocation_percentage for a in emp_allocs_data if a.start_date <= compare_date <= a.end_date)
                        item_to_add = {'employee': emp_item, 'allocations': allocs}
                        item_to_add['detailed_allocations'] = sorted(emp_item.allocations, key=lambda x: x.start_date) if emp_item.allocations else []
                        results.append(item_to_add)

            elif search_type == 'project':
                project_id = search_criteria.get('search_project_id') # Read from collected criteria

                if not project_id:
                     flash('For Project Search: Project selection is required.', 'warning')
                     # No search is performed, results remain empty
                else:
                    try:
                         selected_project_with_skills = Project.query.options(
                             selectinload(Project.skill_requirements).joinedload(ProjectSkillRequirement.skill)
                         ).filter_by(id=project_id).first()
                    except Exception as query_e:
                         app.logger.error(f"Error loading project {project_id} with skill requirements: {query_e}", exc_info=True)
                         flash("Error loading project details, check database setup and ProjectSkillRequirement model/relationship.", "danger") # Improved message
                         selected_project_with_skills = None

                    if not selected_project_with_skills:
                         flash("Selected project not found.", "info")
                         selected_project_with_skills = None


            # Flash message if no results were found for Skill or Employee search after attempting search
            # Refined check to ensure criteria was actually provided before flashing "No results"
            if search_type in ['skill', 'employee'] and not results and (
                 (search_type == 'skill' and (search_criteria.get('skill1_id') is not None or search_criteria.get('project_start_date_skill'))) or
                 (search_type == 'employee' and (search_criteria.get('search_employee_id') is not None or search_criteria.get('allocation_as_of_date_employee')))
            ):
                 flash('No active employees found matching the criteria.', 'info')
            elif search_type == 'employee' and search_criteria.get('search_employee_id') is not None and not results: # Specific message if employee not found
                 flash('Employee not found or is inactive.', 'info')
            # No specific flash needed for Project search if project is found but has no skills, template handles it


        except ValueError as ve:
            if "Skills must be different" in str(ve): flash('Skill 1 and Skill 2 must be different.', 'warning')
            elif "date format" in str(ve).lower() or "literal" in str(ve).lower() or "int" in str(ve).lower(): flash("Invalid input format. Please check dates, numbers, and selections.", "danger")
            else: flash(f'Invalid input: {ve}', 'danger')
            # results/selected_project_with_skills will be whatever was populated before the error
        except Exception as e:
            flash(f'An unexpected error occurred during the search: {e}', 'danger')
            app.logger.error(f"An unexpected error during search: {e}", exc_info=True)
            # results/selected_project_with_skills will be whatever was populated before the error

        # Save the criteria to session to preserve form state on GET redirect (e.g., after export/email)
        session['search_criteria'] = search_criteria


    # GET request or POST request rendering after successful search/handling
    return render_template('index.html',
                           skills=skills_for_template,
                           employees=employees_for_dropdown,
                           projects=projects_for_dropdown,
                           proficiency_choices=proficiency_choices,
                           results=results,
                           search_criteria=search_criteria, # Pass criteria to template to pre-fill form
                           allocation_date_headers=allocation_date_headers,
                           selected_project_with_skills=selected_project_with_skills
                           )


# --- List Routes with Sorting ---
@app.route('/projects/combined/<int:project_id>')
@login_required
def combined_project_view(project_id):
    """Combined view of project details."""
    project = Project.query.get_or_404(project_id)
    allocations = Allocation.query.filter_by(project_id=project_id).all()
    return render_template('combined_project_view.html', 
                         project=project, 
                         allocations=allocations)
                         
@app.route('/skills')
@login_required
def skills_list():
    sort_by_param = request.args.get('sort_by', 'name'); order_param = request.args.get('order', 'asc')
    query = Skill.query
    if hasattr(Skill, sort_by_param): column_to_sort = getattr(Skill, sort_by_param); query = query.order_by(desc(column_to_sort) if order_param == 'desc' else asc(column_to_sort))
    else: query = query.order_by(asc(Skill.name))
    try: skills_data = query.all()
    except Exception as e: flash(f'Error fetching skills: {e}', 'danger'); skills_data = []; app.logger.error(f"Error fetching skills: {e}", exc_info=True)
    return render_template('skills_list.html', skills=skills_data, sort_by=sort_by_param, current_order=order_param)

@app.route('/employees')
@login_required
def employees_list():
    sort_by_param = request.args.get('sort_by', 'name')
    order_param = request.args.get('order', 'asc')

    query = Employee.query.filter_by(is_active=True).options(db.selectinload(Employee.skill_associations).joinedload(EmployeeSkill.skill))

    if sort_by_param == 'name':
        query = query.order_by(desc(Employee.name) if order_param == 'desc' else asc(Employee.name))
    elif sort_by_param == 'email':
        query = query.order_by(desc(Employee.email) if order_param == 'desc' else asc(Employee.email))
    else:
        query = query.order_by(asc(Employee.name))

    try:
        employees_data = query.all()
    except Exception as e:
        flash(f'Error fetching employees: {e}', 'danger')
        employees_data = []
        app.logger.error(f"Error fetching employees: {e}", exc_info=True)

    return render_template('employees_list.html', employees=employees_data, sort_by=sort_by_param, current_order=order_param)





@app.route('/projects')
@login_required
def projects_list():
    try:
        # Get all projects and ensure they have a status
        projects = Project.query.options(joinedload(Project.allocations)).all()
        
        # Ensure each project has a status
        for project in projects:
            if not hasattr(project, 'status') or project.status is None:
                project.status = 'Active'  # Default status
        
        # Debug info
        print(f"Found {len(projects)} projects")
        for i, p in enumerate(projects[:3], 1):  # Print first 3 for debugging
            print(f"Project {i}: {getattr(p, 'name', 'No name')}, Status: {getattr(p, 'status', 'No status')}")
        
        return render_template('projects_list.html', projects=projects)
    except Exception as e:
        print(f"Error in projects_list: {str(e)}")
        return str(e), 500

@app.route('/allocations')
@login_required
def allocations_list():
    sort_by_param = request.args.get('sort_by', 'start_date'); order_param = request.args.get('order', 'desc')
    query = Allocation.query.options(db.selectinload(Allocation.employee), db.selectinload(Allocation.project))
    if sort_by_param == 'employee_name': query = query.join(Allocation.employee).order_by(desc(Employee.name) if order_param == 'desc' else asc(Employee.name))
    elif sort_by_param == 'project_name': query = query.join(Allocation.project).order_by(desc(Project.name) if order_param == 'desc' else asc(Project.name))
    elif sort_by_param == 'allocation_percentage': query = query.order_by(desc(Allocation.allocation_percentage) if order_param == 'desc' else asc(Allocation.allocation_percentage))
    elif hasattr(Allocation, sort_by_param): column_to_sort = getattr(Allocation, sort_by_param); query = query.order_by(desc(column_to_sort) if order_param == 'desc' else asc(column_to_sort))
    else: query = query.order_by(desc(Allocation.start_date), Allocation.id)
    try: allocations_data = query.all()
    except Exception as e: flash(f'Error fetching allocations: {e}', 'danger'); allocations_data = []; app.logger.error(f"Error fetching allocations: {e}", exc_info=True)
    return render_template('allocations_list.html', allocations=allocations_data, sort_by=sort_by_param, current_order=order_param)

# --- Add/Edit/Delete Routes (Applying @admin_required decorator) ---
@app.route('/skills/add', methods=['GET', 'POST'])
@admin_required
def add_skill():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            existing_skill = Skill.query.filter(func.lower(Skill.name) == func.lower(name)).first()
            if existing_skill: flash(f'Skill "{name}" already exists.', 'warning'); return render_template('skill_form.html', action='Add', skill={'name': name})
            try: new_skill = Skill(name=name); db.session.add(new_skill); db.session.commit(); flash(f'Skill "{name}" added successfully.', 'success'); return redirect(url_for('skills_list'))
            except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error adding skill: {e}', 'danger'); app.logger.error(f"DB Error adding skill '{name}': {e}", exc_info=True)
            except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error adding skill '{name}': {e}", exc_info=True)
        else: flash('Skill name cannot be empty.', 'warning')
        return render_template('skill_form.html', action='Add', skill={'name': name})
    return render_template('skill_form.html', action='Add', skill=None)

@app.route('/skills/edit/<int:skill_id>', methods=['GET', 'POST'])
@admin_required
def edit_skill(skill_id):
    skill_to_edit = Skill.query.get_or_404(skill_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            existing_skill = Skill.query.filter(func.lower(Skill.name) == func.lower(name), Skill.id != skill_id).first()
            if existing_skill: flash(f'Another skill with the name "{name}" already exists.', 'warning'); return render_template('skill_form.html', action='Edit', skill=skill_to_edit)
            try: skill_to_edit.name = name; db.session.commit(); flash(f'Skill "{skill_to_edit.name}" updated successfully.', 'success'); return redirect(url_for('skills_list'))
            except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error updating skill: {e}', 'danger'); app.logger.error(f"DB Error updating skill ID {skill_id}: {e}", exc_info=True)
            except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error updating skill ID {skill_id}: {e}", exc_info=True)
        else: flash('Skill name cannot be empty.', 'warning')
        return render_template('skill_form.html', action='Edit', skill=skill_to_edit)
    return render_template('skill_form.html', action='Edit', skill=skill_to_edit)

@app.route('/skills/delete/<int:skill_id>', methods=['POST'])
@admin_required
def delete_skill(skill_id):
    skill_to_delete = Skill.query.get_or_404(skill_id)
    try: skill_name = skill_to_delete.name; db.session.delete(skill_to_delete); db.session.commit(); flash(f'Skill "{skill_name}" deleted successfully.', 'success')
    except exc.IntegrityError as e: db.session.rollback(); flash(f'Error deleting skill "{skill_to_delete.name}": It might still be assigned to employees.', 'danger'); app.logger.warning(f"IntegrityError deleting skill ID {skill_id}: {e}")
    except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error deleting skill "{skill_to_delete.name}": {e}', 'danger'); app.logger.error(f"DB Error deleting skill ID {skill_id}: {e}", exc_info=True)
    except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred while deleting skill "{skill_to_delete.name}": {e}', 'danger'); app.logger.error(f"Error deleting skill ID {skill_id}: {e}", exc_info=True)
    return redirect(url_for('skills_list'))

@app.route('/employees/add', methods=['GET', 'POST'])
@admin_required
def add_employee():
    all_skills_for_form = Skill.query.order_by(Skill.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip() or None
        is_active_form = request.form.get('is_active') == 'on'
        if not name: flash('Employee name cannot be empty.', 'warning')
        elif email and Employee.query.filter(func.lower(Employee.email) == func.lower(email)).first(): flash(f'Email "{email}" is already in use.', 'warning')
        else:
            try:
                new_employee = Employee(name=name, email=email, is_active=is_active_form)
                db.session.add(new_employee)
                selected_skill_ids = set(map(int, request.form.getlist('skill_ids')))
                submitted_proficiencies = {int(k.split('_')[-1]): (v if v else None) for k, v in request.form.items() if k.startswith('proficiency_')}

                for skill_id_form in selected_skill_ids:
                    proficiency_value = submitted_proficiencies.get(skill_id_form)
                    assoc = EmployeeSkill(employee=new_employee, skill_id=skill_id_form, proficiency=proficiency_value)
                    db.session.add(assoc)

                db.session.commit(); flash(f'Employee "{name}" added successfully.', 'success'); return redirect(url_for('employees_list'))
            except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error adding employee '{name}': {e}", exc_info=True)

        current_proficiencies = {int(k.split('_')[-1]): v for k, v in request.form.items() if k.startswith('proficiency_')}
        form_data = request.form.to_dict()
        form_data['is_active'] = is_active_form
        return render_template('employee_form.html', action='Add', employee=form_data, all_skills=all_skills_for_form, current_proficiencies=current_proficiencies)

    return render_template('employee_form.html', action='Add', employee={'is_active': True}, all_skills=all_skills_for_form, current_proficiencies={})

@app.route('/employees/edit/<int:employee_id_param>', methods=['GET', 'POST'])
@admin_required
def edit_employee(employee_id_param):
    employee_to_edit = Employee.query.options(db.selectinload(Employee.skill_associations).joinedload(EmployeeSkill.skill)).get_or_404(employee_id_param)
    all_skills_for_form = Skill.query.order_by(Skill.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip() or None
        is_active_form = request.form.get('is_active') == 'on'
        if not name: flash('Employee name cannot be empty.', 'warning')
        elif email and Employee.query.filter(func.lower(Employee.email) == func.lower(email), Employee.id != employee_id_param).first(): flash(f'Email "{email}" is already in use by another employee.', 'warning')
        else:
            try:
                employee_to_edit.name = name; employee_to_edit.email = email
                employee_to_edit.is_active = is_active_form

                selected_skill_ids = set(map(int, request.form.getlist('skill_ids')))
                submitted_proficiencies = {int(k.split('_')[-1]): (v if v else None) for k, v in request.form.items() if k.startswith('proficiency_')}
                current_associations_map = {assoc.skill_id: assoc for assoc in employee_to_edit.skill_associations}

                for skill_id_form in selected_skill_ids:
                    proficiency_value = submitted_proficiencies.get(skill_id_form)
                    if skill_id_form in current_associations_map:
                        assoc = current_associations_map[skill_id_form]
                        if assoc.proficiency != proficiency_value:
                             assoc.proficiency = proficiency_value
                    else:
                        new_assoc = EmployeeSkill(employee_id=employee_to_edit.id, skill_id=skill_id_form, proficiency=proficiency_value)
                        db.session.add(new_assoc)

                ids_to_remove_assoc = set(current_associations_map.keys()) - selected_skill_ids
                for skill_id_to_remove in ids_to_remove_assoc:
                    assoc_to_remove = current_associations_map[skill_id_to_remove]
                    db.session.delete(assoc_to_remove)

                db.session.commit(); flash(f'Employee "{employee_to_edit.name}" updated successfully.', 'success'); return redirect(url_for('employees_list'))
            except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error updating employee ID {employee_id_param}: {e}", exc_info=True)

        submitted_proficiencies = {int(k.split('_')[-1]): v for k, v in request.form.items() if k.startswith('proficiency_')}
        employee_to_edit.name = name
        employee_to_edit.email = email
        employee_to_edit.is_active = is_active_form
        return render_template('employee_form.html', action='Edit', employee=employee_to_edit, all_skills=all_skills_for_form, current_proficiencies=submitted_proficiencies)

    current_proficiencies = {assoc.skill_id: (assoc.proficiency or '') for assoc in employee_to_edit.skill_associations}
    return render_template('employee_form.html', action='Edit', employee=employee_to_edit, all_skills=all_skills_for_form, current_proficiencies=current_proficiencies)


@app.route('/employees/delete/<int:employee_id_param>', methods=['POST'])
@admin_required
def delete_employee(employee_id_param):
    employee_to_deactivate = Employee.query.get_or_404(employee_id_param)
    try:
        employee_to_deactivate.is_active = False
        db.session.commit()
        flash(f'Employee "{employee_to_deactivate.name}" marked as inactive.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'Error updating employee status: {e}', 'danger')
        app.logger.error(f"Error marking employee ID {employee_id_param} inactive: {e}", exc_info=True)
    return redirect(url_for('employees_list'))

@app.route('/projects/add', methods=['GET', 'POST'])
@admin_required
def add_project():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        service_line = request.form.get('service_line', '').strip() or None
        project_type = request.form.get('project_type', '').strip() or None
        sow_start_date_str = request.form.get('sow_start_date')
        sow_end_date_str = request.form.get('sow_end_date')
        actual_start_date_str = request.form.get('actual_start_date')
        actual_end_date_str = request.form.get('actual_end_date')
        po_amount_str = request.form.get('po_amount')
        sow_allocation_fte_str = request.form.get('sow_allocation_fte')
        actual_allocation_fte_str = request.form.get('actual_allocation_fte')
        if not name: flash('Project name cannot be empty.', 'warning')
        else:
            existing_project = Project.query.filter(func.lower(Project.name) == func.lower(name)).first()
            if existing_project: flash(f'Project "{name}" already exists.', 'warning')
            else:
                try:
                    sow_start_date = datetime.strptime(sow_start_date_str, '%Y-%m-%d').date() if sow_start_date_str else None
                    sow_end_date = datetime.strptime(sow_end_date_str, '%Y-%m-%d').date() if sow_end_date_str else None
                    actual_start_date = datetime.strptime(actual_start_date_str, '%Y-%m-%d').date() if actual_start_date_str else None
                    actual_end_date = datetime.strptime(actual_end_date_str, '%Y-%m-%d').date() if actual_end_date_str else None
                    po_amount = Decimal(po_amount_str) if po_amount_str else None
                    sow_allocation_fte = Decimal(sow_allocation_fte_str) if sow_allocation_fte_str else None
                    actual_allocation_fte = Decimal(actual_allocation_fte_str) if actual_allocation_fte_str else None
                    new_project = Project(
                        name=name,
                        service_line=service_line,
                        project_type=project_type,
                        sow_start_date=sow_start_date,
                        sow_end_date=sow_end_date,
                        actual_start_date=actual_start_date,
                        actual_end_date=actual_end_date,
                        po_amount=po_amount,
                        sow_allocation_fte=sow_allocation_fte,
                        actual_allocation_fte=actual_allocation_fte
                    )
                    db.session.add(new_project); db.session.commit(); flash(f'Project "{name}" added successfully.', 'success'); return redirect(url_for('projects_list'))
                except (ValueError, InvalidOperation): flash("Invalid data format for date or PO amount.", "danger")
                except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error adding project: {e}', 'danger'); app.logger.error(f"DB Error adding project '{name}': {e}", exc_info=True)
                except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error adding project '{name}': {e}", exc_info=True)
        return render_template('project_form.html', action='Add', project=request.form)
    return render_template('project_form.html', action='Add', project=None)

@app.route('/projects/edit/<int:project_id_param>', methods=['GET', 'POST'])
@admin_required
def edit_project(project_id_param):
    try:
         project_to_edit = Project.query.options(
             selectinload(Project.skill_requirements).joinedload(ProjectSkillRequirement.skill)
         ).filter_by(id=project_id_param).first_or_404()
    except Exception as query_e:
        app.logger.error(f"Error loading project ID {project_id_param} with skill requirements for edit: {query_e}", exc_info=True)
        flash("Error loading project details, check database setup and ProjectSkillRequirement model/relationship.", "danger")
        return redirect(url_for('projects_list'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        service_line = request.form.get('service_line', '').strip() or None
        project_type = request.form.get('project_type', '').strip() or None
        sow_start_date_str = request.form.get('sow_start_date')
        sow_end_date_str = request.form.get('sow_end_date')
        actual_start_date_str = request.form.get('actual_start_date')
        actual_end_date_str = request.form.get('actual_end_date')
        po_amount_str = request.form.get('po_amount')
        sow_allocation_fte_str = request.form.get('sow_allocation_fte')
        actual_allocation_fte_str = request.form.get('actual_allocation_fte')
        if not name: flash('Project name cannot be empty.', 'warning')
        else:
            existing_project = Project.query.filter(func.lower(Project.name) == func.lower(name), Project.id != project_id_param).first()
            if existing_project: flash(f'Another project with the name \"{name}\" already exists.', 'warning'); return render_template('project_form.html', action='Edit', project=project_to_edit)
            else:
                try:
                    project_to_edit.name = name
                    project_to_edit.service_line = service_line
                    project_to_edit.project_type = project_type
                    project_to_edit.sow_start_date = datetime.strptime(sow_start_date_str, '%Y-%m-%d').date() if sow_start_date_str else None
                    project_to_edit.sow_end_date = datetime.strptime(sow_end_date_str, '%Y-%m-%d').date() if sow_end_date_str else None
                    project_to_edit.actual_start_date = datetime.strptime(actual_start_date_str, '%Y-%m-%d').date() if actual_start_date_str else None
                    project_to_edit.actual_end_date = datetime.strptime(actual_end_date_str, '%Y-%m-%d').date() if actual_end_date_str else None
                    project_to_edit.po_amount = Decimal(po_amount_str) if po_amount_str else None
                    project_to_edit.sow_allocation_fte = Decimal(sow_allocation_fte_str) if sow_allocation_fte_str else None
                    project_to_edit.actual_allocation_fte = Decimal(actual_allocation_fte_str) if actual_allocation_fte_str else None
                    db.session.commit(); flash(f'Project \"{project_to_edit.name}\" updated successfully.', 'success'); return redirect(url_for('projects_list'))
                except (ValueError, InvalidOperation): flash("Invalid data format for date or PO amount.", "danger")
                except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error updating project: {e}', 'danger'); app.logger.error(f"DB Error updating project ID {project_id_param}: {e}", exc_info=True)
                except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error updating project ID {project_id_param}: {e}", exc_info=True)
        return render_template('project_form.html', action='Edit', project=project_to_edit)

    return render_template('project_form.html', action='Edit', project=project_to_edit)

@app.route('/projects/delete/<int:project_id_param>', methods=['POST'])
@admin_required
def delete_project(project_id_param):
    project_to_delete = Project.query.get_or_404(project_id_param)
    try: project_name = project_to_delete.name; db.session.delete(project_to_delete); db.session.commit(); flash(f'Project "{project_name}" deleted successfully.', 'success')
    except exc.IntegrityError as e: db.session.rollback(); flash(f'Error deleting project "{project_to_delete.name}": Check related allocations or skill requirements.', 'danger'); app.logger.warning(f"IntegrityError deleting project ID {project_id_param}: {e}")
    except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error deleting project "{project_to_delete.name}": {e}', 'danger'); app.logger.error(f"DB Error deleting project ID {project_id_param}: {e}", exc_info=True)
    except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred while deleting project "{project_to_delete.name}": {e}', 'danger'); app.logger.error(f"Error deleting project ID {project_id_param}: {e}", exc_info=True)
    return redirect(url_for('projects_list'))

def validate_allocation_data(form_data):
    errors = []
    percentage_str = form_data.get('allocation_percentage')
    if not percentage_str: errors.append("Percentage is required.")
    else:
        try:
            percentage = int(percentage_str)
            if not (0 <= percentage <= 100): errors.append("Percentage must be between 0 and 100.")
        except ValueError: errors.append("Percentage must be a whole number.")

    start_date_str = form_data.get('start_date')
    end_date_str = form_data.get('end_date')
    start_date = None
    end_date = None

    if not start_date_str: errors.append("Start date is required.")
    else:
        try: start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError: errors.append("Invalid start date format (YYYY-MM-DD).")

    if not end_date_str: errors.append("End date is required.")
    else:
        try: end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError: errors.append("Invalid end date format (YYYY-MM-DD).")

    if start_date and end_date and end_date < start_date: errors.append("End date cannot be before start date.")

    if not form_data.get('employee_id'): errors.append("Employee selection is required.")
    if not form_data.get('project_id'): errors.append("Project selection is required.")

    return errors

@app.route('/allocations/add', methods=['GET', 'POST'])
@admin_required
def add_allocation():
    employees_for_form = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    projects_for_form = Project.query.order_by(Project.name).all()
    if request.method == 'POST':
        validation_errors = validate_allocation_data(request.form)
        if validation_errors:
            for error in validation_errors: flash(error, 'warning')
            return render_template('allocation_form.html', action='Add', allocation=request.form, employees=employees_for_form, projects=projects_for_form)
        try:
            new_allocation = Allocation(
                employee_id=int(request.form.get('employee_id')),
                project_id=int(request.form.get('project_id')),
                billable_allocation_percentage=int(request.form.get('allocation_percentage')),
                start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
                end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            )
            db.session.add(new_allocation); db.session.commit(); flash('Allocation added successfully.', 'success'); return redirect(url_for('allocations_list'))
        except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error adding allocation: {e}', 'danger'); app.logger.error(f"DB Error adding allocation: {e}", exc_info=True)
        except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error adding allocation: {e}", exc_info=True)

        return render_template('allocation_form.html', action='Add', allocation=request.form, employees=employees_for_form, projects=projects_for_form)
    return render_template('allocation_form.html', action='Add', allocation=None, employees=employees_for_form, projects=projects_for_form)

@app.route('/allocations/edit/<int:allocation_id_param>', methods=['GET', 'POST'])
@admin_required
def edit_allocation(allocation_id_param):
    allocation_to_edit = Allocation.query.get_or_404(allocation_id_param)
    active_employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    employees_for_form = active_employees
    if not allocation_to_edit.employee.is_active and allocation_to_edit.employee not in active_employees:
        employees_for_form = sorted(active_employees + [allocation_to_edit.employee], key=lambda emp: emp.name)

    projects_for_form = Project.query.order_by(Project.name).all()

    if request.method == 'POST':
        validation_errors = validate_allocation_data(request.form)
        if validation_errors:
            for error in validation_errors: flash(error, 'warning')
            form_data = request.form.to_dict()
            form_data['start_date'] = form_data.get('start_date')
            form_data['end_date'] = form_data.get('end_date')
            try: form_data['employee'] = Employee.query.get(int(form_data.get('employee_id')));
            except (ValueError, TypeError): form_data['employee'] = None
            try: form_data['project'] = Project.query.get(int(form_data.get('project_id')));
            except (ValueError, TypeError): form_data['project'] = None

            return render_template('allocation_form.html', action='Edit', allocation=form_data, employees=employees_for_form, projects=projects_for_form)
        try:
            allocation_to_edit.employee_id = int(request.form.get('employee_id'))
            allocation_to_edit.project_id = int(request.form.get('project_id'))
            allocation_to_edit.billable_allocation_percentage = int(request.form.get('allocation_percentage'))
            allocation_to_edit.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            allocation_to_edit.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            db.session.commit(); flash('Allocation updated successfully.', 'success'); return redirect(url_for('allocations_list'))
        except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error updating allocation: {e}', 'danger'); app.logger.error(f"DB Error updating allocation ID {allocation_id_param}: {e}", exc_info=True)
        except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error updating allocation ID {allocation_id_param}: {e}", exc_info=True)

        form_data = request.form.to_dict()
        form_data['start_date'] = form_data.get('start_date')
        form_data['end_date'] = form_data.get('end_date')
        try: form_data['employee'] = Employee.query.get(int(form_data.get('employee_id')));
        except (ValueError, TypeError): form_data['employee'] = None
        try: form_data['project'] = Project.query.get(int(form_data.get('project_id')));
        except (ValueError, TypeError): form_data['project'] = None
        return render_template('allocation_form.html', action='Edit', allocation=form_data, employees=employees_for_form, projects=projects_for_form)


    allocation_data = {
        'id': allocation_to_edit.id,
        'employee_id': allocation_to_edit.employee_id,
        'project_id': allocation_to_edit.project_id,
        'billable_allocation_percentage': allocation_to_edit.billable_allocation_percentage,
        'start_date': allocation_to_edit.start_date.strftime('%Y-%m-%d') if allocation_to_edit.start_date else '',
        'end_date': allocation_to_edit.end_date.strftime('%Y-%m-%d') if allocation_to_edit.end_date else '',
        'employee': allocation_to_edit.employee,
        'project': allocation_to_edit.project
    }
    return render_template('allocation_form.html', action='Edit', allocation=allocation_data, employees=employees_for_form, projects=projects_for_form)


@app.route('/allocations/delete/<int:allocation_id_param>', methods=['POST'])
@admin_required
def delete_allocation(allocation_id_param):
    allocation_to_delete = Allocation.query.get_or_404(allocation_id_param)
    try: db.session.delete(allocation_to_delete); db.session.commit(); flash('Allocation deleted successfully.', 'success')
    except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error deleting allocation: {e}', 'danger'); app.logger.error(f"DB Error deleting allocation ID {allocation_id_param}: {e}", exc_info=True)
    except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred while deleting allocation: {e}', 'danger'); app.logger.error(f"Error deleting allocation ID {allocation_id_param}: {e}", exc_info=True)
    return redirect(url_for('allocations_list'))

# --- Clone Allocation Route ---
@app.route('/allocations/clone/<int:allocation_id_param>', methods=['GET', 'POST'])
@admin_required
def clone_allocation(allocation_id_param):
    source_allocation = Allocation.query.get_or_404(allocation_id_param)
    employees_for_form = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    projects_for_form = Project.query.order_by(Project.name).all()

    if request.method == 'POST':
        validation_errors = validate_allocation_data(request.form)
        if validation_errors:
            for error in validation_errors: flash(error, 'warning')
            form_data = request.form.to_dict()
            form_data['start_date'] = form_data.get('start_date')
            form_data['end_date'] = form_data.get('end_date')
            try: form_data['employee'] = Employee.query.get(int(form_data.get('employee_id')));
            except (ValueError, TypeError): form_data['employee'] = None
            try: form_data['project'] = Project.query.get(int(form_data.get('project_id')));
            except (ValueError, TypeError): form_data['project'] = None
            return render_template('allocation_form.html', action='Clone', allocation=form_data, employees=employees_for_form, projects=projects_for_form)
        try:
            new_allocation = Allocation(
                employee_id=int(request.form.get('employee_id')),
                project_id=int(request.form.get('project_id')),
                billable_allocation_percentage=int(request.form.get('allocation_percentage')),
                start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
                end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            )
            db.session.add(new_allocation); db.session.commit(); flash('Allocation cloned successfully.', 'success'); return redirect(url_for('allocations_list'))
        except exc.SQLAlchemyError as e: db.session.rollback(); flash(f'Database error cloning allocation: {e}', 'danger'); app.logger.error(f"DB Error cloning allocation from ID {allocation_id_param}: {e}", exc_info=True)
        except Exception as e: db.session.rollback(); flash(f'An unexpected error occurred: {e}', 'danger'); app.logger.error(f"Error cloning allocation from ID {allocation_id_param}: {e}", exc_info=True)

        form_data = request.form.to_dict()
        form_data['start_date'] = form_data.get('start_date')
        form_data['end_date'] = form_data.get('end_date')
        try: form_data['employee'] = Employee.query.get(int(form_data.get('employee_id')));
        except (ValueError, TypeError): form_data['employee'] = None
        try: form_data['project'] = Project.query.get(int(form_data.get('project_id')));
        except (ValueError, TypeError): form_data['project'] = None
        return render_template('allocation_form.html', action='Clone', allocation=form_data, employees=employees_for_form, projects=projects_for_form)

    # GET request - Pre-fill the form with source allocation data
    source_allocation_data = {
        'employee_id': source_allocation.employee_id,
        'project_id': source_allocation.project_id,
        'billable_allocation_percentage': source_allocation.billable_allocation_percentage,
        'start_date': source_allocation.start_date.strftime('%Y-%m-%d') if source_allocation.start_date else '',
        'end_date': source_allocation.end_date.strftime('%Y-%m-%d') if source_allocation.end_date else '',
        'employee': source_allocation.employee,
        'project': source_allocation.project
    }
    return render_template('allocation_form.html', action='Clone', allocation=source_allocation_data, employees=employees_for_form, projects=projects_for_form)


# --- Helper for Export/Email ---
def get_search_results(criteria):
    results = []; active_project_start_date = None
    try:
        search_type = criteria.get('search_type', 'skill')
        date_str_to_use = None
        if search_type == 'skill': date_str_to_use = criteria.get('project_start_date_skill')
        elif search_type == 'employee': date_str_to_use = criteria.get('allocation_as_of_date_employee')

        # Require date for skill/employee search unless criteria explicitly says otherwise
        if search_type in ['skill', 'employee'] and not date_str_to_use:
             # Only raise if the criteria were actually submitted for these types
             if (search_type == 'skill' and (criteria.get('skill1_id') is not None or criteria.get('project_start_date_skill'))) or \
                (search_type == 'employee' and (criteria.get('search_employee_id') is not None or criteria.get('allocation_as_of_date_employee'))):
                  raise ValueError(f"Search requires a date, none provided for search type '{search_type}'.")
             else:
                 # If no relevant criteria were submitted, just return empty results without an error
                 return []


        if date_str_to_use:
             active_project_start_date = datetime.strptime(date_str_to_use, '%Y-%m-%d').date()


        employees_for_results = []
        if search_type in ['skill', 'employee']:
            # Check for essential criteria before querying
            if search_type == 'skill':
                if criteria.get('skill1_id') is None or not criteria.get('project_start_date_skill'):
                     # Criteria missing, don't query, let the caller handle the empty result/flash
                     return []
                skill1_id = criteria['skill1_id']; skill2_id = criteria.get('skill2_id')
                prof1 = criteria.get('proficiency1'); prof2 = criteria.get('proficiency2')
                query = Employee.query.filter_by(is_active=True)
                f1 = EmployeeSkill.skill_id == skill1_id
                if prof1: f1 = and_(f1, EmployeeSkill.proficiency == prof1)
                query = query.filter(Employee.skill_associations.any(f1))
                if skill2_id:
                    f2 = EmployeeSkill.skill_id == skill2_id
                    if prof2: f2 = and_(f2, EmployeeSkill.proficiency == prof2)
                    query = query.filter(Employee.skill_associations.any(f2))
                employees_for_results = query.options(db.selectinload(Employee.allocations).selectinload(Allocation.project)).order_by(Employee.name).all()
            elif search_type == 'employee':
                 if criteria.get('search_employee_id') is None or not criteria.get('allocation_as_of_date_employee'):
                     # Criteria missing, don't query
                     return []
                 employee_id = criteria['search_employee_id']
                 emp = Employee.query.filter_by(id=employee_id, is_active=True).options(db.selectinload(Employee.allocations).selectinload(Allocation.project)).first()
                 if emp: employees_for_results.append(emp)

            # Process employee/allocation results for skill or employee search if employees_for_results is not empty
            if employees_for_results and active_project_start_date:
                today=date.today() # Use date.today() to get today's date as a date object
                target_dates_calc = {
                    "current": today,
                    "plus_30d": active_project_start_date + timedelta(days=30),
                    "plus_60d": active_project_start_date + timedelta(days=60),
                    "plus_90d": active_project_start_date + timedelta(days=90),
                    "plus_180d": active_project_start_date + timedelta(days=180)
                }
                allocation_date_headers = {
                    "current": "Current Alloc (%)",
                    "plus_30d": f"Alloc ({target_dates_calc['plus_30d']:%b %Y}) %",
                    "plus_60d": f"Alloc ({target_dates_calc['plus_60d']:%b %Y}) %",
                    "plus_90d": f"Alloc ({target_dates_calc['plus_90d']:%b %Y}) %",
                    "plus_180d": f"Alloc ({target_dates_calc['plus_180d']:%b %Y}) %"
                }
                for emp_item in employees_for_results:
                    allocs={};
                    # CORRECTED: Use emp_allocs_item to get allocations from emp_item
                    emp_allocs_item = emp_item.allocations

                    for key, target_date_val in target_dates_calc.items():
                        compare_date = target_date_val.date() if isinstance(target_date_val, datetime) else target_date_val
                        # CORRECTED: Use emp_allocs_item within the sum
                        allocs[key] = sum(a.billable_allocation_percentage for a in emp_allocs_item if a.start_date <= compare_date <= a.end_date)
                    item_data = {'employee':emp_item,'allocations':allocs}
                    if search_type == 'employee':
                         item_data['detailed_allocations'] = sorted(emp_item.allocations, key=lambda x: x.start_date) if emp_item.allocations else []
                    results.append(item_data)

    except Exception as e:
        # Catch any other unexpected errors during query/processing
        app.logger.error(f"Error in get_search_results helper: {e}", exc_info=True)
        # Don't flash message here, let the calling route handle flashing based on empty results
        return []

    return results

@app.route('/export', methods=['POST']) # Needs POST to receive form data
@login_required
def export_results():
    # Read criteria directly from form data
    search_criteria = request.form.to_dict()

    # Re-process search criteria types from form string values
    search_type = search_criteria.get('search_type', 'skill')
    search_criteria['search_type'] = search_type

    # Convert necessary IDs to integers if they exist
    if search_type == 'skill':
        # Use .get() with default None and then int() conversion
        search_criteria['skill1'] = search_criteria.get('skill1') # Keep string value for form repopulation
        search_criteria['skill1_id'] = int(search_criteria.get('skill1', None)) if search_criteria.get('skill1') else None
        search_criteria['skill2'] = search_criteria.get('skill2') # Keep string value for form repopulation
        search_criteria['skill2_id'] = int(search_criteria.get('skill2', None)) if search_criteria.get('skill2') else None
        search_criteria['proficiency1'] = search_criteria.get('proficiency1') or None
        search_criteria['proficiency2'] = search_criteria.get('proficiency2') or None
        search_criteria['project_start_date_skill'] = search_criteria.get('project_start_date_skill') # Ensure date is carried over
    elif search_type == 'employee':
         # Use .get() with default None and then int() conversion
         search_criteria['search_employee_id'] = int(search_criteria.get('search_employee_id', None)) if search_criteria.get('search_employee_id') else None
         search_criteria['allocation_as_of_date_employee'] = search_criteria.get('allocation_as_of_date_employee') # Ensure date is carried over
    elif search_type == 'project':
         # Use .get() with default None and then int() conversion
         search_criteria['search_project_id'] = int(search_criteria.get('search_project_id', None)) if search_criteria.get('search_project_id') else None

    # Export not available for project search type
    if search_type == 'project':
         flash("Export not available for Project Search results yet.", "warning")
         return redirect(url_for('index'))

    # Use the helper function with the criteria from the form
    # get_search_results will return [] if criteria is missing or invalid for the type
    search_results_data = get_search_results(search_criteria)

    if not search_results_data:
        # If get_search_results returned empty (either due to no matches or invalid criteria)
        # Flash message is likely already set by get_search_results, but add a fallback/clarification
        if not get_flashed_messages(with_categories=True): # CORRECTED: Use get_flashed_messages()
             # Added check for essential criteria before flashing "No data found"
             if (search_type == 'skill' and (search_criteria.get('skill1_id') or search_criteria.get('project_start_date_skill'))) or \
                (search_type == 'employee' and (search_criteria.get('search_employee_id') or search_criteria.get('allocation_as_of_date_employee'))):
                  flash("No active employees found matching the criteria.", "info")
             elif search_type == 'employee' and search_criteria.get('search_employee_id') is not None:
                  flash("Employee not found or is inactive.", "info")
             else:
                  flash("No data found for the selected criteria to export.", "info") # Generic fallback
        return redirect(url_for('index'))

    # Proceed with generating Excel if results were found
    data_for_df=[
        {'Employee':i['employee'].name,
         'Email':i['employee'].email or 'N/A',
         'Current Alloc (%)':i['allocations']['current'],
         'Alloc +30d (%)':i['allocations']['plus_30d'],
         'Alloc +60d (%)':i['allocations']['plus_60d'],
         'Alloc +90d (%)':i['allocations']['plus_90d'],
         'Alloc +180d (%)':i['allocations']['plus_180d']}
        for i in search_results_data
    ]

    df = pd.DataFrame(data_for_df); output = BytesIO()
    try:
        writer = pd.ExcelWriter(output, engine='openpyxl');
        df.to_excel(writer, index=False, sheet_name='Employee Allocations Summary');

        # Detailed allocations only for employee search type if it's present in results
        if search_criteria.get('search_type') == 'employee' and search_results_data and search_results_data[0].get('detailed_allocations'):
             detailed_data = []
             for item in search_results_data:
                  if item['detailed_allocations']:
                       for alloc in item['detailed_allocations']:
                            detailed_data.append({
                                'Employee': item['employee'].name,
                                'Project': alloc.project.name if alloc.project else 'N/A',
                                'Allocation (%)': alloc.billable_allocation_percentage,
                                'Start Date': format_date_filter(alloc.start_date),
                                'End Date': format_date_filter(alloc.end_date)
                            })
             if detailed_data:
                  df_detailed = pd.DataFrame(detailed_data)
                  df_detailed.to_excel(writer, index=False, sheet_name='Detailed Allocations')

        writer.close(); output.seek(0)
    except Exception as e:
        app.logger.error(f"Error generating excel: {e}", exc_info=True);
        flash("Error generating Excel file.", "danger");
        return redirect(url_for('index'))

    ts=datetime.now().strftime("%Y%m%d_%H%M%S"); fname=f"employee_allocation_report_{ts}.xlsx"
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=fname)


@app.route('/email_report', methods=['POST']) # Needs POST to receive form data
@login_required
def email_report():
    # Read criteria directly from form data
    recipient_email = request.form.get('recipient_email')
    search_criteria = request.form.to_dict()

    # Re-process search criteria types from form string values
    search_type = search_criteria.get('search_type', 'skill')
    search_criteria['search_type'] = search_type

    # Convert necessary IDs to integers if they exist
    if search_type == 'skill':
        # Use .get() with default None and then int() conversion
        search_criteria['skill1'] = search_criteria.get('skill1') # Keep string value for form repopulation
        search_criteria['skill1_id'] = int(search_criteria.get('skill1', None)) if search_criteria.get('skill1') else None
        search_criteria['skill2'] = search_criteria.get('skill2') # Keep string value for form repopulation
        search_criteria['skill2_id'] = int(search_criteria.get('skill2', None)) if search_criteria.get('skill2') else None
        search_criteria['proficiency1'] = search_criteria.get('proficiency1') or None
        search_criteria['proficiency2'] = search_criteria.get('proficiency2') or None
        search_criteria['project_start_date_skill'] = search_criteria.get('project_start_date_skill') # Ensure date is carried over
    elif search_type == 'employee':
         search_criteria['search_employee_id'] = int(search_criteria.get('search_employee_id', None)) if search_criteria.get('search_employee_id') else None
         search_criteria['allocation_as_of_date_employee'] = search_criteria.get('allocation_as_of_date_employee') # Ensure date is carried over
    elif search_type == 'project':
         search_criteria['search_project_id'] = int(search_criteria.get('search_project_id', None)) if search_criteria.get('search_project_id') else None

    # Email not available for project search type
    if search_type == 'project':
         flash("Email report not available for Project Search results yet.", "warning")
         return redirect(url_for('index'))


    # Use the helper function with criteria from the form
    # get_search_results will return [] if criteria is missing or invalid for the type
    search_results_data = get_search_results(search_criteria)


    if not recipient_email:
         flash("Recipient email is missing from the form.", "warning")
         return redirect(url_for('index'))

    if not search_results_data:
        # If get_search_results returned empty (either due to no matches or invalid criteria)
        # Flash message is likely already set by get_search_results, but add a fallback/clarification
        if not get_flashed_messages(with_categories=True): # CORRECTED: Use get_flashed_messages()
             # Added check for essential criteria before flashing "No data found"
             if (search_type == 'skill' and (search_criteria.get('skill1_id') or search_criteria.get('project_start_date_skill'))) or \
                (search_type == 'employee' and (search_criteria.get('search_employee_id') or search_criteria.get('allocation_as_of_date_employee'))):
                  flash("No active employees found matching the criteria.", "info")
             elif search_type == 'employee' and search_criteria.get('search_employee_id') is not None:
                  flash("Employee not found or is inactive.", "info")
             else:
                  flash("No data found for the selected criteria to email.", "info") # Generic fallback

        return redirect(url_for('index'))

    data_for_df=[
        {'Employee':i['employee'].name,
         'Email':i['employee'].email or 'N/A',
         'Current Alloc (%)':i['allocations']['current'],
         'Alloc +30d (%)':i['allocations']['plus_30d'],
         'Alloc +60d (%)':i['allocations']['plus_60d'],
         'Alloc +90d (%)':i['allocations']['plus_90d'],
         'Alloc +180d (%)':i['allocations']['plus_180d']}
        for i in search_results_data
    ]
    df=pd.DataFrame(data_for_df); output=BytesIO()
    try:
        writer=pd.ExcelWriter(output, engine='openpyxl');
        df.to_excel(writer, index=False, sheet_name='Employee Allocations Summary');

        if search_criteria.get('search_type') == 'employee' and search_results_data and search_results_data[0].get('detailed_allocations'):
             detailed_data = []
             for item in search_results_data:
                  if item['detailed_allocations']:
                       for alloc in item['detailed_allocations']:
                            detailed_data.append({
                                'Employee': item['employee'].name,
                                'Project': alloc.project.name if alloc.project else 'N/A',
                                'Allocation (%)': alloc.billable_allocation_percentage,
                                'Start Date': format_date_filter(alloc.start_date),
                                'End Date': format_date_filter(alloc.end_date)
                            })
             if detailed_data:
                  df_detailed = pd.DataFrame(detailed_data)
                  df_detailed.to_excel(writer, index=False, sheet_name='Detailed Allocations')

        writer.close(); output.seek(0)
    except Exception as e:
        app.logger.error(f"Error generating excel for email: {e}", exc_info=True);
        flash("Error generating Excel file for email.", "danger");
        return redirect(url_for('index'))

    ts=datetime.now().strftime("%Y%m%d_%H%M%S"); fname=f"employee_allocation_report_{ts}.xlsx"
    try:
        # --- Debugging Log: Check MAIL_DEFAULT_SENDER value ---
        app.logger.info(f"MAIL_DEFAULT_SENDER from config: {app.config.get('MAIL_DEFAULT_SENDER')}")
        # --- End Debugging Log ---

        msg = Message("Employee Allocation Report", sender=app.config['MAIL_DEFAULT_SENDER'], recipients=[recipient_email])
        msg.body = "Please find the attached employee allocation report based on your recent search criteria."
        msg.attach(filename=fname, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', data=output.read())

        # --- Debugging Logs START (already had these) ---
        app.logger.info("-" * 30)
        app.logger.info("Attempting to send email...")
        app.logger.info(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
        app.logger.info(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
        app.logger.info(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
        app.logger.info(f"MAIL_USE_SSL: {app.config.get('MAIL_USE_SSL')}")
        app.logger.info(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
        app.logger.info(f"MAIL_DEFAULT_SENDER (From): {app.config.get('MAIL_DEFAULT_SENDER')}") # This will show the same as the new log, but good to keep context
        app.logger.info(f"Recipient (To): {recipient_email}")
        app.logger.info(f"Message sender (msg.sender): {msg.sender}")
        app.logger.info("-" * 30)
        # --- Debugging Logs END ---

        mail.send(msg)

        # --- Debugging Log (after mail.send) ---
        app.logger.info("mail.send(msg) called and returned without raising an immediate exception.")

        flash(f"Report sent to {recipient_email}.", "success")

    except Exception as e: # This catches errors *during email sending*
        app.logger.error(f"Error sending email to {recipient_email}: {e}", exc_info=True);
        flash(f"Failed to send email report. Error: {e}", "danger") # Flash message already includes error

    return redirect(url_for('index'))


# --- Run the App ---


# Project status toggle route
@app.route('/toggle_project_status/<int:project_id>', methods=['POST'])
@login_required
def toggle_project_status(project_id):
    project = Project.query.get_or_404(project_id)
    project.status = 'Closed' if project.status != 'Closed' else 'Active'
    db.session.commit()
    return '', 204  # Return empty success response


@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        # Update project fields here
        project.name = request.form.get('name')
        project.status = request.form.get('status', 'Active')
        # Add other fields as needed
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects_list'))
    return render_template('edit_project.html', project=project)


if __name__ == '__main__':
    with app.app_context():
        # IMPORTANT: After updating models.py, you MUST run migrations
        # (e.g., flask db migrate, flask db upgrade) or db.create_all()
        # if that's how you manage your schema and are starting fresh.
        # Since the table exists, migrations are the correct approach.
        try: #db.create_all() # Commented out assuming migrations are used
            app.logger.info("Database tables checked/created (if using db.create_all()).")
        except exc.OperationalError as e: app.logger.error(f"!!! Database connection failed: {e} !!!"); app.logger.error(f"Ensure DB server is running and DATABASE_URL in .env is correct: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        except Exception as e: app.logger.error(f"An unexpected error occurred during DB check/creation: {e}", exc_info=True)

    is_debug_mode = os.environ.get("FLASK_ENV", "production").lower() == "development"
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("FLASK_RUN_PORT", os.environ.get("PORT", 5000))))
    host = '127.0.0.1' if "HTTP_PLATFORM_PORT" in os.environ or "PORT" in os.environ else '0.0.0.0'
    if not is_debug_mode:
        if not app.config.get('MAIL_DEFAULT_SENDER'):
             app.logger.warning("MAIL_DEFAULT_SENDER is not set. Email functionality may fail.")
        if app.config.get('SECRET_KEY', os.urandom(24)) == os.urandom(24):
             app.logger.warning("SECRET_KEY is not set via environment variable. Using a temporary key. THIS IS INSECURE FOR PRODUCTION.")


    app.run(host=host, port=port, debug=is_debug_mode)
    
    
@app.route('/utilities/clone_tsheet_upload')
@admin_required # Ensures only admins can access this page
def clone_tsheet_upload():
    flash("Cloned Timesheet Upload utility page is under development.", "info")
    # In a real scenario, you would render a specific template for this feature:
    # return render_template('clone_tsheet_upload.html')
    # For now, we'll redirect back to the main index page.
    return redirect(url_for('index'))






