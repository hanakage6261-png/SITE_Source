@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%LocalAppData%\Programs\Python\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

if not exist "%~dp0entrypoint.py" (
  echo entrypoint.py was not found.
  pause
  exit /b 1
)

"%PYTHON%" "%~dp0entrypoint.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
if "%~1"=="" pause
exit /b %EXIT_CODE%
