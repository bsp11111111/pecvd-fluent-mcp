@echo off
setlocal
cd /d "%~dp0"
py -3.11 --version
if errorlevel 1 goto :python_missing
py -3.11 -m venv .venv
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pecvd_mcp.cli mcp-config
if errorlevel 1 goto :failed
echo Installed. Next: double-click 02_Check.cmd.
pause
exit /b 0
:python_missing
echo Install Python 3.11 from python.org, including the Python launcher, then retry.
pause
exit /b 1
:failed
echo Installation failed. Keep the error text and retry after resolving it.
pause
exit /b 1
