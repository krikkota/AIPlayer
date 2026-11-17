@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; assert sys.version_info[:2] == (3,12), 'Install Python 3.12 x64 to build AIPlayer'"
if errorlevel 1 goto fail
python -m venv .build-env
if errorlevel 1 goto fail
".build-env\Scripts\python.exe" -m pip install -c constraints.txt -r requirements-build.txt
if errorlevel 1 goto fail
".build-env\Scripts\python.exe" -m pip install --no-build-isolation -c constraints.txt -e .
if errorlevel 1 goto fail
".build-env\Scripts\python.exe" build.py
if errorlevel 1 goto fail
".build-env\Scripts\python.exe" packaging\build_installer.py
if errorlevel 1 goto fail
echo Build completed. The Windows Setup EXE is in outputs.
exit /b 0
:fail
echo Build failed. No release has been approved.
exit /b 1
