@echo off
REM Rebuild the dataset and retrain the model (about 40-60 minutes).
cd /d "%~dp0"
call backend\venv\Scripts\activate.bat
python ml\build_dataset.py finalize || exit /b 1
python ml\train.py --data ml\data_v2 --epochs 25 || exit /b 1
python ml\evaluate.py
echo Done. Restart start.bat to use the new model.
