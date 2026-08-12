@echo off
cd /d "%~dp0"
python loop_video_suite.py
if errorlevel 1 pause
