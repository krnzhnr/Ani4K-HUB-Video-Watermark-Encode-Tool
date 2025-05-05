@echo off
IF NOT EXIST "venv\Lib" (
    python -m venv venv
    venv\Scripts\pip install -q -r requirements.txt
) ELSE (
    venv\Scripts\pip install -q --upgrade -r requirements.txt
)

venv\Scripts\python watermark_script_updated.py
pause