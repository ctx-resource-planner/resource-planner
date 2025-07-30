# In models.py, update the Employee model to remove the recursive all() method
class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # Add other columns as needed

    # Relationships
    skill_associations = db.relationship('EmployeeSkill', back_populates='employee')
    allocations = db.relationship('Allocation', back_populates='employee')

    def __repr__(self):
        return f'<Employee {self.name}>'

    @classmethod
    def get_active(cls):
        """Return a query with active employees only."""
        return cls.query.filter_by(is_active=True)

# Add this after all model definitions to ensure all models are defined first
@event.listens_for(Employee, 'before_compile', retval=True)
def filter_inactive_employees(query):
    """Filter out inactive employees from all queries by default."""
    if query._execution_options.get('include_inactive', False):
        return query
    return query.filter(Employee.is_active == True)
