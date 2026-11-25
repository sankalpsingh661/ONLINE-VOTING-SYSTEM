@echo off
title College Voting System
echo ===================================================
echo           College Online Voting System
echo ===================================================
echo.
cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH!
    echo Please install Python 3 from https://www.python.org/
    pause
    exit /b 1
)

echo Checking dependencies...
pip install -r requirements.txt --quiet

echo.
echo Starting Voting System server...
echo The application will be accessible at: http://127.0.0.1:5000
echo.
echo Opening browser in 2 seconds...
start "" http://127.0.0.1:5000

python app.py
pause
