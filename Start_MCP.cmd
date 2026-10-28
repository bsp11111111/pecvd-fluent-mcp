@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run 01_Install.cmd first. 1>&2
  exit /b 1
)
".venv\Scripts\python.exe" -m pecvd_mcp.server
