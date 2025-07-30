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
                        WHERE
                            e.is_active = true
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
                TO_CHAR(p.po_amount, 'FM$999,999,999,999,999.00') AS "PO Amount"
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
                TO_CHAR(a.start_date, 'YYYY-MM-DD') AS "Project Start Date",
                TO_CHAR(a.end_date, 'YYYY-MM-DD') AS "Project End Date",
                CONCAT(a.billable_allocation_percentage, '%') AS "Employee Allocation %"
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
                TO_CHAR(total_billable_hrs, 'FM999,999,999,999.00') AS "Total Billable Hrs",
                CASE 
                    WHEN total_hours > 0 THEN ROUND(CAST((total_billable_hrs / total_hours * 100) AS numeric), 2)
                    ELSE 0 
                END AS "Billable %",
                TO_CHAR(total_non_billable_hrs, 'FM999,999,999,999.00') AS "Total Non-Billable Hrs",
                CASE 
                    WHEN total_hours > 0 THEN ROUND(CAST((total_non_billable_hrs / total_hours * 100) AS numeric), 2)
                    ELSE 0 
                END AS "Non-Billable %"
            FROM 
                ytd_hours
            ORDER BY 
                service_line DESC
        """,
        "columns": [
            "Name",
            "Service Line",
            "Total Billable Hrs",
            "Billable %",
            "Total Non-Billable Hrs",
            "Non-Billable %"
        ]
    }
}