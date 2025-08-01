@app.route('/allocations')
@login_required
def allocations_list():
    try:
        allocations = Allocation.query.options(
            db.selectinload(Allocation.employee),
            db.selectinload(Allocation.project)
        ).join(Employee).filter(Employee.is_active == True).order_by(Allocation.start_date.desc()).all()
        return render_template('allocations_list.html', allocations=allocations)
    except Exception as e:
        flash(f'Error fetching allocations: {e}', 'danger')
        app.logger.error(f"Error in allocations_list: {e}", exc_info=True)
        return render_template('allocations_list.html', allocations=[])
