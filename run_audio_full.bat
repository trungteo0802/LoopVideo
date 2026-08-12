@echo off
cd /d "%~dp0"
python audio_full_tool.py
if errorlevel 1 pause
