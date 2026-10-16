@echo off
rem Starts EduCommute Matrix on this machine: database, backend and frontend,
rem all in Docker. Double-click it, or run it from a terminal.
setlocal
cd /d "%~dp0"

rem Add Docker's usual install folder, in case this terminal's PATH lacks it.
set "PATH=%PATH%;%ProgramFiles%\Docker\Docker\resources\bin"

docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
echo Starting Docker Desktop. This can take a minute or two...
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
:wait_for_docker
ping -n 6 127.0.0.1 >nul
docker info >nul 2>&1
if errorlevel 1 goto wait_for_docker
:docker_ready

echo Starting the database, the backend and the frontend...
docker compose up -d
if errorlevel 1 goto failed

echo.
echo The site is running at http://localhost:3000 and opens in your browser.
echo To stop everything, run in this folder: docker compose down
start "" http://localhost:3000
echo.
pause
goto :eof

:failed
echo.
echo Docker could not start the site. See the message above.
pause
