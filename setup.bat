@echo off
REM One-time setup for Freshlytics on Windows. Run from the project folder.
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Python was not found. Install Python 3.10-3.12 from python.org and tick "Add to PATH". & exit /b 1)
where npm >nul 2>nul || (echo Node.js was not found. Install Node 18+ from nodejs.org. & exit /b 1)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example - edit it to point at your database.
)

echo.
echo [1/5] Creating Python environment in backend\venv ...
if not exist "backend\venv" python -m venv backend\venv || exit /b 1
call backend\venv\Scripts\activate.bat

echo.
echo [2/5] Installing backend packages and PyTorch (CPU) - this can take a few minutes ...
python -m pip install --upgrade pip
pip install -r backend\requirements.txt || exit /b 1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu || exit /b 1

echo.
echo [3/5] Installing frontend packages ...
pushd frontend
call npm install || (popd & exit /b 1)
popd

echo.
echo [4/5] Building the cleaned fruit dataset (downloads from GitHub + reads ml\raw) ...
set TRIES=0
:download
set /a TRIES+=1
python ml\build_dataset.py download
python ml\build_dataset.py finalize
if errorlevel 1 (
    if %TRIES% LSS 5 goto download
    echo Dataset build failed - check your internet connection and run setup.bat again.
    exit /b 1
)

echo.
echo [5/5] Training the model on the new dataset - this takes about 40-60 minutes ...
python ml\train.py --data ml\data_v2 --epochs 25 || exit /b 1
python ml\evaluate.py

echo.
echo Setup complete. Run start.bat to launch Freshlytics.
endlocal
