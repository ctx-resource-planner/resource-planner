@echo off
cd /d C:\apps\resource_planner_web
call venv\Scripts\activate.bat
flask run --debug --host=0.0.0.0 --port=5000
