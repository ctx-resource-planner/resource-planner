from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# --- Main Reports List Page ---
@reports_bp.route('/reports_list')
@login_required
def reports_list():
    """Available Reports landing page."""
    return render_template('reports_list.html')

# --- Employee Allocation Matrix ---
@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    """Employee Allocation Matrix Report."""
    return render_template('allocation_matrix.html')

# --- Employee Monthly Utilization Report ---
@reports_bp.route('/monthwise_utilization_report')
@login_required
def monthwise_utilization_report():
    """Employee Monthly Utilization Report."""
    legend = {
        "Act": "Active Days",
        "Cap": "Capacity",
        "BHrs": "Billable Hours",
        "B%": "Billable %",
        "NBHrs": "Non-Billable Hours",
        # Add service line colors or more abbreviations as needed
    }
    return render_template('monthwise_utilization_report.html', legend=legend)

# --- Projects Summary ---
@reports_bp.route('/projects_summary')
@login_required
def projects_summary():
    """Projects Summary Report."""
    return render_template('projects_list.html')

# --- Employee Skills Proficiency ---
@reports_bp.route('/skills_proficiency')
@login_required
def skills_proficiency():
    """Employee Skills Proficiency Report."""
    return render_template('skills_list.html')

# --- Employee Projects Billable Allocation ---
@reports_bp.route('/projects_billable_allocation')
@login_required
def projects_billable_allocation():
    """Employee Projects Billable Allocation Report."""
    return render_template('report_view.html')

# --- Upload Utilization (Utility in Reports) ---
@reports_bp.route('/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    """Upload Utilization Data."""
    if request.method == 'POST':
        flash('Upload Utilization not implemented.', 'info')
        return redirect(url_for('reports.upload_utilization'))
    return render_template('upload_utilization.html')

# --- Resource Utilization Dashboard (Embedded) ---
@reports_bp.route('/resource_utilization_dashboard')
@login_required
def resource_utilization_dashboard():
    """Embedded Resource Utilization Dashboard."""
    return render_template('utilities/streamlit_iframe.html')

# --- Aliases for old routes (if needed) ---
@reports_bp.route('/resource_utilization_report')
@login_required
def resource_utilization_report():
    return redirect(url_for('reports.monthwise_utilization_report'))

# --- Excel and Email Export Placeholders ---
@reports_bp.route('/monthwise_utilization_report/excel')
@login_required
def utilization_excel():
    flash('Excel export not implemented.', 'info')
    return redirect(url_for('reports.monthwise_utilization_report'))

@reports_bp.route('/monthwise_utilization_report/email')
@login_required
def utilization_email():
    flash('Email export not implemented.', 'info')
    return redirect(url_for('reports.monthwise_utilization_report'))

# --- END OF REPORTS BLUEPRINT ---
