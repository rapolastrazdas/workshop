@echo off
setlocal
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe" set "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;%PATH%"
if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
where docker >nul 2>nul
if errorlevel 1 (
  echo Reikia idiegti ir paleisti Docker Desktop su WSL 2.
  echo Instrukcija: README.md
  pause
  exit /b 1
)
docker compose up --build -d --wait
if errorlevel 1 (
  echo Paleisti nepavyko. Patikrinkite, ar veikia Docker Desktop.
  pause
  exit /b 1
)
echo Programa paleista. Adresa rasite zemiau prie frontend.
docker compose port frontend 80
echo Numatytasis adresas: http://localhost:8080
pause
