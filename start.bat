@echo off
title Mizune Launcher
echo ========================================
echo   Starting Mizune AI Companion...
echo ========================================

:: Start Python Backend
start "Mizune Backend" python server.py

:: Start Tauri frontend compiled executable
start "Mizune Frontend" "src-tauri\target\release\mizune-ai.exe"

echo.
echo  Both systems launched! You can close this launcher window.
timeout /t 2 /noq >nul
