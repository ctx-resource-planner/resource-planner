from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

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

# --- END OF UTILITIES BLUEPRINT ---
