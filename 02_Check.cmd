@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run 01_Install.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pecvd_mcp.cli doctor
if errorlevel 1 goto :failed
echo See environment-report.json. See README.md for MCP client setup.
pause
exit /b 0
:failed
echo Check failed. Keep the error text.
pause
exit /b 1
