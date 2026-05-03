@echo off
cd /d "%~dp0\.."

python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r apps\demo_web\requirements.txt
if exist sample\requirements.txt (
  pip install -r sample\requirements.txt
  pip install -e sample\
)

echo.
echo Done. Web: cd apps\demo_web ^&^& uvicorn app:app --reload --host 127.0.0.1 --port 8765
echo.
pause
