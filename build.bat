@echo off
setlocal
cd /d "%~dp0"
if defined PYTHON_EXE (
  "%PYTHON_EXE%" -m venv .venv-build
) else (
  py -3 -m venv .venv-build
)
if errorlevel 1 goto fail
set "BUILD_PY=%~dp0.venv-build\Scripts\python.exe"
"%BUILD_PY%" -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
"%BUILD_PY%" -m unittest discover -v
if errorlevel 1 goto fail
"%BUILD_PY%" app.py --smoke-test
if errorlevel 1 goto fail
"%BUILD_PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --additional-hooks-dir hooks --name DeepSeekCalculator --distpath dist --workpath build app.py
if errorlevel 1 goto fail
start "" /wait "%~dp0dist\DeepSeekCalculator.exe" --smoke-test
if errorlevel 1 goto fail
echo Built: %~dp0dist\DeepSeekCalculator.exe
pause
exit /b 0
:fail
echo Build failed. See messages above. Install Python 3.10+ with Tcl/Tk.
pause
exit /b 1
