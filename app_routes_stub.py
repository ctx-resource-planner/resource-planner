from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import login_required, logout_user, login_user, current_user

app = Flask(__name__)

# --- Home / Employee Search ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# --- Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Placeholder login logic
    if request.method == 'POST':
        flash('Login not implemented.', 'info')
        return redirect(url_for('login'))
    return render_template('login.html')

# --- Logout ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Change Password ---
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        flash('Change password not implemented.', 'info')
        return redirect(url_for('change_password'))
    return render_template('change_password.html')

# --- Employees List ---
@app.route('/employees_list')
@login_required
def employees_list():
    return render_template('employees_list.html')

# --- Skills List ---
@app.route('/skills_list')
@login_required
def skills_list():
    return render_template('skills_list.html')

# --- Projects List ---
@app.route('/projects_list')
@login_required
def projects_list():
    return render_template('projects_list.html')

# --- Allocations List ---
@app.route('/allocations_list')
@login_required
def allocations_list():
    return render_template('allocations_list.html')

# --- END OF MAIN ROUTES STUB ---
