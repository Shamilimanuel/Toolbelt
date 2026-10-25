@echo off
rem Toolbelt's installer: double-click it. The work is done by setup.ps1 next to it (read it first if you like).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause
