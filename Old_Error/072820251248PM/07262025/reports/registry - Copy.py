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
    "employee_skills_proficiency": {
        "title": "Employee Skills Proficiency",
        "description": "List of employees with their skills and proficiency.",
        "sql": """
            SELECT 
                e.name AS "Employee Name",
                e.email AS "Email",
                e.empid AS "Employee ID",
                e.service_line AS "Service Line",
                COALESCE(s.name, 'No skills listed') AS "Skill",
                COALESCE(es.proficiency, 'N/A') AS "Proficiency Level",
                CASE 
                    WHEN es.proficiency = 'Advanced' THEN 'Expert'
                    WHEN es.proficiency = 'Intermediate' THEN 'Proficient' 
                    WHEN es.proficiency = 'Basic' THEN 'Beginner'
                    WHEN es.proficiency IS NULL THEN 'Not Rated'
                    ELSE es.proficiency
                END AS "Proficiency Category"
            FROM 
                public.employees e
            LEFT JOIN 
                public.employee_skills es ON e.id = es.employee_id
            LEFT JOIN 
                public.skills s ON es.skill_id = s.id
            WHERE 
                e.is_active = true
        """,
        "columns": [
            "Employee Name",
            "Email",
            "Employee ID",
            "Service Line",
            "Skill",
            "Proficiency Level",
            "Proficiency Category"
        ]
    },
    "employee_projects_billable_allocation": {
        "title": "Employee Projects Billable Allocation",
        "description": "Shows each employee's current billable project allocations and allocation percentage.",
        "sql": """
            SELECT
                e.empid AS "Emp ID",
                e.name AS "Employee Name",
                p.project_name AS "Currently Allocated Project",
                a.start_date AS "Project Start Date",
                a.end_date AS "Project End Date",
                a.billable_allocation_percentage AS "Employee Allocation %"
            FROM
                employees e
            JOIN
                allocations a ON e.id = a.employee_id
            JOIN
                projects p ON a.project_id = p.id
            WHERE
                a.start_date <= CURRENT_DATE
                AND (a.end_date IS NULL OR a.end_date >= CURRENT_DATE)
        """,
        "columns": [
            "Emp ID",
            "Employee Name",
            "Currently Allocated Project",
            "Project Start Date",
            "Project End Date",
            "Employee Allocation %"
        ]
    }
}