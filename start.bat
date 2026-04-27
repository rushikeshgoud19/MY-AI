@echo off
title Mizune Launcher
echo ========================================
echo   Starting Mizune AI Companion...
echo ========================================

:: Start Python backend in a new terminal
start "Mizune Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe server.py"

:: Wait 3 seconds for backend to initialize before starting frontend
timeout /t 3 /noq >nul

:: Start Electron frontend in a new terminal
start "Mizune Frontend" cmd /k "cd /d %~dp0 && npm start"

echo.
echo  Both terminals launched! You can close this window.
timeout /t 2 /noq >nul
