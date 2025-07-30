#from flask import Blueprint, render_template, request, redirect, url_for, flash
#from flask_login import login_required
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user  # ADD current_user HERE
from models import db
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
    try:
        from app import db
        from models import TimesheetUpload, Employee
        from collections import defaultdict
        from pandas.tseries.holiday import USFederalHolidayCalendar
        import pandas as pd
        
        # Get all timesheet entries (adapted from Jul-18 logic)
        entries = TimesheetUpload.query.order_by(TimesheetUpload.username, TimesheetUpload.local_date).all()
        
        summary = defaultdict(lambda: defaultdict(lambda: {
            "billable_total": 0,
            "non_billable_total": 0,
            "billable_details": [],
            "non_billable_details": [],
            "capacity": 0
        }))
        
        def us_business_days(year, month):
            start = pd.Timestamp(year=year, month=month, day=1)
            end = (start + pd.offsets.MonthEnd(1))
            cal = USFederalHolidayCalendar()
            holidays = cal.holidays(start=start, end=end)
            bdays = pd.bdate_range(start, end, freq='B')
            bdays = bdays.difference(holidays)
            return len(bdays)
        
        # Get employee names for mapping
        employees = {emp.email: emp.name for emp in Employee.query.all()}
        
        for entry in entries:
            emp = employees.get(entry.username, entry.username)  # Use employee name if available
            month = entry.local_date.strftime('%Y-%m')
            year = entry.local_date.year
            month_num = entry.local_date.month
            
            if summary[emp][month]["capacity"] == 0:
                summary[emp][month]["capacity"] = us_business_days(year, month_num) * 8
            
            # Check if billable (adapt to your is_billable field)
            is_billable = str(entry.is_billable).lower() in ['true', '1', 'yes', 'y']
            
            if is_billable:
                summary[emp][month]["billable_total"] += entry.hours
                summary[emp][month]["billable_details"].append(entry)
            else:
                summary[emp][month]["non_billable_total"] += entry.hours
                summary[emp][month]["non_billable_details"].append(entry)
        
        result = []
        for emp, months in summary.items():
            for month, data in months.items():
                capacity = float(data.get("capacity", 0) or 0)
                billable_total = float(data.get("billable_total", 0) or 0)
                non_billable_total = float(data.get("non_billable_total", 0) or 0)
                billable_pct = f"{int(round((billable_total / capacity) * 100))}%" if capacity > 0 else "0%"
                non_billable_pct = f"{int(round((non_billable_total / capacity) * 100))}%" if capacity > 0 else "0%"
                
                row = {
                    "employee_name": emp,
                    "month": month,
                    "billable_total": billable_total,
                    "non_billable_total": non_billable_total,
                    "billable_details": data.get("billable_details", []),
                    "non_billable_details": data.get("non_billable_details", []),
                    "billable_pct": billable_pct,
                    "non_billable_pct": non_billable_pct,
                }
                result.append(row)
        
        result.sort(key=lambda x: (x['employee_name'], x['month']))
        return render_template('utilities/timesheet_summary.html', summary=result)
        
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return render_template('utilities/timesheet_summary.html', summary=[])


# --- Resource Utilization Dashboard (Embedded) ---
#@utilities_bp.route('/streamlit_dashboard')
#@login_required
#def streamlit_dashboard():
     #return render_template('utilities/streamlit_iframe.html')

# --- CloneTsheet Upload ---
# @utilities_bp.route('/clone_tsheet_upload', methods=['GET', 'POST'])
# @login_required
# def clone_tsheet_upload():
    # if request.method == 'POST':
        # flash('CloneTsheet Upload not implemented.', 'info')
        # return redirect(url_for('utilities.clone_tsheet_upload'))
    # return render_template('utilities/clone_tsheet_upload.html')

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

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_mail import Message
from app import mail, app
import pandas as pd
from io import BytesIO
from datetime import datetime

utilities_bp = Blueprint('utilities', __name__, url_prefix='/utilities')

#{{ ... }}

##return render_template("demo_report.html", rows=data)

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

#@utilities_bp.route('/project_setup_preview')
#@login_required
#def project_setup_preview():
    # Admin-only access check
   # if not current_user.is_admin:
     #   flash("Access denied. Admin privileges required.", "danger")
      #  return redirect(url_for('index'))
    
    #form_data = session.get('project_setup_data')
    #if not form_data:
        #flash("No form data found. Please fill out the form first.", "danger")
        #return redirect(url_for('utilities.project_setup'))
    
    r#eturn render_template('utilities/project_setup_preview.html', data=form_data)

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
        

@utilities_bp.route('/clone_tsheet_upload', methods=['GET', 'POST'])
@login_required
def clone_tsheet_upload():
    if request.method == 'POST':
        try:
            from flask_mail import Message
            from app import mail, db
            from models import ProjectSetup
            from datetime import datetime
            
            # Collect form data
            project_setup = ProjectSetup(
                company_name=request.form.get('company_name'),
                customer_name=request.form.get('customer_name'),
                customer_abbreviation=request.form.get('customer_abbreviation'),
                project_name_quickbooks=request.form.get('project_name_quickbooks'),
                customer_address=request.form.get('customer_address'),
                customer_bill_contact_name=request.form.get('customer_bill_contact_name'),
                customer_bill_contact_email=request.form.get('customer_bill_contact_email'),
                customer_bill_contact_phone=request.form.get('customer_bill_contact_phone'),
                customer_po_number=request.form.get('customer_po_number'),
                project_type=request.form.get('project_type'),
                project_start_date=datetime.strptime(request.form.get('project_start_date'), '%Y-%m-%d').date() if request.form.get('project_start_date') else None,
                estimated_end_date=datetime.strptime(request.form.get('estimated_end_date'), '%Y-%m-%d').date() if request.form.get('estimated_end_date') else None,
                project_status=request.form.get('project_status'),
                as_bid_gross_margin=request.form.get('as_bid_gross_margin'),
                project_estimating_sheet_link=request.form.get('project_estimating_sheet_link'),
                submitted_by=current_user.email,
                email_recipients=request.form.get('email_recipients')
            )
            
            # Collect employee/contractor details
            employee_details = []
            employee_names = request.form.getlist('employee_name[]')
            onshore_offshore = request.form.getlist('onshore_offshore[]')
            tsheet_service_names = request.form.getlist('tsheet_service_name[]')
            bill_rates = request.form.getlist('bill_rate[]')
            cost_rates = request.form.getlist('cost_rate[]')
            
            for i in range(len(employee_names)):
                if employee_names[i]:  # Only add if name is provided
                    employee_details.append({
                        'employee_name': employee_names[i],
                        'onshore_offshore': onshore_offshore[i] if i < len(onshore_offshore) else '',
                        'tsheet_service_name': tsheet_service_names[i] if i < len(tsheet_service_names) else '',
                        'bill_rate': bill_rates[i] if i < len(bill_rates) else '',
                        'cost_rate': cost_rates[i] if i < len(cost_rates) else ''
                    })
            
            project_setup.employee_contractor_details = employee_details
            
            # Collect fixed price details
            fixed_price_details = []
            fp_descriptions = request.form.getlist('fp_description[]')
            fp_amounts = request.form.getlist('fp_amount[]')
            
            for i in range(len(fp_descriptions)):
                if fp_descriptions[i]:
                    fixed_price_details.append({
                        'description': fp_descriptions[i],
                        'amount': fp_amounts[i] if i < len(fp_amounts) else ''
                    })
            
            project_setup.fixed_price_details = fixed_price_details
            
            # Save to database
            db.session.add(project_setup)
            db.session.commit()
            
            # Send email notification
            recipients = [email.strip() for email in request.form.get('email_recipients', '').split(',') if email.strip()]
            
            if recipients:
                msg = Message(
                    f"New Project Setup: {project_setup.project_name_quickbooks}",
                    sender=app.config['MAIL_DEFAULT_SENDER'],
                    recipients=recipients
                )
                
                # Create email body
                email_body = f"""
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

Submitted by: {current_user.email}
Submitted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review and process this project setup request.
                """
                
                msg.body = email_body
                mail.send(msg)
            
            flash('Project setup form submitted successfully!', 'success')
            return redirect(url_for('utilities.clone_tsheet_upload'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting form: {str(e)}', 'danger')
            return redirect(url_for('utilities.clone_tsheet_upload'))
    
    return render_template('utilities/clone_tsheet_upload.html')
    
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
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    
    # Get existing data from session if coming back from preview
    form_data = session.get('project_setup_data', {})
    
    return render_template('utilities/project_setup.html', employees=employees, form_data=form_data)



@utilities_bp.route('/project_setup_preview', methods=['GET', 'POST'])
@login_required
def project_setup_preview():
    # Admin-only access check
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    form_data = session.get('project_setup_data')
    if not form_data:
        flash("No form data found. Please fill the form first.", "warning")
        return redirect(url_for('utilities.project_setup'))
    
    if request.method == 'POST':
        if request.form.get('action') == 'confirm':
            # Process the actual submission
            return process_project_setup_submission()
        else:
            # Go back to form
            return redirect(url_for('utilities.project_setup'))
    
    # Show preview page
    return render_template('utilities/project_setup_preview.html', data=form_data)

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
        from app import db, mail
        from models import ProjectSetup, Customer, Project, Employee, Allocation
        from flask_mail import Message
        from datetime import datetime
        import json
        
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
            if emp_name:
                if emp_name == 'new':
                    # Create new employee
                    if i < len(new_employee_names) and i < len(new_employee_emails):
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
            if description:
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
        from flask_mail import Message
        from app import mail, app  # Import app for config
        import pandas as pd
        from io import BytesIO
        from datetime import datetime
        
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
    """Generate structured Excel file for project setup"""
    import pandas as pd
    from io import BytesIO
    
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    
    # Section A: Project & Customer Details
    project_data = {
        'Field': [
            'Company Name', 'Customer Name', 'Customer Abbreviation', 'Project Name (Quickbooks)',
            'Customer Address', 'Bill-To Contact Name', 'Bill-To Contact Email', 'Bill-To Contact Phone',
            'Customer PO Number', 'Project Type', 'Project Start Date', 'Estimated End Date',
            'Project Status', 'As-Bid Gross Margin', 'Project Estimating Sheet Link'
        ],
        'Value': [
            project_setup.company_name or '', project_setup.customer_name or '', 
            project_setup.customer_abbreviation or '', project_setup.project_name_quickbooks or '',
            project_setup.customer_address or '', project_setup.customer_bill_contact_name or '',
            project_setup.customer_bill_contact_email or '', project_setup.customer_bill_contact_phone or '',
            project_setup.customer_po_number or '', project_setup.project_type or '',
            str(project_setup.project_start_date) if project_setup.project_start_date else '',
            str(project_setup.estimated_end_date) if project_setup.estimated_end_date else '',
            project_setup.project_status or '', project_setup.as_bid_gross_margin or '',
            project_setup.project_estimating_sheet_link or ''
        ]
    }
    
    df_project = pd.DataFrame(project_data)
    df_project.to_excel(writer, sheet_name='Project Details', index=False)
    
    # Section B: Employee Details
    if project_setup.employee_contractor_details:
        df_employees = pd.DataFrame(project_setup.employee_contractor_details)
        df_employees.to_excel(writer, sheet_name='Employee Details', index=False)
    
    # Section C: Fixed Price Details
    if project_setup.fixed_price_details:
        df_fixed_price = pd.DataFrame(project_setup.fixed_price_details)
        df_fixed_price.to_excel(writer, sheet_name='Fixed Price Details', index=False)
    
    writer.close()
    output.seek(0)
    
    return output
    
# --- END OF UTILITIES BLUEPRINT ---
