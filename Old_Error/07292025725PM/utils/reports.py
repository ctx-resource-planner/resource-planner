# utils/reports.py
from flask import send_file, current_app
from io import BytesIO
import pandas as pd
from datetime import datetime
from flask_mail import Message
from app import mail

def generate_excel_report(query, filename_prefix, columns=None):
    """Generate an Excel report from a SQLAlchemy query"""
    df = pd.read_sql_query(query.statement, query.session.bind)
    
    if columns:
        df = df[columns]
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Report', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Report']
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_length, 50))  # Cap width at 50
    
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        output,
        as_attachment=True,
        download_name=f'{filename_prefix}_{timestamp}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def send_report_email(query, template_name, subject, recipient_email, columns=None):
    """Send a report via email"""
    try:
        # Generate Excel file
        output = BytesIO()
        df = pd.read_sql_query(query.statement, query.session.bind)
        
        if columns:
            df = df[columns]
            
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Report', index=False)
        
        output.seek(0)
        
        # Create and send email
        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            html=f"<p>Please find attached the {template_name} report.</p>"
        )
        
        msg.attach(
            f"{template_name}_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            output.getvalue()
        )
        
        mail.send(msg)
        return True, None
        
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        return False, str(e)
