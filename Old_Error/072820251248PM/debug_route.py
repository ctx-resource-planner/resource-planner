@app.route('/debug/employees')
@login_required
def debug_employees():
    try:
        # Test basic employee query
        employees = Employee.query.limit(5).all()
        result = [{"id": e.id, "name": e.name} for e in employees]
        return jsonify({"status": "success", "count": len(result), "employees": result})
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "type": type(e).__name__
        }), 500
