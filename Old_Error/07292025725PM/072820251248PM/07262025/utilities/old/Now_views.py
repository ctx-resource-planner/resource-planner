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
from flask import jsonify 
##from . import mail  # This imports the mail instance from your app factory




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

###########################

@utilities_bp.route('/project_setup/summary/<int:project_id>')
@login_required
def project_setup_summary(project_id):
    project = ProjectSetup.query.get_or_404(project_id)
    return render_template('utilities/project_setup_summary.html', project=project)
    
    
###########################
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
            # Convert form data to dict
            form_data = request.form.to_dict(flat=False)
            form_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                        for k, v in form_data.items()}
            
            # Create new project
            new_project = ProjectSetup(
                # Map your form fields to model attributes here
                project_name=form_data.get('project_name'),
                customer_name=form_data.get('customer_name'),
                # Add other fields as needed
            )
            
            # Save to database
            db.session.add(new_project)
            db.session.commit()
            
            # Send email with PDF
            success = send_project_email_with_pdf(form_data)
            if success:
                flash('Project setup completed successfully!', 'success')
                return redirect(url_for('utilities.project_setup_summary', project_id=new_project.id))
            else:
                flash('Error sending email notification.', 'warning')
                return redirect(url_for('utilities.project_setup'))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in project setup: {str(e)}")
            flash('An error occurred while processing your request.', 'danger')
            return redirect(url_for('utilities.project_setup'))
    
    # GET request - show the form
    return render_template('utilities/project_setup.html')
    
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
def send_project_email_with_pdf(form_data, pdf_buffer):
    """Send email with PDF attachment"""
    try:
        recipients = [email.strip() for email in form_data['email_recipients'].split(',') if email.strip()]
        if not recipients:
            return False

        msg = Message(
            subject=f"Project Setup: {form_data.get('project_name_quickbooks', 'New Project')}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
            recipients=recipients
        )

        # Simple email body
        msg.body = f"""
        Project: {form_data.get('project_name_quickbooks', 'N/A')}
        Customer: {form_data.get('customer_name', 'N/A')}
        Type: {form_data.get('project_type', 'N/A')}
        Status: {form_data.get('project_status', 'Draft')}
        
        See attached PDF for complete details.
        """

        # Attach PDF
        msg.attach(
            "project_details.pdf",
            "application/pdf",
            pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer
        )

        mail.send(msg)
        return True

    except Exception as e:
        current_app.logger.error(f"Email error: {str(e)}")
        return False
        
        
        
        
#################################


#############################
def generate_simple_pdf(form_data):
    """Generate a PDF with all project details"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Project Setup Details", styles['Heading1']))
    elements.append(Spacer(1, 20))

    # Function to add a section
    def add_section(title, data):
        elements.append(Paragraph(title, styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        table_data = []
        for key, value in data.items():
            if value:  # Only add fields with values
                table_data.append([key, str(value)])
        
        if table_data:
            table = Table(table_data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONT', (1, 0), (1, -1), 'Helvetica'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))

    # Project Information
    project_info = {
        'Project Name': form_data.get('project_name_quickbooks'),
        'Customer': form_data.get('customer_name'),
        'Project Type': form_data.get('project_type'),
        'Status': form_data.get('project_status'),
        'Start Date': form_data.get('project_start_date'),
        'End Date': form_data.get('estimated_end_date'),
        'PO Number': form_data.get('customer_po_number'),
        'Gross Margin': form_data.get('as_bid_gross_margin')
    }
    add_section("Project Information", project_info)

    # Billing Information
    billing_info = {
        'Billing Contact': form_data.get('customer_bill_contact_name'),
        'Email': form_data.get('customer_bill_contact_email'),
        'Phone': form_data.get('customer_bill_contact_phone'),
        'Address': form_data.get('customer_address')
    }
    add_section("Billing Information", billing_info)

    # Team Members
    if 'employee_name' in form_data and form_data.get('employee_name'):
        elements.append(Paragraph("Team Members", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        team_data = [['Name', 'Role', 'Location', 'Bill Rate', 'Cost Rate']]
        for i in range(len(form_data['employee_name'])):
            if form_data['employee_name'][i]:
                team_data.append([
                    form_data['employee_name'][i],
                    form_data.get('tsheet_service_name', [''])[i],
                    form_data.get('onshore_offshore', [''])[i],
                    form_data.get('bill_rate', [''])[i],
                    form_data.get('cost_rate', [''])[i]
                ])
        
        if len(team_data) > 1:
            table = Table(team_data, colWidths=[1.8*inch, 1.8*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))

    # Fixed Price Items
    if 'fp_description' in form_data and form_data.get('fp_description'):
        elements.append(Paragraph("Fixed Price Items", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        fp_data = [['Description', 'Amount']]
        for i in range(len(form_data['fp_description'])):
            if form_data['fp_description'][i]:
                fp_data.append([
                    form_data['fp_description'][i],
                    form_data.get('fp_amount', [''])[i]
                ])
        
        if len(fp_data) > 1:
            table = Table(fp_data, colWidths=[4.5*inch, 2.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
            ]))
            elements.append(table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

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
    try:
        recipients = [email.strip() for email in form_data['email_recipients'].split(',') if email.strip()]
        if not recipients:
            current_app.logger.warning("No valid email recipients")
            return False

        # Generate PDF
        pdf_buffer = generate_simple_pdf(form_data)
        if not pdf_buffer:
            current_app.logger.error("Failed to generate PDF")
            return False

        # Create email
        msg = Message(
            subject=f"Project Setup: {form_data.get('project_name_quickbooks', 'New Project')}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
            recipients=recipients
        )
        
        # Simple email body
        msg.body = f"""
        Project: {form_data.get('project_name_quickbooks', 'N/A')}
        Customer: {form_data.get('customer_name', 'N/A')}
        Type: {form_data.get('project_type', 'N/A')}
        Status: {form_data.get('project_status', 'Draft')}
        
        See attached PDF for complete details.
        """

        # Attach PDF
        msg.attach(
            "project_details.pdf",
            "application/pdf",
            pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer
        )

        # Send email
        mail.send(msg)
        return True

    except Exception as e:
        current_app.logger.error(f"Email error: {str(e)}")
        return False
        
        
@utilities_bp.route('/project_setup_preview', methods=['GET', 'POST'])
@login_required
def project_setup_preview():
    if request.method == 'POST':
        form_data = request.form.to_dict(flat=False)
        # Convert single values from lists
        form_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                    for k, v in form_data.items()}
        return render_template('utilities/project_setup_preview.html', form_data=form_data)
    return redirect(url_for('utilities.project_setup'))


    


def generate_project_pdf(form_data):
    """Generate a PDF with all project details"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        elements.append(Paragraph("Project Setup Details", styles['Heading1']))
        elements.append(Spacer(1, 20))

        # Function to add a section
        def add_section(title, data):
            elements.append(Paragraph(title, styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            table_data = []
            for key, value in data.items():
                if value:
                    table_data.append([f"{key}:", str(value)])
            
            if table_data:
                table = Table(table_data, colWidths=[2*inch, 4*inch])
                table.setStyle(TableStyle([
                    ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONT', (1, 0), (1, -1), 'Helvetica'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 12))

        # Add project info
        project_info = {
            'Project Name': form_data.get('project_name_quickbooks'),
            'Customer': form_data.get('customer_name'),
            'Project Type': form_data.get('project_type'),
            'Start Date': form_data.get('project_start_date'),
            'End Date': form_data.get('estimated_end_date'),
            'Status': form_data.get('project_status'),
            'PO Number': form_data.get('customer_po_number')
        }
        add_section("Project Information", project_info)

        # Add billing info
        billing_info = {
            'Billing Contact': form_data.get('customer_bill_contact_name'),
            'Email': form_data.get('customer_bill_contact_email'),
            'Phone': form_data.get('customer_bill_contact_phone')
        }
        add_section("Billing Information", billing_info)

        # Add team members if available
        if 'employee_name[]' in form_data:
            team_members = form_data.getlist('employee_name[]')
            if any(team_members):
                elements.append(Paragraph("Team Members", styles['Heading2']))
                elements.append(Spacer(1, 10))
                
                team_data = [['Name', 'Role', 'Location', 'Bill Rate', 'Cost Rate']]
                for i in range(len(team_members)):
                    if team_members[i]:
                        team_data.append([
                            team_members[i],
                            form_data.getlist('tsheet_service_name[]')[i] if i < len(form_data.getlist('tsheet_service_name[]')) else '',
                            form_data.getlist('onshore_offshore[]')[i] if i < len(form_data.getlist('onshore_offshore[]')) else '',
                            form_data.getlist('bill_rate[]')[i] if i < len(form_data.getlist('bill_rate[]')) else '',
                            form_data.getlist('cost_rate[]')[i] if i < len(form_data.getlist('cost_rate[]')) else ''
                        ])
                
                if len(team_data) > 1:
                    table = Table(team_data, colWidths=[1.8*inch, 1.8*inch, 1.2*inch, 1.2*inch, 1.2*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    elements.append(table)
                    elements.append(Spacer(1, 12))

        # Add fixed price items if available
        if 'fp_description[]' in form_data:
            descriptions = form_data.getlist('fp_description[]')
            if any(descriptions):
                elements.append(Paragraph("Fixed Price Items", styles['Heading2']))
                elements.append(Spacer(1, 10))
                
                fp_data = [['Description', 'Amount']]
                for i in range(len(descriptions)):
                    if descriptions[i]:
                        amount = form_data.getlist('fp_amount[]')[i] if i < len(form_data.getlist('fp_amount[]')) else ''
                        fp_data.append([descriptions[i], amount])
                
                if len(fp_data) > 1:
                    table = Table(fp_data, colWidths=[4.5*inch, 2.5*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
                    ]))
                    elements.append(table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        current_app.logger.error(f"Error generating PDF: {str(e)}")
        return None
    
    
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
    test_data = {
        'email_recipients': 'your.email@example.com',  # CHANGE THIS
        'project_name_quickbooks': 'Test Project',
        'customer_name': 'Test Customer',
        'project_type': 'Test Type',
        'project_status': 'Active',
        'project_start_date': '2023-01-01',
        'estimated_end_date': '2023-12-31'
    }
    
    try:
        pdf = generate_simple_pdf(test_data)
        if not pdf:
            return "Failed to generate test PDF"
            
        success = send_project_email_with_pdf(test_data)
        if success:
            return "Test email with PDF sent successfully! Please check your email (including spam folder)."
        else:
            return "Failed to send test email. Check the Flask console for errors."
            
    except Exception as e:
        return f"Error during test: {str(e)}"
        
        
@utilities_bp.route('/test-email-send')
def test_email_send():
    """Test email sending functionality"""
    try:
        # Test with minimal data
        test_data = {
            'email_recipients': 'ravindra.sonakiya@clovertex.com',  # CHANGE THIS
            'project_name_quickbooks': 'Test Project',
            'customer_name': 'Test Customer',
            'project_type': 'Test',
            'project_status': 'Active',
            'project_start_date': '2025-01-01',
            'estimated_end_date': '2025-12-31'
        }
        
        # Call the email function directly
        from your_email_module import send_project_email_with_pdf  # Update import path
        result = send_project_email_with_pdf(test_data)
        
        if result:
            return "Test email sent successfully! Please check your email (including spam folder)."
        else:
            return "Failed to send test email. Check the Flask console for errors."
            
    except Exception as e:
        return f"Error: {str(e)}"
        
@utilities_bp.route('/email-config')
def show_email_config():
    """Show current email configuration"""
    config = {
    'MAIL_SERVER': current_app.config.get('MAIL_SERVER', 'smtp.office365.com'),
    'MAIL_PORT': current_app.config.get('MAIL_PORT', 587),
    'MAIL_USE_TLS': current_app.config.get('MAIL_USE_TLS', True),
    'MAIL_USE_SSL': current_app.config.get('MAIL_USE_SSL', False),
    'MAIL_USERNAME': current_app.config.get('MAIL_USERNAME', 'ravindra.sonakiya@clovertex.com'),
    'MAIL_DEFAULT_SENDER': current_app.config.get('MAIL_DEFAULT_SENDER', 'Resource Planner App <hello-test@herry.com>')
    }
    return jsonify(config)
    


##@utilities_bp.route('/test-email-send')
##def test_email_send():
    ##"""Test email sending functionality"""
    ##from flask_mail import Message
    
    ##try:
        # Test with minimal data
        ##msg = Message(
            ##subject="Test Email from Resource Planner",
            ##sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@clovertex.com'),
            ##recipients=['ravindra.sonakiya@clovertx.com'],  # CHANGE THIS
            ##body="This is a test email from the Resource Planner application."
        ##)
        
        ##mail.send(msg)
        ##return "Test email sent successfully! Please check your email (including spam folder)."
            
    ##except Exception as e:
        ##return f"Error sending test email: {str(e)}"