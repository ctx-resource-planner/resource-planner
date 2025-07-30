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
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_wtf.csrf import CSRFProtect
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO






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
            
            # Convert single-item lists to single values
            form_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                        for k, v in form_data.items()}
            
            # Store form data in session for preview
            session['project_setup_data'] = form_data
            session.modified = True
            return redirect(url_for('utilities.project_setup_preview'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in project setup: {str(e)}", exc_info=True)
            flash("An error occurred while processing your request. Please try again.", "danger")
            return redirect(url_for('utilities.project_setup'))
    
    # GET request - show the form
    form_data = session.get('project_setup_data', {})
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template('utilities/project_setup.html', 
                         form_data=form_data,
                         employees=employees)

@utilities_bp.route('/project_setup_preview', methods=['GET', 'POST'])
@login_required
def project_setup_preview():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('index'))
    
    # Get form data from session
    form_data = session.get('project_setup_data')
    if not form_data:
        flash("No form data found. Please fill out the form first.", "warning")
        return redirect(url_for('utilities.project_setup'))
    
    if request.method == 'POST':
        try:
            if request.form.get('action') == 'edit':
                return redirect(url_for('utilities.project_setup'))
                
            elif request.form.get('action') == 'confirm':
                try:
                    # Start a transaction
                    db.session.begin_nested()
                    
                    # 1. Create Project with only valid fields
                    project_data = {
                        'name': form_data.get('project_name_quickbooks'),
                        'service_line': form_data.get('service_line'),
                        'project_type': form_data.get('project_type'),
                        'sow_start_date': datetime.strptime(form_data.get('project_start_date'), '%Y-%m-%d').date() if form_data.get('project_start_date') else None,
                        'sow_end_date': datetime.strptime(form_data.get('estimated_end_date'), '%Y-%m-%d').date() if form_data.get('estimated_end_date') else None,
                        'actual_start_date': datetime.strptime(form_data.get('project_start_date'), '%Y-%m-%d').date() if form_data.get('project_start_date') else None,
                        'po_amount': float(form_data.get('as_bid_gross_margin')) if form_data.get('as_bid_gross_margin') and form_data.get('as_bid_gross_margin').replace('.', '', 1).isdigit() else None
                    }
                    
                    # Only add non-None values
                    project = Project(**{k: v for k, v in project_data.items() if v is not None})
                    db.session.add(project)
                    db.session.flush()  # Get the project ID
                    
                    # 2. Process employees if any
                    if 'employee_name' in form_data:
                        employee_data = {
                            'names': form_data.get('employee_name', []),
                            'onshore_offshore': form_data.get('onshore_offshore', []),
                            'tsheet_service_names': form_data.get('tsheet_service_name', []),
                            'bill_rates': form_data.get('bill_rate', []),
                            'cost_rates': form_data.get('cost_rate', [])
                        }
                        
                        # Process each employee
                        for i in range(len(employee_data['names'])):
                            email = employee_data['names'][i]
                            if not email:
                                continue
                                
                            # Find or create employee
                            employee = Employee.query.filter_by(email=email).first()
                            if not employee and email.startswith('new_employee_'):
                                # Create new employee
                                employee = Employee(
                                    email=email,
                                    name=form_data.get(f'new_employee_name_{i}', 'New Employee'),
                                    is_active=True,
                                    service_line=form_data.get('service_line')
                                )
                                db.session.add(employee)
                                db.session.flush()
                            
                            # Create allocation
                            if employee:
                                allocation = Allocation(
                                    employee_id=employee.id,
                                    project_id=project.id,
                                    billable_allocation_percentage=100,  # Default to 100%
                                    start_date=project.sow_start_date or datetime.utcnow().date(),
                                    end_date=project.sow_end_date or (datetime.utcnow() + timedelta(days=365)).date()
                                )
                                db.session.add(allocation)
                    
                    # 3. Create ProjectSetup record with all form data
                    project_setup_data = {
                        'company_name': form_data.get('company_name'),
                        'customer_name': form_data.get('customer_name'),
                        'customer_abbreviation': form_data.get('customer_abbreviation'),
                        'project_name_quickbooks': form_data.get('project_name_quickbooks'),
                        'customer_address': form_data.get('customer_address'),
                        'customer_bill_contact_name': form_data.get('customer_bill_contact_name'),
                        'customer_bill_contact_email': form_data.get('customer_bill_contact_email'),
                        'customer_bill_contact_phone': form_data.get('customer_bill_contact_phone'),
                        'customer_po_number': form_data.get('customer_po_number'),
                        'project_type': form_data.get('project_type'),
                        'project_start_date': datetime.strptime(form_data.get('project_start_date'), '%Y-%m-%d').date() if form_data.get('project_start_date') else None,
                        'estimated_end_date': datetime.strptime(form_data.get('estimated_end_date'), '%Y-%m-%d').date() if form_data.get('estimated_end_date') else None,
                        'project_status': form_data.get('project_status'),
                        'as_bid_gross_margin': form_data.get('as_bid_gross_margin'),
                        'project_estimating_sheet_link': form_data.get('project_estimating_sheet_link'),
                        'email_recipients': form_data.get('email_recipients'),
                        'submitted_by': current_user.username
                    }
                    
                    # Only add non-None values
                    project_setup = ProjectSetup(**{k: v for k, v in project_setup_data.items() if v is not None})
                    db.session.add(project_setup)
                    
                    # Commit all changes
                    db.session.commit()
                    
                    # 4. Send email with PDF
                    try:
                        # Generate PDF
                        pdf_buffer = generate_simple_pdf(form_data)
                        
                        # Send email
                        success = send_project_email_with_pdf(form_data)
                        
                        if success:
                            flash("Project setup completed and email notification sent successfully!", "success")
                        else:
                            flash("Project setup completed, but there was an error sending the email notification.", "warning")
                            
                    except Exception as e:
                        current_app.logger.error(f"Error sending email: {str(e)}", exc_info=True)
                        flash("Project setup completed, but there was an error sending the email notification.", "warning")
                    
                    # Clear session data
                    if 'project_setup_data' in session:
                        del session['project_setup_data']
                    
                    return redirect(url_for('utilities.project_setup'))
                    
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error processing project setup: {str(e)}", exc_info=True)
                    flash(f"An error occurred: {str(e)}", "danger")
                    return redirect(url_for('utilities.project_setup'))
                    
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in project setup preview: {str(e)}", exc_info=True)
            flash("An error occurred while processing your request.", "danger")
            return redirect(url_for('utilities.project_setup'))
    
    # Show preview page
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template('utilities/project_setup_preview.html', 
                         data=form_data,
                         employees=employees)

    

####################################################
def send_project_email_with_pdf(form_data, pdf_buffer):
    """Send email with PDF attachment matching the screenshot format"""
    try:
        recipients = [email.strip() for email in form_data['email_recipients'].split(',') if email.strip()]
        if not recipients:
            return False

        msg = Message(
            subject=f"Project Setup Confirmation - {form_data.get('project_name_quickbooks', 'New Project')}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
            recipients=recipients
        )

        # Extract all required fields from form_data
        company_name = form_data.get('company_name', 'N/A')
        customer_name = form_data.get('customer_name', 'N/A')
        customer_abbreviation = form_data.get('customer_abbreviation', 'N/A')
        project_name = form_data.get('project_name_quickbooks', 'N/A')
        customer_address = form_data.get('customer_address', 'N/A')
        billing_contact = form_data.get('customer_bill_contact_name', 'N/A')
        billing_email = form_data.get('customer_bill_contact_email', 'N/A')
        billing_phone = form_data.get('customer_bill_contact_phone', 'N/A')
        po_number = form_data.get('customer_po_number', 'N/A')
        project_type = form_data.get('project_type', 'N/A')
        start_date = form_data.get('project_start_date', 'N/A')
        end_date = form_data.get('estimated_end_date', 'N/A')
        project_status = form_data.get('project_status', 'N/A')
        gross_margin = form_data.get('as_bid_gross_margin', 'N/A')
        estimating_sheet = form_data.get('project_estimating_sheet_link', 'N/A')

        # Employee/Contractor details
        employee_rows = ""
        for emp in form_data.get('employee_data', []):
            employee_rows += f"""
            <tr>
                <td>{emp.get('employee_name', 'N/A')}</td>
                <td>{emp.get('onshore_offshore', 'N/A')}</td>
                <td>{emp.get('tsheet_service_name', 'N/A')}</td>
                <td>{emp.get('bill_rate', 'N/A')}</td>
                <td>{emp.get('cost_rate', 'N/A')}</td>
            </tr>
            """

        # HTML email body matching the screenshot format
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-bottom: 1px solid #e1e5e9;
                    margin-bottom: 20px;
                }}
                .section {{
                    margin-bottom: 30px;
                    border: 1px solid #e1e5e9;
                    border-radius: 5px;
                    padding: 20px;
                }}
                .section-title {{
                    background-color: #f8f9fa;
                    padding: 10px 15px;
                    margin: -20px -20px 20px -20px;
                    border-bottom: 1px solid #e1e5e9;
                    font-size: 18px;
                    font-weight: bold;
                }}
                .detail-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                .detail-table th {{
                    text-align: left;
                    padding: 8px;
                    background-color: #f8f9fa;
                    border-bottom: 1px solid #e1e5e9;
                }}
                .detail-table td {{
                    padding: 8px;
                    border-bottom: 1px solid #e1e5e9;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: bold;
                    background-color: #28a745;
                    color: white;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e1e5e9;
                    font-size: 12px;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Project Setup Confirmation</h1>
                <p>Project: {project_name}</p>
            </div>
            
            <div class="section">
                <div class="section-title">Section A. Project & Customer Details</div>
                
                <table class="detail-table">
                    <tr>
                        <th>Company Name</th>
                        <td>{company_name}</td>
                    </tr>
                    <tr>
                        <th>Customer Name</th>
                        <td>{customer_name}</td>
                    </tr>
                    <tr>
                        <th>Customer Abbreviation</th>
                        <td>{customer_abbreviation}</td>
                    </tr>
                    <tr>
                        <th>Project Name (QuickBooks)</th>
                        <td>{project_name}</td>
                    </tr>
                    <tr>
                        <th>Customer Address</th>
                        <td>{customer_address}</td>
                    </tr>
                    <tr>
                        <th>Billing Contact</th>
                        <td>{billing_contact}</td>
                    </tr>
                    <tr>
                        <th>Contact Email</th>
                        <td>{billing_email}</td>
                    </tr>
                    <tr>
                        <th>Contact Phone</th>
                        <td>{billing_phone}</td>
                    </tr>
                    <tr>
                        <th>PO Number</th>
                        <td>{po_number}</td>
                    </tr>
                    <tr>
                        <th>Project Type</th>
                        <td>{project_type}</td>
                    </tr>
                    <tr>
                        <th>Start Date</th>
                        <td>{start_date}</td>
                    </tr>
                    <tr>
                        <th>Estimated End Date</th>
                        <td>{end_date}</td>
                    </tr>
                    <tr>
                        <th>Project Status</th>
                        <td><span class="status-badge">{project_status}</span></td>
                    </tr>
                    <tr>
                        <th>As-Bid Gross Margin</th>
                        <td>{gross_margin}%</td>
                    </tr>
                    <tr>
                        <th>Estimating Sheet Link</th>
                        <td><a href="{estimating_sheet}">View Sheet</a></td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">Section B. Employee/Contractor Details</div>
                
                <table class="detail-table">
                    <thead>
                        <tr>
                            <th>Employee/Contractor</th>
                            <th>Location</th>
                            <th>T sheet Service</th>
                            <th>Bill Rate</th>
                            <th>Cost Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {employee_rows}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">Section C. Fixed Price Details</div>
                
                <table class="detail-table">
                    <tr>
                        <th>Fixed Price Amount</th>
                        <td>N/A</td>
                    </tr>
                    <tr>
                        <th>Payment Schedule</th>
                        <td>N/A</td>
                    </tr>
                    <tr>
                        <th>Milestone 1</th>
                        <td>N/A</td>
                    </tr>
                    <tr>
                        <th>Milestone 2</th>
                        <td>N/A</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">Section D. Additional Information</div>
                
                <table class="detail-table">
                    <tr>
                        <th>Special Instructions</th>
                        <td>N/A</td>
                    </tr>
                    <tr>
                        <th>Email Recipients</th>
                        <td>{form_data['email_recipients']}</td>
                    </tr>
                </table>
            </div>
            
            <div class="footer">
                <p>This is an automated message. Please do not reply directly to this email.</p>
                <p>For support, contact: support@yourcompany.com</p>
            </div>
        </body>
        </html>
        """

        # Plain text version for non-HTML email clients
        msg.body = f"""
        PROJECT SETUP CONFIRMATION - {project_name}

        SECTION A. PROJECT & CUSTOMER DETAILS
        ------------------------------------
        Company Name: {company_name}
        Customer Name: {customer_name}
        Customer Abbreviation: {customer_abbreviation}
        Project Name (QuickBooks): {project_name}
        Customer Address: {customer_address}
        Billing Contact: {billing_contact}
        Contact Email: {billing_email}
        Contact Phone: {billing_phone}
        PO Number: {po_number}
        Project Type: {project_type}
        Start Date: {start_date}
        Estimated End Date: {end_date}
        Project Status: {project_status}
        As-Bid Gross Margin: {gross_margin}%
        Estimating Sheet Link: {estimating_sheet}

        SECTION B. EMPLOYEE/CONTRACTOR DETAILS
        --------------------------------------
        Employee/Contractor    Location    T sheet Service    Bill Rate    Cost Rate
        {''.join([f"{emp.get('employee_name', 'N/A')}    {emp.get('onshore_offshore', 'N/A')}    {emp.get('tsheet_service_name', 'N/A')}    {emp.get('bill_rate', 'N/A')}    {emp.get('cost_rate', 'N/A')}\n" for emp in form_data.get('employee_data', [])])}

        SECTION C. FIXED PRICE DETAILS
        ------------------------------
        Fixed Price Amount: N/A
        Payment Schedule: N/A
        Milestone 1: N/A
        Milestone 2: N/A

        SECTION D. ADDITIONAL INFORMATION
        --------------------------------
        Special Instructions: N/A
        Email Recipients: {form_data['email_recipients']}

        ---
        This is an automated message. For support, contact: support@yourcompany.com
        """

        # Attach PDF with a descriptive filename
        pdf_filename = f"Project_Setup_{project_name.replace(' ', '_')}.pdf"
        msg.attach(
            pdf_filename,
            "application/pdf",
            pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer
        )

        mail.send(msg)
        return True

    except Exception as e:
        current_app.logger.error(f"Email error: {str(e)}")
        return False
        
        



#############################
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO

def generate_simple_pdf(form_data):
    """Generate a clean PDF matching the desired format"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Define custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#2c3e50')
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=6,
        textColor=colors.HexColor('#3498db')
    )
    
    # Add title
    elements.append(Paragraph("Project Setup Details", title_style))
    elements.append(Spacer(1, 12))
    
    # Project Information
    elements.append(Paragraph("1. Project Information", section_style))
    project_data = [
        ["Project Name", form_data.get('project_name_quickbooks', 'N/A')],
        ["Customer", form_data.get('customer_name', 'N/A')],
        ["Project Type", form_data.get('project_type', 'N/A')],
        ["Status", form_data.get('project_status', 'Draft')],
        ["Start Date", form_data.get('project_start_date', 'N/A')],
        ["End Date", form_data.get('estimated_end_date', 'N/A')],
        ["PO Number", form_data.get('customer_po_number', 'N/A')],
        ["Gross Margin", form_data.get('as_bid_gross_margin', 'N/A')],
        ["Estimating Sheet", form_data.get('estimating_sheet_link', 'N/A')]
    ]
    
    project_table = Table(project_data, colWidths=[2*inch, 4*inch])
    project_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
    ]))
    elements.append(project_table)
    elements.append(Spacer(1, 12))
    
    # Billing Information
    elements.append(Paragraph("2. Billing Information", section_style))
    billing_data = [
        ["Billing Contact", form_data.get('customer_bill_contact_name', 'N/A')],
        ["Email", form_data.get('customer_bill_contact_email', 'N/A')],
        ["Phone", form_data.get('customer_bill_contact_phone', 'N/A')],
        ["Address", form_data.get('customer_address', 'N/A')]
    ]
    
    billing_table = Table(billing_data, colWidths=[2*inch, 4*inch])
    billing_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
    ]))
    elements.append(billing_table)
    elements.append(Spacer(1, 12))
    
    # Team Members
    if 'employee_name' in form_data and form_data['employee_name']:
        elements.append(Paragraph("3. Team Members", section_style))
        team_header = ["Name", "Role", "Location", "Bill Rate", "Cost Rate"]
        team_data = [team_header]
        
        # Handle both single and multiple employees
        employee_names = form_data['employee_name']
        if not isinstance(employee_names, list):
            employee_names = [employee_names]
            
        for i in range(len(employee_names)):
            if employee_names[i]:  # Only add if name exists
                team_data.append([
                    employee_names[i],
                    form_data.get('tsheet_service_name', [''])[i] if isinstance(form_data.get('tsheet_service_name'), list) else form_data.get('tsheet_service_name', ''),
                    form_data.get('onshore_offshore', [''])[i] if isinstance(form_data.get('onshore_offshore'), list) else form_data.get('onshore_offshore', ''),
                    form_data.get('bill_rate', [''])[i] if isinstance(form_data.get('bill_rate'), list) else form_data.get('bill_rate', ''),
                    form_data.get('cost_rate', [''])[i] if isinstance(form_data.get('cost_rate'), list) else form_data.get('cost_rate', '')
                ])
        
        team_table = Table(team_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 1*inch, 1*inch])
        team_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),  # Right-align numeric columns
        ]))
        elements.append(team_table)
        elements.append(Spacer(1, 12))
    
    # Fixed Price Items
    if 'fp_description' in form_data and form_data['fp_description']:
        elements.append(Paragraph("4. Fixed Price Items", section_style))
        fp_header = ["Description", "Amount"]
        fp_data = [fp_header]
        
        # Handle both single and multiple items
        fp_descriptions = form_data['fp_description']
        fp_amounts = form_data.get('fp_amount', [])
        if not isinstance(fp_descriptions, list):
            fp_descriptions = [fp_descriptions]
        if not isinstance(fp_amounts, list):
            fp_amounts = [fp_amounts]
            
        for i in range(len(fp_descriptions)):
            if fp_descriptions[i]:  # Only add if description exists
                fp_data.append([
                    fp_descriptions[i],
                    fp_amounts[i] if i < len(fp_amounts) else ''
                ])
        
        fp_table = Table(fp_data, colWidths=[5*inch, 1*inch])
        fp_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),  # Right-align amount column
        ]))
        elements.append(fp_table)
    
    # Build the PDF
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
    """Send email with PDF attachment containing all project details"""
    try:
        # 1. Prepare recipients
        recipients = [email.strip() for email in form_data['email_recipients'].split(',') if email.strip()]
        if not recipients:
            current_app.logger.warning("No valid email recipients")
            return False

        # 2. Generate PDF (keeping existing PDF generation)
        pdf_buffer = generate_simple_pdf(form_data)
        if not pdf_buffer:
            current_app.logger.error("Failed to generate PDF")
            return False

        # 3. Prepare email content with enhanced HTML
        project_name = form_data.get('project_name_quickbooks', 'Project')
        customer_name = form_data.get('customer_name', 'Customer')
        
        # Enhanced HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Project Setup: {project_name}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #2c3e50, #3498db);
                    color: white;
                    padding: 30px;
                    border-radius: 8px 8px 0 0;
                    margin-bottom: 20px;
                }}
                .card {{
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                    overflow: hidden;
                }}
                .card-header {{
                    background-color: #f8f9fa;
                    padding: 15px 20px;
                    border-bottom: 1px solid #eee;
                    font-size: 16px;
                    font-weight: 600;
                    color: #2c3e50;
                }}
                .card-body {{
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #eee;
                }}
                th {{
                    background-color: #f8f9fa;
                    color: #2c3e50;
                    font-weight: 600;
                }}
                .status-active {{
                    background-color: #d4edda;
                    color: #155724;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #6c757d;
                    font-size: 14px;
                }}
                .highlight {{
                    background-color: #f8f9fa;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-family: monospace;
                }}
                .btn {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #3498db;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin: 10px 0;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1 style="margin: 0; font-size: 24px;">Project Setup Confirmation</h1>
                <p style="margin: 5px 0 0; opacity: 0.9;">Details for {project_name}</p>
            </div>
            
            <div class="card">
                <div class="card-header">Project Overview</div>
                <div class="card-body">
                    <table>
                        <tr>
                            <td style="width: 40%; font-weight: 600;">Project Name</td>
                            <td>{form_data.get('project_name_quickbooks', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Customer</td>
                            <td>{customer_name}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Project Type</td>
                            <td>{form_data.get('project_type', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Status</td>
                            <td><span class="status-active">{form_data.get('project_status', 'Draft')}</span></td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Timeline</td>
                            <td>{form_data.get('project_start_date', 'N/A')} to {form_data.get('estimated_end_date', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">PO Number</td>
                            <td>{form_data.get('customer_po_number', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Gross Margin</td>
                            <td>{form_data.get('as_bid_gross_margin', 'N/A')}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <!-- Billing Information -->
            <div class="card">
                <div class="card-header">Billing Information</div>
                <div class="card-body">
                    <table>
                        <tr>
                            <td style="width: 40%; font-weight: 600;">Billing Contact</td>
                            <td>{form_data.get('customer_bill_contact_name', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Email</td>
                            <td>{form_data.get('customer_bill_contact_email', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Phone</td>
                            <td>{form_data.get('customer_bill_contact_phone', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 600;">Address</td>
                            <td>{form_data.get('customer_address', 'N/A')}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <!-- Team Members -->
            <div class="card">
                <div class="card-header">Team Members</div>
                <div class="card-body">
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Role</th>
                                <th>Location</th>
                                <th>Bill Rate</th>
                                <th>Cost Rate</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        # Add team members
        if 'employee_name' in form_data and any(form_data['employee_name']):
            for i in range(len(form_data['employee_name'])):
                if form_data['employee_name'][i]:
                    html_content += f"""
                    <tr>
                        <td>{form_data['employee_name'][i]}</td>
                        <td>{form_data.get('tsheet_service_name', [''])[i]}</td>
                        <td>{form_data.get('onshore_offshore', [''])[i]}</td>
                        <td>{form_data.get('bill_rate', [''])[i]}</td>
                        <td>{form_data.get('cost_rate', [''])[i]}</td>
                    </tr>
                    """

        html_content += """
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Fixed Price Items -->
            <div class="card">
                <div class="card-header">Fixed Price Items</div>
                <div class="card-body">
                    <table>
                        <thead>
                            <tr>
                                <th>Description</th>
                                <th>Amount</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        # Add fixed price items
        if 'fp_description' in form_data and any(form_data['fp_description']):
            for i in range(len(form_data['fp_description'])):
                if form_data['fp_description'][i]:
                    html_content += f"""
                    <tr>
                        <td>{form_data['fp_description'][i]}</td>
                        <td>{form_data.get('fp_amount', [''])[i]}</td>
                    </tr>
                    """

        # Email footer
        html_content += f"""
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="footer">
                <p>This is an automated notification. The detailed project setup information is attached as a PDF.</p>
                <p>If you have any questions, please contact the project manager.</p>
                <p><strong>Note:</strong> This email was generated automatically. Please do not reply to this message.</p>
            </div>
        </body>
        </html>
        """

        # 4. Create and send email
        msg = Message(
            subject=f"✅ Project Setup: {project_name}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@clovertex.com'),
            recipients=recipients
        )
        
        # Set HTML content
        msg.html = html_content
        
        # Plain text fallback
        msg.body = f"""Project Setup: {project_name}

A new project has been set up with the following details:

Project: {form_data.get('project_name_quickbooks', 'N/A')}
Customer: {form_data.get('customer_name', 'N/A')}
Type: {form_data.get('project_type', 'N/A')}
Status: {form_data.get('project_status', 'Draft')}
Start Date: {form_data.get('project_start_date', 'N/A')}
End Date: {form_data.get('estimated_end_date', 'N/A')}

Please see the attached PDF for complete details.

This is an automated message. Please do not reply to this email.
"""

        # Attach PDF
        msg.attach(
            f"project_{project_name.replace(' ', '_')}_details.pdf",
            "application/pdf",
            pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer
        )

        # Send email
        mail.send(msg)
        current_app.logger.info(f"Email with PDF sent to {', '.join(recipients)}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        

def process_project_setup_submission():
    try:
        from app import db, mail
        from models import ProjectSetup, Customer, Project, Employee, Allocation
        from flask_mail import Message
        from datetime import datetime
        import json
        
        # Get form data from session
        form_data = session.get('project_setup_data')
        if not form_data:
            flash("No form data found.", "danger")
            return redirect(url_for('utilities.project_setup'))
        
        # Start a database transaction
        db.session.begin()
        
        try:
            # Helper function to handle list data from form
            def get_list_data(key):
                value = form_data.get(key, [])
                if isinstance(value, list):
                    return value
                return [value] if value else []
            
            # Get employee data
            employee_emails = get_list_data('employee_name[]')
            new_employee_names = get_list_data('new_employee_name[]')
            new_employee_emails = get_list_data('new_employee_email[]')
            onshore_offshore = get_list_data('onshore_offshore[]')
            tsheet_services = get_list_data('tsheet_service_name[]')
            bill_rates = get_list_data('bill_rate[]')
            cost_rates = get_list_data('cost_rate[]')
            
            # Create or find Customer
            customer = Customer.query.filter_by(customer_name=form_data['company_name']).first()
            if not customer:
                customer = Customer(
                    customer_name=form_data['company_name'],
                    customer_abbreviation=form_data.get('customer_abbreviation', ''),
                    customer_address_1=form_data.get('customer_address', ''),
                    bill_contact_name=form_data.get('customer_bill_contact_name', ''),
                    bill_contact_email=form_data.get('customer_bill_contact_email', ''),
                    bill_contact_phone=form_data.get('customer_bill_contact_phone', '')
                )
                db.session.add(customer)
                db.session.flush()  # Get the customer ID
            
            # Create Project
            project = Project(
                project_name=form_data['project_name_quickbooks'],
                customer_id=customer.id,
                project_type=form_data.get('project_type', ''),
                status=form_data.get('project_status', 'Active'),
                start_date=datetime.strptime(form_data['project_start_date'], '%Y-%m-%d') if form_data.get('project_start_date') else None,
                end_date=datetime.strptime(form_data['estimated_end_date'], '%Y-%m-%d') if form_data.get('estimated_end_date') else None,
                po_number=form_data.get('customer_po_number', ''),
                description=form_data.get('project_description', '')
            )
            db.session.add(project)
            db.session.flush()  # Get the project ID
            
            # Process employees and allocations
            for i in range(len(employee_emails)):
                email = employee_emails[i]
                
                # Handle new employees
                if email == 'new' and i < len(new_employee_emails):
                    # Check if employee already exists by email
                    employee = Employee.query.filter_by(email=new_employee_emails[i]).first()
                    if not employee:
                        employee = Employee(
                            name=new_employee_names[i],
                            email=new_employee_emails[i],
                            is_active=True,
                            is_onshore=(onshore_offshore[i].lower() == 'onshore') if i < len(onshore_offshore) else True
                        )
                        db.session.add(employee)
                        db.session.flush()
                else:
                    # Get existing employee
                    employee = Employee.query.filter_by(email=email).first()
                
                if employee:
                    # Create allocation
                    allocation = Allocation(
                        employee_id=employee.id,
                        project_id=project.id,
                        tsheet_service_name=tsheet_services[i] if i < len(tsheet_services) else '',
                        bill_rate=float(bill_rates[i]) if i < len(bill_rates) and bill_rates[i] else 0.0,
                        cost_rate=float(cost_rates[i]) if i < len(cost_rates) and cost_rates[i] else 0.0,
                        start_date=project.start_date,
                        end_date=project.end_date,
                        is_active=True
                    )
                    db.session.add(allocation)
            
            # Commit all changes
            db.session.commit()
            
            # Send email notification
            send_project_setup_email(project, form_data)
            
            # Clear the session data
            session.pop('project_setup_data', None)
            
            flash('Project setup completed successfully!', 'success')
            return redirect(url_for('utilities.project_setup'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error in project setup: {str(e)}")
            flash(f'An error occurred while saving the project: {str(e)}', 'danger')
            return redirect(url_for('utilities.project_setup_preview'))
            
    except Exception as e:
        app.logger.error(f"Unexpected error in project setup: {str(e)}")
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('utilities.project_setup'))
        
        
        
@utilities_bp.route('/project_setup_submit', methods=['POST'])
@login_required
def project_setup_submit():
    """Handle project setup form submission"""
    try:
        # Get form data from session
        form_data = session.get('project_form_data')
        if not form_data:
            flash('No project data to submit', 'error')
            return redirect(url_for('utilities.project_setup'))
        
        # Save to database
        project = Project(
            name=form_data.get('project_name_quickbooks'),
            # ... (rest of your project fields)
        )
        
        db.session.add(project)
        db.session.commit()
        
        # Clear the session data
        session.pop('project_form_data', None)
        
        # Send email with PDF
        success = send_project_email_with_pdf(form_data)
        if success:
            flash('Project created and email sent successfully!', 'success')
        else:
            flash('Project created, but there was an error sending the email', 'warning')
            
        return redirect(url_for('utilities.project_setup'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in project setup: {str(e)}")
        flash('An error occurred while processing your request.', 'danger')
        return redirect(url_for('utilities.project_setup'))
    
    



    
    
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
    try:
        # Test data with all required fields
        test_data = {
            'email_recipients': 'ravindra.sonakiya@clovertex.com',  # CHANGE THIS
            'project_name_quickbooks': 'Test Project',
            'customer_name': 'Test Customer',
            'project_type': 'Test Type',
            'project_status': 'Active',
            'project_start_date': '2023-01-01',
            'estimated_end_date': '2023-12-31',
            # Add any other required fields that your PDF generation might need
            'customer_po_number': 'TEST123',
            'customer_bill_contact_name': 'Test Contact',
            'customer_bill_contact_email': 'contact@clovertex.com',
            'customer_bill_contact_phone': '123-456-7890'
        }
        
        print("\n=== Starting Email Test ===")
        print("1. Testing PDF generation...")
        
        # Test PDF generation first
        pdf = generate_simple_pdf(test_data)
        if not pdf:
            print("ERROR: PDF generation failed")
            return "Failed to generate test PDF"
        print("✓ PDF generated successfully")
        
        print("\n2. Testing email sending...")
        # Test email with PDF
        success = send_project_email_with_pdf(test_data)
        
        if success:
            print("✓ Email sent successfully")
            return "Test email with PDF sent successfully! Please check your email (including spam folder)."
        else:
            print("ERROR: Email sending failed")
            return "Failed to send test email. Check the Flask console for errors."
            
    except Exception as e:
        print(f"!!! UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
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
