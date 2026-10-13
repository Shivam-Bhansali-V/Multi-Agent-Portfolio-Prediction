@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
echo ==== started %date% %time% ==== > logs\run_35.txt
python -c "import torch; print('torch', torch.__version__)" >> logs\run_35.txt 2>&1
if errorlevel 1 (
  echo PyTorch not found, installing the CPU version...
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu >> logs\run_35.txt 2>&1
)
python -m pip install pandas pyarrow scikit-learn lightgbm >> logs\run_35.txt 2>&1
echo Cleaning and features...
python -u scripts\30_clean_v2.py >> logs\run_35.txt 2>&1
python -u scripts\31_features.py >> logs\run_35.txt 2>&1
echo Rebuilding the baseline paper with LSTM (can take 30-60 minutes)...
python -u scripts\35_baseline_replication.py >> logs\run_35.txt 2>&1
python -u scripts\35b_paired_test.py >> logs\run_35.txt 2>&1
echo ==== finished %date% %time% ==== >> logs\run_35.txt
echo.
echo Done. Tell Claude it finished.
pause
