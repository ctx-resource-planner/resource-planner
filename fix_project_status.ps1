# Save this as: C:\apps\resource_planner_web\fix_project_status.ps1

# 1. Backup current files
$backupDir = "C:\apps\resource_planner_web\backups\project_status_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir
Copy-Item "C:\apps\resource_planner_web\app.py" $backupDir
Copy-Item "C:\apps\resource_planner_web\templates\projects_list.html" $backupDir -ErrorAction SilentlyContinue

Write-Host "Backup created at: $backupDir" -ForegroundColor Green

# 2. Update models.py - Add status property to Project model
$modelsPath = "C:\apps\resource_planner_web\models.py"
$modelsContent = Get-Content $modelsPath -Raw

# Add status property to Project model
$statusProperty = @'

    @property
    def status(self):
        """Return 'Active' or 'Closed' based on project end date"""
        from datetime import date
        if hasattr(self, 'sow_end_date') and self.sow_end_date:
            return 'Active' if self.sow_end_date >= date.today() else 'Closed'
        return 'Active'

'@

# Add status property after the last method in Project class
$modelsContent = $modelsContent -replace '(def __repr__\(self\):\s+return f''<Project {self\.name}>'')', @'
$1

    # Status property to check if project is active or closed
    @property
    def status(self):
        """Return 'Active' or 'Closed' based on project end date"""
        from datetime import date
        if hasattr(self, 'sow_end_date') and self.sow_end_date:
            return 'Active' if self.sow_end_date >= date.today() else 'Closed'
        return 'Active'
'@

$modelsContent | Set-Content $modelsPath -Encoding UTF8
Write-Host "Updated models.py" -ForegroundColor Green

# 3. Update projects list template to show status badge
$projectsTemplate = Get-ChildItem -Path "C:\apps\resource_planner_web\templates" -Filter "*project*list*.html" -Recurse -File | Select-Object -First 1

if ($projectsTemplate) {
    $templateContent = Get-Content $projectsTemplate.FullName -Raw
    
    # Add status column header
    $templateContent = $templateContent -replace '(</th>\s*<th>Actions</th>)', '$1<th>Status</th>'
    
    # Add status badge to each project row
    $templateContent = $templateContent -replace '(<td>\s*<a href="[^"]*" class="[^"]*">[^<]*</a>.*?</td>\s*</tr>)', @'
$1
        <td>
            {% if project.status == 'Active' %}
                <span class="badge bg-success">Active</span>
            {% else %}
                <span class="badge bg-secondary">Closed</span>
            {% endif %}
        </td>
    </tr>
'@

    # Add filter dropdown if it doesn't exist
    if (-not ($templateContent -match "Show All Projects")) {
        $filterHtml = @'
    <div class="mb-3">
        <form method="get" class="d-flex gap-2">
            <select name="show_all" class="form-select" style="width: auto;" onchange="this.form.submit()">
                <option value="no" {% if not request.args.get('show_all') == 'yes' %}selected{% endif %}>Show Active Projects</option>
                <option value="yes" {% if request.args.get('show_all') == 'yes' %}selected{% endif %}>Show All Projects</option>
            </select>
        </form>
    </div>
'@
        $templateContent = $templateContent -replace '(<\!-- Add any filter controls here \-\->)', $filterHtml
    }

    $templateContent | Set-Content $projectsTemplate.FullName -Encoding UTF8
    Write-Host "Updated $($projectsTemplate.Name)" -ForegroundColor Green
}

# 4. Update projects list route to handle status filter
$appPath = "C:\apps\resource_planner_web\app.py"
$appContent = Get-Content $appPath -Raw

# Update the projects_list route to handle status filtering
$appContent = $appContent -replace '(@app\.route\([''"]/projects[''"]\)\s+@login_required\s+def projects_list\(\):.*?return render_template\([^)]+)', @'
@app.route('/projects')
@login_required
def projects_list():
    sort_by_param = request.args.get('sort_by', 'name')
    order_param = request.args.get('order', 'asc')
    show_all = request.args.get('show_all') == 'yes'
    
    query = Project.query
    
    # Filter by status if not showing all projects
    if not show_all:
        from datetime import date
        query = query.filter((Project.sow_end_date.is_(None)) | (Project.sow_end_date >= date.today()))
    
    # Handle sorting
    if hasattr(Project, sort_by_param): 
        column_to_sort = getattr(Project, sort_by_param)
        query = query.order_by(desc(column_to_sort) if order_param == 'desc' else asc(column_to_sort))
    else: 
        query = query.order_by(asc(Project.name))
    
    try: 
        projects_data = query.all()
    except Exception as e: 
        flash(f'Error fetching projects: {e}', 'danger')
        projects_data = []
        app.logger.error(f"Error fetching projects: {e}", exc_info=True)
    
    return render_template('projects_list.html', 
                         projects=projects_data, 
                         sort_by=sort_by_param,
                         current_order=order_param)
'@

$appContent | Set-Content $appPath -Encoding UTF8
Write-Host "Updated app.py" -ForegroundColor Green

Write-Host "`nUpdate completed successfully!" -ForegroundColor Green
Write-Host "Please restart your Flask application for the changes to take effect." -ForegroundColor Yellow