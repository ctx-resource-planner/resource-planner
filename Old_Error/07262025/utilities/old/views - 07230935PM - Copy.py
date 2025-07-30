from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_mail import Message
from app import mail, app
from models import db, Employee, ProjectSetup, Customer, Project
import pandas as pd
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from pandas.tseries.holiday import USFederalHolidayCalendar

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from flask import current_app 
from flask import send_file 


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
        from models import TimesheetUpload
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
        
        employees = {emp.email: emp.name for emp in Employee.query.all()}
        
        for entry in entries:
            emp = employees.get(entry.username, entry.username)
            month = entry.local_date.strftime('%Y-%m')
            year = entry.local_date.year
            month_num = entry.local_date.month
            
            if summary[emp][month]["capacity"] == 0:
                summary[emp][month]["capacity"] = us_business_days(year, month_num) * 8
            
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

###########################
@utilities_bp.route('/project_setup', methods=['GET', 'POST'])
@login_required
def project_setup():
    if request.method == 'POST':
        try:
            # Get form data
            form_data = request.form.to_dict(flat=False)
            
            # Process and save to database first
            project_setup = ProjectSetup(
                company_name=form_data.get('company_name', [''])[0],
                customer_name=form_data.get('customer_name', [''])[0],
                customer_abbreviation=form_data.get('customer_abbreviation', [''])[0],
                project_name_quickbooks=form_data.get('project_name_quickbooks', [''])[0],
                customer_address=form_data.get('customer_address', [''])[0],
                customer_bill_contact_name=form_data.get('customer_bill_contact_name', [''])[0],
                customer_bill_contact_email=form_data.get('customer_bill_contact_email', [''])[0],
                customer_bill_contact_phone=form_data.get('customer_bill_contact_phone', [''])[0],
                customer_po_number=form_data.get('customer_po_number', [''])[0],
                project_type=form_data.get('project_type', [''])[0],
                project_start_date=datetime.strptime(form_data.get('project_start_date', [None])[0], '%Y-%m-%d') if form_data.get('project_start_date', [None])[0] else None,
                estimated_end_date=datetime.strptime(form_data.get('estimated_end_date', [None])[0], '%Y-%m-%d') if form_data.get('estimated_end_date', [None])[0] else None,
                project_status=form_data.get('project_status', [''])[0],
                as_bid_gross_margin=form_data.get('as_bid_gross_margin', [''])[0],
                project_estimating_sheet_link=form_data.get('project_estimating_sheet_link', [''])[0],
                submitted_by=current_user.email,
                email_recipients=form_data.get('email_recipients', [''])[0]
            )
            
            # Process employee details
            employee_data = []
            employee_names = form_data.get('employee_name[]', [])
            onshore_offshore = form_data.get('onshore_offshore[]', [])
            tsheet_services = form_data.get('tsheet_service_name[]', [])
            bill_rates = form_data.get('bill_rate[]', [])
            cost_rates = form_data.get('cost_rate[]', [])
            
            for i in range(len(employee_names)):
                if employee_names[i]:  # Only add if employee name exists
                    employee_data.append({
                        'employee_name': employee_names[i],
                        'onshore_offshore': onshore_offshore[i] if i < len(onshore_offshore) else '',
                        'tsheet_service_name': tsheet_services[i] if i < len(tsheet_services) else '',
                        'bill_rate': bill_rates[i] if i < len(bill_rates) else '',
                        'cost_rate': cost_rates[i] if i < len(cost_rates) else ''
                    })
            
            # Process fixed price details
            fixed_price_data = []
            fp_descriptions = form_data.get('fp_description[]', [])
            fp_amounts = form_data.get('fp_amount[]', [])
            
            for i in range(len(fp_descriptions)):
                if fp_descriptions[i]:  # Only add if description exists
                    fixed_price_data.append({
                        'description': fp_descriptions[i],
                        'amount': fp_amounts[i] if i < len(fp_amounts) else ''
                    })
            
            # Add the processed data to the model
            project_setup.employee_contractor_details = employee_data
            project_setup.fixed_price_details = fixed_price_data
            
            # Save to database
            db.session.add(project_setup)
            db.session.commit()
            
            flash('Project setup saved successfully!', 'success')
            return redirect(url_for('utilities.project_setup_preview', project_id=project_setup.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving project: {str(e)}', 'danger')
            app.logger.error(f"Error saving project: {str(e)}", exc_info=True)
            return redirect(url_for('utilities.project_setup'))
    
    # GET request - show empty form
    employees = Employee.query.all()  # For the employee dropdown
    return render_template('utilities/project_setup.html', employees=employees)
    
#####################################
#####################################

@utilities_bp.route('/project_setup_submit', methods=['POST'])
@login_required
def project_setup_submit():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    return process_project_setup_submission()

def process_project_setup_submission():
    try:
        form_data = session.get('project_setup_data')
        if not form_data:
            flash("No form data found.", "danger")
            return redirect(url_for('utilities.project_setup'))
        
        def get_list_data(key):
            value = form_data.get(key)
            if isinstance(value, list):
                return value
            elif value:
                return [value]
            else:
                return []
        
        # Create or find Customer
        customer = None
        if form_data.get('customer_name'):
            customer = Customer.query.filter_by(customer_name=form_data['customer_name']).first()
            if not customer:
                customer = Customer(
                    customer_name=form_data['customer_name'],
                    customer_abbreviation=form_data.get('customer_abbreviation'),
                    customer_address_1=form_data.get('customer_address'),
                    bill_contact_name=form_data.get('customer_bill_contact_name'),
                    bill_contact_email=form_data.get('customer_bill_contact_email'),
                    bill_contact_phone=form_data.get('customer_bill_contact_phone')
                )
                db.session.add(customer)
                db.session.flush()
        
        # Process Employee Details
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
        
        # Process Fixed Price Details
        fixed_price_details = []
        fp_descriptions = get_list_data('fp_description[]')
        fp_amounts = get_list_data('fp_amount[]')
        
        for i, description in enumerate(fp_descriptions):
            if description:
                fixed_price_details.append({
                    'description': description,
                    'amount': fp_amounts[i] if i < len(fp_amounts) else ''
                })
        
        # Create ProjectSetup record
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
        
        # Create basic Project record if needed
        if form_data.get('project_name_quickbooks'):
            existing_project = Project.query.filter_by(name=form_data['project_name_quickbooks']).first()
            if not existing_project:
                project = Project(
                    name=form_data['project_name_quickbooks'],
                    project_type=form_data.get('project_type'),
                    sow_start_date=project_setup.project_start_date,
                    sow_end_date=project_setup.estimated_end_date
                )
                db.session.add(project)
        
        db.session.commit()
        
        # Generate PDF and send email
        try:
            # Process data for PDF (same format as preview)
            employee_data_for_pdf = []
            for emp in employee_details:
                employee_data_for_pdf.append({
                    'employee_name': emp.get('employee_email', ''),
                    'new_employee_name': emp.get('employee_name', ''),
                    'location': emp.get('onshore_offshore', ''),
                    'service': emp.get('tsheet_service_name', ''),
                    'cost_rate': emp.get('cost_rate', '')
                })
            
            fixed_price_data_for_pdf = []
            for fp in fixed_price_details:
                fixed_price_data_for_pdf.append({
                    'description': fp.get('description', ''),
                    'amount': fp.get('amount', '')
                })
            
            # Generate PDF with processed data
            pdf_data = generate_project_setup_pdf(project_setup, form_data, employee_data_for_pdf, fixed_price_data_for_pdf)
            
            # Send email with PDF attachment
            print("About to send email...")
            print(f"Recipients: {form_data.get('email_recipients')}")
            print(f"PDF data size: {len(pdf_data.getvalue()) if pdf_data else 'No PDF'}")
            send_project_setup_email(project_setup, form_data, pdf_data)
            
        except Exception as e:
            print(f"Error generating PDF or sending email: {e}")
            # Continue even if email fails
        
        success_msg = f"Project setup '{form_data.get('project_name_quickbooks')}' submitted successfully!"
        if new_employees_created:
            success_msg += f" Created {len(new_employees_created)} new employee(s)."
        if customer and customer.id:
            success_msg += f" Customer '{customer.customer_name}' processed."
        
        flash(success_msg, "success")
        session.pop('project_setup_data', None)
        
        # Redirect to home page after successful submission
        return redirect('/')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing project setup: {str(e)}", "danger")
        return redirect(url_for('utilities.project_setup_preview'))

####################################################
def send_project_email_with_pdf(form_data):
    """Send email with PDF attachment"""
    print("=== EMAIL FUNCTION STARTED ===")
    
    try:
        recipients = []
        if form_data.get('email_recipients'):
            recipients = [email.strip() for email in form_data['email_recipients'].split(',')]
        
        print(f"Recipients: {recipients}")
        
        if not recipients:
            print("No recipients - exiting")
            return
        
        print("Creating email message...")
        # ... rest of your email code with print statements
        
    except Exception as e:
        print(f"Email function error: {e}")
        import traceback
        traceback.print_exc()
        
        
#################################


#############################
def generate_simple_pdf(form_data):
    """Generate better formatted PDF"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        story.append(Paragraph("PROJECT SETUP FORM", styles['Title']))
        story.append(Spacer(1, 20))
        
        # Project Details Table
        project_data = [
            ['Project Name:', form_data.get('project_name_quickbooks', '')],
            ['Customer Name:', form_data.get('customer_name', '')],
            ['Company Name:', form_data.get('company_name', '')],
            ['Project Type:', form_data.get('project_type', '')],
            ['Start Date:', form_data.get('project_start_date', '')],
            ['End Date:', form_data.get('estimated_end_date', '')],
            ['Gross Margin:', form_data.get('as_bid_gross_margin', '')],
            ['Customer Address:', form_data.get('customer_address', '')],
            ['Contact Email:', form_data.get('customer_bill_contact_email', '')],
        ]
        
        table = Table(project_data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Employees Section
        story.append(Paragraph("EMPLOYEE DETAILS", styles['Heading2']))
        employee_names = form_data.get('employee_name[]', [])
        cost_rates = form_data.get('cost_rate[]', [])
        services = form_data.get('tsheet_service_name[]', [])
        
        if employee_names and any(employee_names):
            emp_data = [['Employee', 'Service', 'Cost Rate']]
            for i, name in enumerate(employee_names):
                if name:
                    cost = cost_rates[i] if i < len(cost_rates) else ''
                    service = services[i] if i < len(services) else ''
                    emp_data.append([name, service, f"${cost}" if cost else ''])
            
            emp_table = Table(emp_data, colWidths=[3*inch, 2*inch, 1*inch])
            emp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(emp_table)
        
        story.append(Spacer(1, 20))
        
        # Fixed Price Section
        story.append(Paragraph("FIXED PRICE ITEMS", styles['Heading2']))
        fp_descriptions = form_data.get('fp_description[]', [])
        fp_amounts = form_data.get('fp_amount[]', [])
        
        if fp_descriptions and any(fp_descriptions):
            fp_data = [['Description', 'Amount']]
            for i, desc in enumerate(fp_descriptions):
                if desc:
                    amount = fp_amounts[i] if i < len(fp_amounts) else ''
                    fp_data.append([desc, f"${amount}" if amount else ''])
            
            fp_table = Table(fp_data, colWidths=[4*inch, 2*inch])
            fp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(fp_table)
        
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"PDF Error: {e}")
        return None

#############################

def generate_simple_pdf_fallback(project_setup, form_data):
    """Simple fallback PDF if HTML-to-PDF fails"""
    from io import BytesIO
    buffer = BytesIO()
    buffer.write(b"Project Setup Form - Please see email for details")
    buffer.seek(0)
    return buffer

# --- Clone Timesheet Upload ---
@utilities_bp.route('/clone_tsheet_upload', methods=['GET', 'POST'])
@login_required
def clone_tsheet_upload():
    if request.method == 'POST':
        try:
            project_setup = ProjectSetup(
                company_name=request.form.get('company_name'),
                project_name_quickbooks=request.form.get('project_name_quickbooks'),
                submitted_by=current_user.email,
                email_recipients=request.form.get('email_recipients')
            )
            db.session.add(project_setup)
            db.session.commit()
            flash('Project setup form submitted successfully!', 'success')
            return redirect(url_for('utilities.clone_tsheet_upload'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting form: {str(e)}', 'danger')
            return redirect(url_for('utilities.clone_tsheet_upload'))
    
    return render_template('utilities/clone_tsheet_upload.html')
    
@utilities_bp.route('/process_project_setup_submission', methods=['POST'])
@login_required
def process_project_setup_submission():
    try:
        form_data = session.get('project_setup_data')
        if not form_data:
            flash("No form data found.", "danger")
            return redirect(url_for('utilities.project_setup'))
        
        def get_list_data(key):
            value = form_data.get(key)
            if isinstance(value, list):
                return value
            elif value:
                return [value]
            else:
                return []
        
        # Create or find Customer
        customer = None
        if form_data.get('customer_name'):
            customer = Customer.query.filter_by(customer_name=form_data['customer_name']).first()
            if not customer:
                customer = Customer(
                    customer_name=form_data['customer_name'],
                    customer_abbreviation=form_data.get('customer_abbreviation'),
                    customer_address_1=form_data.get('customer_address'),
                    bill_contact_name=form_data.get('customer_bill_contact_name'),
                    bill_contact_email=form_data.get('customer_bill_contact_email'),
                    bill_contact_phone=form_data.get('customer_bill_contact_phone')
                )
                db.session.add(customer)
                db.session.flush()
        
        # Process Employee Details
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
        
        # Process Fixed Price Details
        fixed_price_details = []
        fp_descriptions = get_list_data('fp_description[]')
        fp_amounts = get_list_data('fp_amount[]')
        
        for i, description in enumerate(fp_descriptions):
            if description:
                fixed_price_details.append({
                    'description': description,
                    'amount': fp_amounts[i] if i < len(fp_amounts) else ''
                })
        
        # Create ProjectSetup record
        
        
        print("Saving to database...")
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
        db.session.add(project_setup)
        db.session.commit()
        print(f"Project setup saved with ID: {project_setup.id}")
        
    except Exception as e:
        print(f"Database save error: {e}")
        db.session.rollback()
        
        # Create basic Project record if needed
        if form_data.get('project_name_quickbooks'):
            existing_project = Project.query.filter_by(name=form_data['project_name_quickbooks']).first()
            if not existing_project:
                project = Project(
                    name=form_data['project_name_quickbooks'],
                    project_type=form_data.get('project_type'),
                    sow_start_date=project_setup.project_start_date,
                    sow_end_date=project_setup.estimated_end_date
                )
                db.session.add(project)
        
        db.session.commit()
        
        # Generate PDF and send email
        try:
            # Process data for PDF (same format as preview)
            employee_data_for_pdf = []
            for emp in employee_details:
                employee_data_for_pdf.append({
                    'employee_name': emp.get('employee_email', ''),
                    'new_employee_name': emp.get('employee_name', ''),
                    'location': emp.get('onshore_offshore', ''),
                    'service': emp.get('tsheet_service_name', ''),
                    'cost_rate': emp.get('cost_rate', '')
                })
            
            fixed_price_data_for_pdf = []
            for fp in fixed_price_details:
                fixed_price_data_for_pdf.append({
                    'description': fp.get('description', ''),
                    'amount': fp.get('amount', '')
                })
            
            # Generate PDF with processed data
            pdf_data = generate_project_setup_pdf(project_setup, form_data, employee_data_for_pdf, fixed_price_data_for_pdf)
            
            # Send email with PDF attachment
            send_project_setup_email(project_setup, form_data, pdf_data)
            
        except Exception as e:
            print(f"Error generating PDF or sending email: {e}")
            # Continue even if email fails
        
        success_msg = f"Project setup '{form_data.get('project_name_quickbooks')}' submitted successfully!"
        if new_employees_created:
            success_msg += f" Created {len(new_employees_created)} new employee(s)."
        if customer and customer.id:
            success_msg += f" Customer '{customer.customer_name}' processed."
        
        flash(success_msg, "success")
        session.pop('project_setup_data', None)
        
        # Redirect to home page after successful submission
        return redirect('/')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing project setup: {str(e)}", "danger")
        return redirect(url_for('utilities.project_setup_preview'))
        
def send_project_email_with_pdf(form_data):
    """Send email with PDF attachment"""
    try:
        # 1. Prepare recipients
        recipients = [email.strip() for email in form_data['email_recipients'].split(',') if email.strip()]
        if not recipients:
            current_app.logger.warning("No valid email recipients")
            return False

        # 2. Generate PDF first
        try:
            pdf_buffer = generate_simple_pdf(form_data)
            if not pdf_buffer:
                current_app.logger.error("Failed to generate PDF")
                return False
                
            # Ensure we're at the start of the buffer
            if hasattr(pdf_buffer, 'seek'):
                pdf_buffer.seek(0)
            pdf_data = pdf_buffer.read() if hasattr(pdf_buffer, 'read') else pdf_buffer
            
        except Exception as e:
            current_app.logger.error(f"PDF generation error: {str(e)}")
            return False

        # 3. Prepare email
        project_name = form_data.get('project_name_quickbooks', 'Project')
        msg = Message(
            subject=f"Project Setup: {project_name}",
            recipients=recipients,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'ravindra.sonakiya@clovertex.com')
        )
        
        # 4. Simple text body (more reliable for testing)
        msg.body = f"""
        Project Setup: {project_name}
        ----------------------------
        
        A new project has been set up:
        
        Project: {project_name}
        Customer: {form_data.get('customer_name', 'N/A')}
        Type: {form_data.get('project_type', 'N/A')}
        Status: {form_data.get('project_status', 'Draft')}
        
        Please see the attached PDF for complete details.
        """
        
        # 5. Attach PDF from bytes
        try:
            msg.attach(
                f"{project_name.replace(' ', '_')}_details.pdf",
                "application/pdf",
                pdf_data
            )
        except Exception as e:
            current_app.logger.error(f"PDF attachment error: {str(e)}")
            return False

        # 6. Send email
        mail.send(msg)
        current_app.logger.info(f"Email with PDF sent to {', '.join(recipients)}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Email sending failed: {str(e)}")
        return False
        
        
@utilities_bp.route('/project_setup/preview/<int:project_id>')
@login_required
def project_setup_preview(project_id):
    project = ProjectSetup.query.get_or_404(project_id)
    return render_template('utilities/project_setup_preview.html', project=project)
    
    
    
def send_project_creation_email(project):
    """Send email with project details and PDF attachment"""
    try:
        # Get recipient email (or use a default)
        recipient = getattr(project, 'submitted_by', current_user.email)
        
        # Create email message
        msg = Message(
            f'New Project Created: {project.name}',
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'ravindra.sonakiya@clovertex.com'),
            recipients=[recipient]
        )
        
        # Create email body with basic project info
        msg.body = f"""
        A new project has been created:

        Project Details:
        ---------------
        Project ID: {project.id}
        Project Name: {project.name}
        Service Line: {getattr(project, 'service_line', 'N/A')}
        Project Type: {getattr(project, 'project_type', 'N/A')}
        
        SOW Details:
        -----------
        Start Date: {project.sow_start_date.strftime('%Y-%m-%d') if hasattr(project, 'sow_start_date') and project.sow_start_date else 'N/A'}
        End Date: {project.sow_end_date.strftime('%Y-%m-%d') if hasattr(project, 'sow_end_date') and project.sow_end_date else 'N/A'}
        PO Amount: ${getattr(project, 'po_amount', 'N/A')}
        
        Created by: {getattr(project, 'submitted_by', current_user.email)}
        Created on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
        """
        
        # Generate and attach PDF
        try:
            pdf_data = generate_project_pdf(project)
            msg.attach(
                f"project_{project.id}_details.pdf",
                "application/pdf",
                pdf_data
            )
        except Exception as e:
            current_app.logger.error(f"PDF generation failed: {str(e)}")
            # Continue without PDF if generation fails
        
        # Send email
        mail.send(msg)
        current_app.logger.info(f"Email sent successfully to {recipient}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to send project creation email: {str(e)}")
        return False
    
    
    


def generate_project_pdf(project):
    """Generate a PDF for the project using ReportLab"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='ProjectTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=1  # Center
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=10,
        textColor=colors.HexColor('#2c3e50')
    ))
    
    elements = []
    
    # Title
    elements.append(Paragraph("Project Details", styles['ProjectTitle']))
    elements.append(Spacer(1, 20))
    
    # Project Information
    elements.append(Paragraph("Basic Information", styles['SectionHeader']))
    project_data = [
        ["Project ID:", str(project.id)],
        ["Project Name:", project.name or 'N/A'],
        ["Service Line:", project.service_line or 'N/A'],
        ["Project Type:", project.project_type or 'N/A'],
        ["Created On:", project.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(project, 'created_at') and project.created_at else 'N/A'],
        ["Created By:", getattr(project, 'creator', {}).get('username', 'System') if hasattr(project, 'creator') else 'System']
    ]
    
    # SOW Details
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("SOW Details", styles['SectionHeader']))
    sow_data = [
        ["SOW Start Date:", project.sow_start_date.strftime('%Y-%m-%d') if hasattr(project, 'sow_start_date') and project.sow_start_date else 'N/A'],
        ["SOW End Date:", project.sow_end_date.strftime('%Y-%m-%d') if hasattr(project, 'sow_end_date') and project.sow_end_date else 'N/A'],
        ["PO Amount:", f"${project.po_amount:,.2f}" if hasattr(project, 'po_amount') and project.po_amount is not None else 'N/A'],
        ["SOW Allocation FTE:", str(project.sow_allocation_fte) if hasattr(project, 'sow_allocation_fte') and project.sow_allocation_fte is not None else 'N/A']
    ]
    
    # Actual Details
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Actual Details", styles['SectionHeader']))
    actual_data = [
        ["Actual Start Date:", project.actual_start_date.strftime('%Y-%m-%d') if hasattr(project, 'actual_start_date') and project.actual_start_date else 'N/A'],
        ["Actual End Date:", project.actual_end_date.strftime('%Y-%m-%d') if hasattr(project, 'actual_end_date') and project.actual_end_date else 'N/A'],
        ["Actual Allocation FTE:", str(project.actual_allocation_fte) if hasattr(project, 'actual_allocation_fte') and project.actual_allocation_fte is not None else 'N/A']
    ]
    
    # Function to create styled tables
    def create_table(data, col_widths=[2*inch, 4*inch]):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return t
    
    # Add tables to elements
    elements.append(create_table(project_data))
    elements.append(Spacer(1, 12))
    elements.append(create_table(sow_data))
    elements.append(Spacer(1, 12))
    elements.append(create_table(actual_data))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
    
    
@utilities_bp.route('/project/<int:project_id>/download')
@login_required
def download_project_pdf(project_id):
    """Download project details as PDF"""
    project = Project.query.get_or_404(project_id)
    pdf_data = generate_project_pdf(project)
    return send_file(
        BytesIO(pdf_data),
        as_attachment=True,
        download_name=f'project_{project.id}_details.pdf',
        mimetype='application/pdf'
    )
    
@utilities_bp.route('/test-email')
def test_email():
    """Test email configuration"""
    try:
        msg = Message(
            'Test Email',
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'ravindra.sonakiya@clovertex.com'),
            recipients=['ravindra.sonakiya@clovertex.com']  # Replace with your email
        )
        msg.body = 'This is a test email from the application.'
        mail.send(msg)
        return 'Test email sent successfully!'
    except Exception as e:
        return f'Error sending test email: {str(e)}'
        
def send_simple_project_email(project, recipients):
    """Simplified email sender for project setup"""
    try:
        if not recipients:
            current_app.logger.warning("No email recipients provided")
            return False

        # Ensure recipients is a list
        if isinstance(recipients, str):
            recipients = [email.strip() for email in recipients.split(',') if email.strip()]

        # Basic email content
        subject = f"Project Setup: {getattr(project, 'project_name_quickbooks', 'New Project')}"
        body = f"""
        Project Setup Notification
        --------------------------
        
        Project: {getattr(project, 'project_name_quickbooks', 'N/A')}
        Customer: {getattr(project, 'customer_name', 'N/A')}
        Type: {getattr(project, 'project_type', 'N/A')}
        Status: {getattr(project, 'project_status', 'Draft')}
        
        View details in the application or contact support for more information.
        """

        msg = Message(
            subject=subject,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'),
            recipients=recipients,
            body=body
        )

        mail.send(msg)
        current_app.logger.info(f"Email sent to {', '.join(recipients)}")
        return True

    except Exception as e:
        current_app.logger.error(f"Email error: {str(e)}")
        return False



@utilities_bp.route('/project_setup/submit', methods=['POST'])
@login_required
def submit_project_setup():
    try:
        # Your existing form processing code...
        
        # After saving to database
        db.session.add(project_setup)
        db.session.commit()
        
        # Get recipients - prioritize form data, fallback to current user
        recipients = request.form.get('email_recipients', '')
        if not recipients and current_user.is_authenticated:
            recipients = current_user.email
            
        # Send simple email
        if recipients:
            send_simple_project_email(project_setup, recipients)
        
        flash('Project setup submitted successfully!', 'success')
        return redirect(url_for('utilities.project_setup_preview', project_id=project_setup.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in project setup: {str(e)}", exc_info=True)
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('utilities.project_setup'))
    
    
@utilities_bp.route('/test-pdf')
def test_pdf():
    """Test PDF generation"""
    test_data = {
        'project_name_quickbooks': 'Test Project',
        'customer_name': 'Test Customer',
        'project_type': 'Test Type',
        'project_status': 'Active',
        'project_start_date': '2023-01-01',
        'estimated_end_date': '2023-12-31'
    }
    
    try:
        pdf = generate_simple_pdf(test_data)
        if pdf:
            if hasattr(pdf, 'seek'):
                pdf.seek(0)
            return send_file(
                pdf,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='test.pdf'
            )
        return "Failed to generate PDF"
    except Exception as e:
        return f"Error: {str(e)}"
        

@utilities_bp.route('/test-email-with-pdf')
def test_email_with_pdf():
    """Test email with PDF attachment"""
    test_data = {
        'email_recipients': 'ravindra.sonakiya@clovertex.com',  # CHANGE THIS
        'project_name_quickbooks': 'Test Project',
        'customer_name': 'Test Customer',
        'project_type': 'Test Type',
        'project_status': 'Active',
        'project_start_date': '2023-01-01',
        'estimated_end_date': '2023-12-31'
    }
    
    try:
        # Test PDF generation first
        pdf = generate_simple_pdf(test_data)
        if not pdf:
            return "Failed to generate test PDF"
            
        # Test email with PDF
        success = send_project_email_with_pdf(test_data)
        if success:
            return "Test email with PDF sent successfully! Please check your email (including spam folder)."
        else:
            return "Failed to send test email. Check the Flask console for errors."
            
    except Exception as e:
        return f"Error during test: {str(e)}"