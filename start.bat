@echo off
REM Starts the Freshlytics API (port 8000) and website (port 3000) in two windows.
cd /d "%~dp0"

if not exist "backend\venv\Scripts\activate.bat" (
    echo Run setup.bat first.
    exit /b 1
)

start "Freshlytics API" cmd /k "cd /d "%~dp0backend" && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --port 8000"
start "Freshlytics website" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Freshlytics is starting. The website opens at http://localhost:3000
