# reports/registry.py

REPORTS = {
    "utilization_report": {
        "title": "Employee Monthly Utilization Report",
        "description": "Monthly billable and non-billable utilization by employee and service line.",
        "sql": """
            SELECT
                e.name AS "Employee Name",
                emu.service_line AS "Service Line",
                emu.month AS "Month",
                emu.billable_hours AS "Billable Hours",
                emu.billable_percent AS "Billable %",
                emu.non_billable_hours AS "Non-Billable Hours",
                emu.non_billable_percent AS "Non-Billable %",
                emu.location AS "Location"
            FROM
                employee_monthly_utilization emu
            JOIN
                employees e ON emu.employee_id = e.id
        """,
        "columns": [
            "Employee Name",
            "Service Line",
            "Month",
            "Billable Hours",
            "Billable %",
            "Non-Billable Hours",
            "Non-Billable %",
            "Location"
        ]
    },
    "ytd_hours_report": {
        "title": "YTD Employee Hours Report",
        "description": "Year-to-date billable and non-billable hours by employee with percentages.",
        "sql": """
            WITH ytd_hours AS (
                SELECT 
                    e.name,
                    e.service_line,
                    COALESCE(SUM(CASE WHEN tu.is_billable = TRUE THEN tu.hours ELSE 0 END), 0) AS total_billable_hrs,
                    COALESCE(SUM(CASE WHEN tu.is_billable = FALSE THEN tu.hours ELSE 0 END), 0) AS total_non_billable_hrs,
                    COALESCE(SUM(tu.hours), 0) AS total_hours
                FROM 
                    employees e
                LEFT JOIN 
                    timesheet_uploads tu ON e.email = tu.username
                WHERE 
                    tu.local_date BETWEEN DATE_TRUNC('year', CURRENT_DATE) AND CURRENT_DATE
                    AND e.is_active = TRUE
                GROUP BY 
                    e.name, e.service_line
            )
            SELECT 
                name AS "Name",
                service_line AS "Service Line",
                total_billable_hrs AS "Total Billable Hrs",
                CASE 
                    WHEN total_hours > 0 THEN ROUND(CAST((total_billable_hrs / total_hours * 100) AS numeric), 2)
                    ELSE 0 
                END AS "Billable %",
                total_non_billable_hrs AS "Total Non-Billable Hrs",
                CASE 
                    WHEN total_hours > 0 THEN ROUND(CAST((total_non_billable_hrs / total_hours * 100) AS numeric), 2)
                    ELSE 0 
                END AS "Non-Billable %"
            FROM 
                ytd_hours
            ORDER BY 
                name
        """,
        "columns": [
            "Name",
            "Service Line",
            "Total Billable Hrs",
            "Billable %",
            "Total Non-Billable Hrs",
            "Non-Billable %"
        ]
    },
    "Projects Summary": {
        "title": "Projects Summary",
        "description": "Project details for managers.",
        "sql": """
            SELECT
                p.project_name AS "Name",
                CONCAT(p.service_line, ' + ', p.project_type) AS "Service Line + Project Type",
                TO_CHAR(p.sow_start_date, 'YYYY-MM-DD') AS "SOW Start",
                TO_CHAR(p.sow_end_date, 'YYYY-MM-DD') AS "SOW End",
                TO_CHAR(p.actual_start_date, 'YYYY-MM-DD') AS "Actual Start",
                TO_CHAR(p.actual_end_date, 'YYYY-MM-DD') AS "Actual End",
                '$' || p.po_amount AS "PO Amount"
            FROM
                public.projects p
        """,
        "columns": [
            "Name",
            "Service Line + Project Type",
            "SOW Start",
            "SOW End",
            "Actual Start",
            "Actual End",
            "PO Amount"
        ]
    },
    # ... (keep all other existing reports)
}