from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_mail import Message
from app import mail, app
import pandas as pd
from io import BytesIO
from datetime import datetime

utilities_bp = Blueprint('utilities', __name__, url_prefix='/utilities')

# --- Upload Timesheet ---
@utilities_bp.route('/upload_timesheet', methods=['GET', 'POST'])
@login_required
def upload_timesheet():
    if request.method == 'POST':
        flash('Upload Timesheet not implemented.', 'info')
        return redirect(url_for('utilities.upload_timesheet'))
    return render_template('utilities/upload_timesheet.html')

# --- Timesheet Monthly Summary ---
@utilities_bp.route('/timesheet_summary')
@login_required
def timesheet_summary():
    return render_template('utilities/timesheet_summary.html')

# --- Resource Utilization Dashboard (Embedded) ---
@utilities_bp.route('/streamlit_dashboard')
@login_required
def streamlit_dashboard():
    return render_template('utilities/streamlit_iframe.html')

# --- CloneTsheet Upload ---
@utilities_bp.route('/clone_tsheet_upload', methods=['GET', 'POST'])
@login_required
def clone_tsheet_upload():
    if request.method == 'POST':
        flash('CloneTsheet Upload not implemented.', 'info')
        return redirect(url_for('utilities.clone_tsheet_upload'))
    return render_template('utilities/clone_tsheet_upload.html')

# --- Demo Report ---
@utilities_bp.route('/demo/report')
@login_required
def demo_report():
    data = [
        {
            "sno": 1,
            "name": "Sayan Mitra",
            "march": [
                {"service_line": "SCC", "hours": 10, "color": "#4e79a7"},
                {"service_line": "DTE", "hours": 8, "color": "#f28e2b"},
            ]
        }
    ]
    for row in data:
        row['total'] = sum(split['hours'] for split in row['march'])
    return render_template("demo_report.html", rows=data)

# --- Project Setup ---
@utilities_bp.route('/project_setup', methods=['GET', 'POST'])
@login_required
def project_setup():
    # Admin-only access check
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Store form data in session for preview - handle array fields properly
        form_data = {}
        
        # Handle all form fields, including arrays
        for key in request.form:
            if key.endswith('[]'):
                # Array fields - use getlist
                form_data[key] = request.form.getlist(key)
            else:
                # Single value fields
                form_data[key] = request.form.get(key)
        
        session['project_setup_data'] = form_data
        return redirect(url_for('utilities.project_setup_preview'))
    
    # GET request - show the form
    from models import Employee
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    
    # Get existing data from session if coming back from preview
    form_data = session.get('project_setup_data', {})
    
    return render_template('utilities/project_setup.html', employees=employees, form_data=form_data)

@utilities_bp.route('/project_setup_preview')
@login_required
def project_setup_preview():
    # Admin-only access check
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    form_data = session.get('project_setup_data')
    if not form_data:
        flash("No form data found. Please fill out the form first.", "danger")
        return redirect(url_for('utilities.project_setup'))
    
    return render_template('utilities/project_setup_preview.html', data=form_data)

@utilities_bp.route('/project_setup_submit', methods=['POST'])
@login_required
def project_setup_submit():
    # Admin-only access check
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    return process_project_setup_submission()

def process_project_setup_submission():
    try:
        from app import db
        from models import ProjectSetup, Customer, Project, Employee
        
        form_data = session.get('project_setup_data')
        if not form_data:
            flash("No form data found.", "danger")
            return redirect(url_for('utilities.project_setup'))
        
        # Helper function to handle list data from session
        def get_list_data(key):
            value = form_data.get(key)
            if isinstance(value, list):
                return value
            elif value:
                return [value]
            else:
                return []
        
        # Step 1: Create or find Customer
        customer = None
        if form_data.get('customer_name'):
            customer = Customer.query.filter_by(customer_name=form_data['customer_name']).first()
            
            if not customer:
                # Create new customer
                customer = Customer(
                    customer_name=form_data['customer_name'],
                    customer_abbreviation=form_data.get('customer_abbreviation'),
                    customer_address_1=form_data.get('customer_address'),
                    bill_contact_name=form_data.get('customer_bill_contact_name'),
                    bill_contact_email=form_data.get('customer_bill_contact_email'),
                    bill_contact_phone=form_data.get('customer_bill_contact_phone')
                )
                db.session.add(customer)
                db.session.flush()  # Get customer ID
        
        # Step 2: Process Employee Details and Create New Employees
        employee_details = []
        new_employees_created = []
        
        employee_names = get_list_data('employee_name[]')
        new_employee_names = get_list_data('new_employee_name[]')
        new_employee_emails = get_list_data('new_employee_email[]')
        onshore_offshore = get_list_data('onshore_offshore[]')
        tsheet_service_names = get_list_data('tsheet_service_name[]')
        bill_rates = get_list_data('bill_rate[]')
        cost_rates = get_list_data('cost_rate[]')
        
        for i, emp_name in enumerate(employee_names):
            if emp_name and emp_name.strip():
                if emp_name == 'new':
                    # Create new employee
                    if i < len(new_employee_names) and i < len(new_employee_emails):
                        if new_employee_names[i] and new_employee_emails[i]:
                            new_emp = Employee(
                                name=new_employee_names[i],
                                email=new_employee_emails[i],
                                is_active=True
                            )
                            db.session.add(new_emp)
                            db.session.flush()
                            new_employees_created.append(new_emp)
                            emp_email = new_employee_emails[i]
                            emp_display_name = new_employee_names[i]
                else:
                    emp_email = emp_name
                    emp = Employee.query.filter_by(email=emp_email).first()
                    emp_display_name = emp.name if emp else emp_email
                
                employee_details.append({
                    'employee_email': emp_email,
                    'employee_name': emp_display_name,
                    'onshore_offshore': onshore_offshore[i] if i < len(onshore_offshore) else '',
                    'tsheet_service_name': tsheet_service_names[i] if i < len(tsheet_service_names) else '',
                    'bill_rate': bill_rates[i] if i < len(bill_rates) else '',
                    'cost_rate': cost_rates[i] if i < len(cost_rates) else ''
                })
        
        # Step 3: Process Fixed Price Details
        fixed_price_details = []
        fp_descriptions = get_list_data('fp_description[]')
        fp_amounts = get_list_data('fp_amount[]')
        
        for i, description in enumerate(fp_descriptions):
            if description and description.strip():
                fixed_price_details.append({
                    'description': description,
                    'amount': fp_amounts[i] if i < len(fp_amounts) else ''
                })
        
        # Step 4: Create ProjectSetup record
        project_setup = ProjectSetup(
            company_name=form_data.get('company_name'),
            customer_name=form_data.get('customer_name'),
            customer_abbreviation=form_data.get('customer_abbreviation'),
            project_name_quickbooks=form_data.get('project_name_quickbooks'),
            customer_address=form_data.get('customer_address'),
            customer_bill_contact_name=form_data.get('customer_bill_contact_name'),
            customer_bill_contact_email=form_data.get('customer_bill_contact_email'),
            customer_bill_contact_phone=form_data.get('customer_bill_contact_phone'),
            customer_po_number=form_data.get('customer_po_number'),
            project_type=form_data.get('project_type'),
            project_start_date=datetime.strptime(form_data['project_start_date'], '%Y-%m-%d').date() if form_data.get('project_start_date') else None,
            estimated_end_date=datetime.strptime(form_data['estimated_end_date'], '%Y-%m-%d').date() if form_data.get('estimated_end_date') else None,
            project_status=form_data.get('project_status'),
            as_bid_gross_margin=form_data.get('as_bid_gross_margin'),
            project_estimating_sheet_link=form_data.get('project_estimating_sheet_link'),
            customer_id=customer.id if customer else None,
            employee_contractor_details=employee_details,
            fixed_price_details=fixed_price_details,
            submitted_by=current_user.email,
            email_recipients=form_data.get('email_recipients')
        )
        
        db.session.add(project_setup)
        
        # Step 5: Create basic Project record (handle duplicates)
        if form_data.get('project_name_quickbooks'):
            # Check if project already exists
            existing_project = Project.query.filter_by(name=form_data['project_name_quickbooks']).first()
            if not existing_project:
                project = Project(
                    name=form_data['project_name_quickbooks'],
                    project_type=form_data.get('project_type'),
                    sow_start_date=project_setup.project_start_date,
                    sow_end_date=project_setup.estimated_end_date
                )
                db.session.add(project)
            else:
                print(f"Project '{form_data['project_name_quickbooks']}' already exists, skipping creation")
        
        # Commit all database changes
        db.session.commit()
        
        # Step 6: Send Email with Excel Attachment
        send_project_setup_email(project_setup, form_data)
        
        # Success message
        success_msg = f"Project setup '{form_data.get('project_name_quickbooks')}' submitted successfully!"
        if new_employees_created:
            success_msg += f" Created {len(new_employees_created)} new employee(s)."
        if customer and customer.id:
            success_msg += f" Customer '{customer.customer_name}' processed."
        
        flash(success_msg, "success")
        session.pop('project_setup_data', None)  # Clear session data
        
        return redirect(url_for('utilities.project_setup'))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing project setup: {str(e)}", "danger")
        return redirect(url_for('utilities.project_setup_preview'))

def send_project_setup_email(project_setup, form_data):
    """Send email with Excel attachment"""
    try:
        recipients = [email.strip() for email in form_data.get('email_recipients', '').split(',') if email.strip()]
        
        if not recipients:
            print("No email recipients found")
            return
        
        # Generate Excel attachment
        excel_data = generate_project_setup_excel(project_setup, form_data)
        
        # Create email
        msg = Message(
            f"New Project Setup: {project_setup.project_name_quickbooks}",
            sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@company.com'),
            recipients=recipients
        )
        
        msg.body = f"""
New Project Setup Form Submitted

Project Details:
- Company: {project_setup.company_name}
- Customer: {project_setup.customer_name}
- Project Name: {project_setup.project_name_quickbooks}
- Project Type: {project_setup.project_type}
- Start Date: {project_setup.project_start_date}
- Estimated End Date: {project_setup.estimated_end_date}
- Status: {project_setup.project_status}

Customer Contact:
- Name: {project_setup.customer_bill_contact_name}
- Email: {project_setup.customer_bill_contact_email}
- Phone: {project_setup.customer_bill_contact_phone}

Submitted by: {project_setup.submitted_by}
Submitted at: {project_setup.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}

Please find the detailed project setup form attached as Excel file.
        """
        
        # Attach Excel file
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"project_setup_{project_setup.project_name_quickbooks}_{ts}.xlsx"
        
        msg.attach(
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            data=excel_data.read()
        )
        
        mail.send(msg)
        print(f"Email sent successfully to: {', '.join(recipients)}")
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        # Don't fail the whole process if email fails
        pass

def generate_project_setup_excel(project_setup, form_data):
    """Generate Excel file with project setup data"""
    try:
        # Create a simple Excel file with project setup data
        data = {
            'Field': ['Company Name', 'Customer Name', 'Project Name', 'Project Type', 'Start Date', 'End Date'],
            'Value': [
                project_setup.company_name,
                project_setup.customer_name,
                project_setup.project_name_quickbooks,
                project_setup.project_type,
                str(project_setup.project_start_date) if project_setup.project_start_date else '',
                str(project_setup.estimated_end_date) if project_setup.estimated_end_date else ''
            ]
        }
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Project Setup', index=False)
        
        excel_buffer.seek(0)
        return excel_buffer
        
    except Exception as e:
        print(f"Error generating Excel: {str(e)}")
        # Return empty buffer if Excel generation fails
        return BytesIO()

# --- END OF UTILITIES BLUEPRINT ---