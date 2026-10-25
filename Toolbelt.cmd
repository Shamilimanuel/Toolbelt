@echo off
rem Starts Toolbelt. Better: use the "Toolbelt" entry in the Start menu (made on first start), which has no black window.
if exist "%LOCALAPPDATA%\Toolbelt\venv\Scripts\Toolbelt.exe" (
  start "" "%LOCALAPPDATA%\Toolbelt\venv\Scripts\Toolbelt.exe" "%~dp0main.py"
) else (
  start "" "%LOCALAPPDATA%\Toolbelt\venv\Scripts\pythonw.exe" "%~dp0main.py"
)
