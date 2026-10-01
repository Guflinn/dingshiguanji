@echo off
cd /d "%~dp0"
set "PYW=pythonw"
if not exist "%PYW%" set "PYW=pythonw"
start "" "%PYW%" "%~dp0ds_shutdown.py"
