@echo off
REM Проверяем, есть ли виртуальное окружение
IF NOT EXIST "venv" (
    echo Creating venv...
    python -m venv venv
)

REM Устанавливаем зависимости
echo Installing dependencies...
venv\Scripts\pip install -r requirements.txt

REM Запускаем основной скрипт
echo Running the script...
venv\Scripts\python watermark_script_updated.py

pause
