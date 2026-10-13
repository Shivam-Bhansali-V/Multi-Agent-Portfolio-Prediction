@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
echo ==== started %date% %time% ==== > logs\run_33.txt
echo Installing packages...
python -m pip install yfinance pandas requests pyarrow scikit-learn lightgbm >> logs\run_33.txt 2>&1
echo Downloading NIFTY 500 prices (about 25 minutes)...
python -u scripts\33_download_universe_ext.py >> logs\run_33.txt 2>&1
echo Cleaning and building features...
python -u scripts\30_clean_v2.py >> logs\run_33.txt 2>&1
python -u scripts\31_features.py >> logs\run_33.txt 2>&1
echo Running the point-in-time universe test...
python -u scripts\36_pit_universe.py >> logs\run_33.txt 2>&1
echo ==== finished %date% %time% ==== >> logs\run_33.txt
echo.
echo Done. Results: reports\phase5\checkpoint_5_6_pit_universe.csv and logs\run_33.txt. Tell Claude it finished.
pause
