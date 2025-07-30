@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    try:
        skills_for_template = Skill.query.order_by(Skill.name).all()
        employees_for_dropdown = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        projects_for_dropdown = Project.query.order_by(Project.name).all()
        proficiency_choices = ['Basic', 'Moderate', 'Advanced']
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}", exc_info=True)
        return render_template('index.html', 
                            skills=[], 
                            employees=[], 
                            projects=[],
                            proficiency_choices=[],
                            results=[],
                            search_criteria={'search_type': 'skill'},
                            allocation_date_headers={},
                            selected_project_with_skills=None)
