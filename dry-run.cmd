@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" bridge.py --capture
pause
