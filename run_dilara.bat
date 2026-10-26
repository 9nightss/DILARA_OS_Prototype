@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo DILARA's encrypted vault requires the cryptography package.
    echo Install it with: py -3 -m pip install -r requirements.txt
    pause
    exit /b 1
)
py -3 main.py
if errorlevel 1 pause
endlocal
