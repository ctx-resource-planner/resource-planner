@echo off
cd /d C:\apps\resource_planner_web
call venv\Scripts\activate.bat
python -c "from app import app; app.run(host='0.0.0.0', port=5000)"
