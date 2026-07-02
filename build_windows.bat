@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Creating virtual environment...
py -3 -m venv .venv
if errorlevel 1 goto :error

echo [2/3] Installing dependencies...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\pip.exe install -r requirements-build.txt
if errorlevel 1 goto :error

echo [3/3] Building exe...
call .venv\Scripts\pyinstaller.exe --clean --noconfirm xhs_package_generator.spec
if errorlevel 1 goto :error

echo.
echo Build complete:
echo dist\XHS_Package_Generator.exe
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Please check the error above.
pause
exit /b 1
