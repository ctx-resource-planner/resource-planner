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
@login_required
def project_setup():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Debug: Print raw form data
        print("=== RAW FORM DATA ===")
        print("Form keys:", list(request.form.keys()))
        print("Form values:", dict(request.form))
        print("Form lists:", {key: request.form.getlist(key) for key in request.form.keys()})
        print("=== END RAW DATA ===")
        
        # Store form data properly
        form_data = {}
        for key in request.form:
            if key.endswith('[]'):
                form_data[key] = request.form.getlist(key)
                print(f"Array field {key}: {form_data[key]}")
            else:
                form_data[key] = request.form.get(key)
        
        # Debug: Print final form data
        print("=== FINAL FORM DATA ===")
        for key, value in form_data.items():
            print(f"{key}: {value}")
        print("=== END FORM DATA ===")
        
        session['project_setup_data'] = form_data
        return redirect(url_for('utilities.project_setup_preview'))
    
    from models import Employee
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    form_data = session.get('project_setup_data', {})
    return render_template('utilities/project_setup.html', employees=employees, form_data=form_data)

@utilities_bp.route('/project_setup_preview', methods=['GET', 'POST'])
@login_required
def project_setup_preview():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    form_data = session.get('project_setup_data')
    if not form_data:
        flash("No form data found. Please fill the form first.", "warning")
        return redirect('/')
    
    if request.method == 'POST' and request.form.get('action') == 'confirm':
        return process_project_setup_submission()
    
    return render_template('utilities/project_setup_preview.html', data=form_data)

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
            return redirect('/')
        
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
        send_project_setup_email(project_setup, form_data)
        
        success_msg = f"Project setup '{form_data.get('project_name_quickbooks')}' submitted successfully!"
        if new_employees_created:
            success_msg += f" Created {len(new_employees_created)} new employee(s)."
        if customer and customer.id:
            success_msg += f" Customer '{customer.customer_name}' processed."
        
        flash(success_msg, "success")
        session.pop('project_setup_data', None)
        return redirect(url_for('utilities.project_setup'))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing project setup: {str(e)}", "danger")
        return redirect(url_for('utilities.project_setup_preview'))

def send_project_setup_email(project_setup, form_data):
    """Send email with PDF attachment"""
    try:
        recipients = [email.strip() for email in form_data.get('email_recipients', '').split(',') if email.strip()]
        
        if not recipients:
            print("No email recipients found")
            return
        
        # Generate PDF attachment
        pdf_data = generate_project_setup_pdf(project_setup, form_data)
        
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

Submitted by: {project_setup.submitted_by}
Submitted at: {project_setup.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}

Please find the detailed project setup form attached as PDF.
        """
        
        # Attach PDF file
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"project_setup_{project_setup.project_name_quickbooks}_{ts}.pdf"
        
        msg.attach(
            filename=filename,
            content_type='application/pdf',
            data=pdf_data.read()
        )
        
        mail.send(msg)
        print(f"Email sent successfully to: {', '.join(recipients)}")
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        pass

def generate_project_setup_pdf(project_setup, form_data):
    """Generate comprehensive PDF with all form data"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from io import BytesIO
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=72)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        story.append(Paragraph("Project Setup Form", styles['Title']))
        story.append(Spacer(1, 20))
        
        # Section A: Project Details
        story.append(Paragraph("Section A: Project & Customer Details", styles['Heading2']))
        project_data = [
            ['Company:', form_data.get('company_name', '')],
            ['Customer:', form_data.get('customer_name', '')],
            ['Project Name:', form_data.get('project_name_quickbooks', '')],
            ['Customer Address:', form_data.get('customer_address', '')],
            ['Bill Contact:', form_data.get('customer_bill_contact_name', '')],
            ['Bill Email:', form_data.get('customer_bill_contact_email', '')],
            ['PO Number:', form_data.get('customer_po_number', '')],
            ['Gross Margin:', form_data.get('as_bid_gross_margin', '')],
        ]
        
        table = Table(project_data, colWidths=[120, 350])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
            #<!-- Section B: Employee/Contractor Details -->
            <div class="card mb-4">
                <div class="card-header bg-info text-white">
                    <h5 class="mb-0">Section B. Employee/Contractor Details</h5>
                </div>
                <div class="card-body">
                    {% if employee_data %}
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>Employee Email</th>
                                    <th>New Employee Name</th>
                                    <th>New Employee Email</th>
                                    <th>Location</th>
                                    <th>Service</th>
                                    <th>Bill Rate</th>
                                    <th>Cost Rate</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for emp in employee_data %}
                                    <tr>
                                        <td>{{ emp.employee_name }}</td>
                                        <td>{{ emp.new_employee_name }}</td>
                                        <td>{{ emp.new_employee_email }}</td>
                                        <td>{{ emp.location }}</td>
                                        <td>{{ emp.service }}</td>
                                        <td>{{ emp.bill_rate }}</td>
                                        <td>{{ emp.cost_rate }}</td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <p class="text-muted">No employee details provided.</p>
                    {% endif %}
                </div>
            </div>

            #<!-- Section C: Fixed Price Details -->
            <div class="card mb-4">
                <div class="card-header bg-info text-white">
                    <h5 class="mb-0">Section C. Fixed Price & Managed Service Details</h5>
                </div>
                <div class="card-body">
                    {% if fixed_price_data %}
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>Description</th>
                                    <th>Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for fp in fixed_price_data %}
                                    <tr>
                                        <td>{{ fp.description }}</td>
                                        <td>${{ fp.amount }}</td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <p class="text-muted">No fixed price details provided.</p>
                    {% endif %}
                </div>
            </div>
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"PDF Error: {e}")
        buffer = BytesIO()
        buffer.write(b"PDF generation failed")
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        # Fallback to simple text PDF if HTML-to-PDF fails
        return generate_simple_pdf_fallback(project_setup, form_data)

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