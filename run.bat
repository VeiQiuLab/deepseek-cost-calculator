@echo off
setlocal
cd /d "%~dp0"
if defined PYTHON_EXE (
  "%PYTHON_EXE%" app.py
) else (
  py -3 app.py
)
if errorlevel 1 (
  echo Failed. Install Python 3.10+ with Tcl/Tk, or set PYTHON_EXE.
  pause
  exit /b 1
)
