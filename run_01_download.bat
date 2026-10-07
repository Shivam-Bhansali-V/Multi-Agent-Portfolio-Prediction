@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
echo ==== Run started %date% %time% ==== >> logs\run_01.txt
python --version >> logs\run_01.txt 2>&1
echo Installing packages...
python -m pip install yfinance pandas requests >> logs\run_01.txt 2>&1
echo Downloading prices (about 5 minutes)...
powershell -NoProfile -Command "python -u scripts\01_download_prices.py 2>&1 | Tee-Object -FilePath logs\run_01.txt -Append"
echo ==== Run finished %date% %time% ==== >> logs\run_01.txt
echo.
echo Done. You can close this window and tell Claude it finished.
pause
