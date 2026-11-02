@echo off
rem Stop all alphaview containers. Data volumes and images are kept; start again with start.bat.
setlocal EnableExtensions
cd /d "%~dp0"

where docker >nul 2>nul || (echo error: Docker is not installed. & exit /b 1)
docker info >nul 2>nul || (echo error: Docker daemon is not running. Start Docker Desktop and retry. & exit /b 1)

call :compose down --remove-orphans || exit /b 1
echo.
echo alphaview stopped. Your data is preserved.
echo   Start again:      start.bat
echo   Wipe everything:  reset.bat
exit /b 0

:compose
if exist .env (
  docker compose -f infra\docker-compose.yml --env-file .env -p alphaview %*
) else (
  rem Compose still requires these variables to parse the file during teardown.
  set "JWT_SECRET=teardown-placeholder-not-a-real-secret"
  set "ENCRYPTION_KEY=unused"
  docker compose -f infra\docker-compose.yml -p alphaview %*
)
exit /b %errorlevel%
