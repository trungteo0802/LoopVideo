@echo off
cd /d "%~dp0"
python video_loop_tool.py
if errorlevel 1 pause
