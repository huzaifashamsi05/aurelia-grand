@echo off
rem Loads the AureliaGrand database into Azure SQL Database (run once).
cd /d "%~dp0"
set "VENV=%USERPROFILE%\.venvs\aurelia-grand"
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" deploy_to_azure.py
) else (
    python deploy_to_azure.py
)
pause
