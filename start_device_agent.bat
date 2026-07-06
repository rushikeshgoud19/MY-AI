@echo off
title Mizune Device Agent
:: Connects this laptop to Mizune's cloud brain as a device node.
:: To auto-start on boot: press Win+R, type shell:startup, drop a shortcut to this file there.
cd /d "%~dp0"
echo Starting Mizune Device Agent (laptop node)...
.venv\Scripts\python.exe device_agent.py --server ws://40.123.215.32:8001/ws --name laptop
pause
