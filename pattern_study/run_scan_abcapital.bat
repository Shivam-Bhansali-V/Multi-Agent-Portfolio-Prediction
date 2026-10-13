@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=python
where python >nul 2>&1 || set PY=py
if not exist logs mkdir logs
echo ==== Scan started %date% %time% ==== >> "logs\scan.txt"
echo Installing packages...
%PY% -m pip install yfinance pandas numpy matplotlib >> "logs\scan.txt" 2>&1
echo Downloading Aditya Birla Capital and scanning for patterns...
%PY% -u fetch_and_scan.py ABCAPITAL 5 > "logs\last_run.txt" 2>&1
set RC=%ERRORLEVEL%
type "logs\last_run.txt"
type "logs\last_run.txt" >> "logs\scan.txt"
echo ==== Scan finished %date% %time% (exit code %RC%) ==== >> "logs\scan.txt"
echo.
if not "%RC%"=="0" (
  echo [FAILED] exit code %RC%. See pattern_study\logs\last_run.txt and tell Claude.
) else (
  echo Done. The report is in pattern_study\results\scan_ABCAPITAL.md. Tell Claude it finished.
)
pause
