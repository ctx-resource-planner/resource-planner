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

# --- Project Setup ---
@utilities_bp.route('/project_setup', methods=['GET', 'POST'])
def project_setup():
    if request.method == 'POST' and request.form.get('action') == 'submit':
        # Get form data
        form_data = {}
        for key in request.form.keys():
            if key.endswith('[]'):
                form_data[key] = request.form.getlist(key)
            else:
                form_data[key] = request.form.get(key)
        
        # Send email with PDF
        send_project_email_with_pdf(form_data)
        
        flash('Project setup submitted with PDF attachment!', 'success')
        return redirect(url_for('main.index'))
    
    # Show form
    employees = Employee.query.all()
    return render_template('utilities/project_setup.html', employees=employees)

@utilities_bp.route('/project_setup_preview')
@login_required
def project_setup_preview():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    form_data = session.get('project_setup_data')
    if not form_data:
        flash("No form data found. Please fill out the form first.", "danger")
        return redirect(url_for('utilities.project_setup'))
    
    # Debug: Print what's in session
    print("=== SESSION DATA ===")
    for key, value in form_data.items():
        print(f"{key}: {value}")
    print("=== END SESSION ===")
    
    # Process Section B data into clean list of dictionaries
    employee_data = []
    employee_names = form_data.get('employee_name[]', [])
    new_employee_names = form_data.get('new_employee_name[]', [])
    new_employee_emails = form_data.get('new_employee_email[]', [])
    onshore_offshore = form_data.get('onshore_offshore[]', [])
    tsheet_service = form_data.get('tsheet_service_name[]', [])
    bill_rates = form_data.get('bill_rate[]', [])
    cost_rates = form_data.get('cost_rate[]', [])
    
    print(f"Processing employees: {employee_names}")
    print(f"Processing onshore_offshore: {onshore_offshore}")
    print(f"Processing cost_rates: {cost_rates}")
    
    # Get the maximum length to iterate through all entries
    max_employees = max(len(employee_names) if employee_names else 0, 
                       len(new_employee_names) if new_employee_names else 0, 
                       len(onshore_offshore) if onshore_offshore else 0)
    
    for i in range(max_employees):
        emp_name = employee_names[i] if i < len(employee_names) else ''
        new_emp_name = new_employee_names[i] if i < len(new_employee_names) else ''
        new_emp_email = new_employee_emails[i] if i < len(new_employee_emails) else ''
        location = onshore_offshore[i] if i < len(onshore_offshore) else ''
        service = tsheet_service[i] if i < len(tsheet_service) else ''
        bill_rate = bill_rates[i] if i < len(bill_rates) else ''
        cost_rate = cost_rates[i] if i < len(cost_rates) else ''
        
        # Only add if there's actual data
        if emp_name or new_emp_name or location or service or cost_rate:
            employee_data.append({
                'employee_name': emp_name,
                'new_employee_name': new_emp_name,
                'new_employee_email': new_emp_email,
                'location': location,
                'service': service,
                'bill_rate': bill_rate,
                'cost_rate': cost_rate
            })
            print(f"Added employee: {emp_name}, location: {location}, cost: {cost_rate}")
    
    # Process Section C data into clean list of dictionaries
    fixed_price_data = []
    fp_descriptions = form_data.get('fp_description[]', [])
    fp_amounts = form_data.get('fp_amount[]', [])
    
    print(f"Processing FP descriptions: {fp_descriptions}")
    print(f"Processing FP amounts: {fp_amounts}")
    
    max_fp = max(len(fp_descriptions) if fp_descriptions else 0, 
                len(fp_amounts) if fp_amounts else 0)
    
    for i in range(max_fp):
        description = fp_descriptions[i] if i < len(fp_descriptions) else ''
        amount = fp_amounts[i] if i < len(fp_amounts) else ''
        
        # Only add if there's actual data
        if description or amount:
            fixed_price_data.append({
                'description': description,
                'amount': amount
            })
            print(f"Added FP: {description}, amount: {amount}")
    
    print(f"Final employee_data: {employee_data}")
    print(f"Final fixed_price_data: {fixed_price_data}")
    
    # Pass clean data to template
    return render_template('utilities/project_setup_preview.html', 
                         data=form_data, 
                         employee_data=employee_data,
                         fixed_price_data=fixed_price_data)

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

def send_project_setup_email(project_setup, form_data):
    """Send email with PDF attachment"""
    try:
        from flask_mail import Message
        from app import mail
        from datetime import datetime
        import logging

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # Get recipients
        recipients = []
        if form_data.get('email_recipients'):
            recipients = [email.strip() for email in form_data['email_recipients'].split(',') if email.strip()]
        
        if not recipients:
            logger.warning("No valid email recipients found")
            return False

        logger.info(f"Preparing email for recipients: {recipients}")

        # Generate PDF
        pdf_data = generate_project_setup_pdf(project_setup, form_data)
        if not pdf_data:
            logger.error("Failed to generate PDF")
            return False

        # Create email
        msg = Message(
            subject=f"New Project Setup: {project_setup.project_name_quickbooks}",
            sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'),
            recipients=recipients,
            body=f"""Project Setup Notification\n\n
                  Project: {project_setup.project_name_quickbooks}\n
                  Customer: {project_setup.customer_name}\n
                  Submitted by: {project_setup.submitted_by}"""
        )

        # Attach PDF
        try:
            pdf_data.seek(0)
            filename = f"project_setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            msg.attach(filename, "application/pdf", pdf_data.read())
            logger.info("PDF attachment added successfully")
        except Exception as e:
            logger.error(f"Failed to attach PDF: {str(e)}")
            return False

        # Send email
        try:
            mail.send(msg)
            logger.info("Email sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Error in send_project_setup_email: {str(e)}")
        return False
        
        # Send email
        mail.send(msg)
        print(f"Email sent successfully to: {', '.join(recipients)}")
        
    except Exception as e:
        print(f"Error sending email: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise exception - continue even if email fails



#############################
def generate_simple_pdf(form_data):
    """Generate simple PDF with form data"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        story.append(Paragraph("Project Setup Form", styles['Title']))
        story.append(Spacer(1, 20))
        
        # Basic project info
        story.append(Paragraph(f"<b>Project Name:</b> {form_data.get('project_name_quickbooks', '')}", styles['Normal']))
        story.append(Paragraph(f"<b>Customer:</b> {form_data.get('customer_name', '')}", styles['Normal']))
        story.append(Paragraph(f"<b>Company:</b> {form_data.get('company_name', '')}", styles['Normal']))
        story.append(Paragraph(f"<b>Start Date:</b> {form_data.get('project_start_date', '')}", styles['Normal']))
        story.append(Paragraph(f"<b>End Date:</b> {form_data.get('estimated_end_date', '')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Employees
        story.append(Paragraph("<b>Employees:</b>", styles['Heading2']))
        employee_names = form_data.get('employee_name[]', [])
        cost_rates = form_data.get('cost_rate[]', [])
        
        for i, name in enumerate(employee_names):
            if name:
                cost = cost_rates[i] if i < len(cost_rates) else ''
                story.append(Paragraph(f"• {name} - Cost Rate: {cost}", styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Fixed Price Items
        story.append(Paragraph("<b>Fixed Price Items:</b>", styles['Heading2']))
        fp_descriptions = form_data.get('fp_description[]', [])
        fp_amounts = form_data.get('fp_amount[]', [])
        
        for i, desc in enumerate(fp_descriptions):
            if desc:
                amount = fp_amounts[i] if i < len(fp_amounts) else ''
                story.append(Paragraph(f"• {desc} - Amount: ${amount}", styles['Normal']))
        
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
        recipients = []
        if form_data.get('email_recipients'):
            recipients = [email.strip() for email in form_data['email_recipients'].split(',')]
        
        if not recipients:
            return
        
        subject = f"Project Setup: {form_data.get('project_name_quickbooks', 'New Project')}"
        
        html_body = f"""
        <h2>Project Setup Submitted</h2>
        <p><strong>Project:</strong> {form_data.get('project_name_quickbooks', '')}</p>
        <p><strong>Customer:</strong> {form_data.get('customer_name', '')}</p>
        <p>Complete details are attached as PDF.</p>
        """
        
        msg = Message(
            subject=subject,
            recipients=recipients,
            html=html_body,
            sender='ravindra.sonakiya@clovertex.com'
        )
        
        # Generate and attach PDF
        pdf_buffer = generate_simple_pdf(form_data)
        if pdf_buffer:
            filename = f"project_setup_{form_data.get('project_name_quickbooks', 'project')}.pdf"
            msg.attach(filename, "application/pdf", pdf_buffer.read())
            print(f"PDF attached: {filename}")
        
        mail.send(msg)
        print(f"Email with PDF sent to: {', '.join(recipients)}")
        
    except Exception as e:
        print(f"Email error: {e}")