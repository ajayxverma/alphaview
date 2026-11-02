@echo off
rem Delete all alphaview containers, data volumes and built images so the project starts from scratch.
rem Always asks for confirmation.
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

where docker >nul 2>nul || (echo error: Docker is not installed. & exit /b 1)
docker info >nul 2>nul || (echo error: Docker daemon is not running. Start Docker Desktop and retry. & exit /b 1)

echo WARNING: this permanently deletes ALL alphaview data on this machine:
echo   - all alphaview containers and the alphaview network
echo   - database volumes: users, workspaces, connected tools, AI provider keys,
echo     discovery runs, opportunities and crawled signals
echo   - locally built alphaview images (rebuilt automatically by start.bat)
echo.
set "ANSWER="
set /p "ANSWER=Type 'reset' to continue (anything else aborts): "
if /i not "!ANSWER!"=="reset" (
  echo Aborted. Nothing was deleted.
  exit /b 1
)

set "DEL_ENV=n"
set /p "DEL_ENV=Also delete .env (generated secrets and any server API keys you added)? [y/N] "
set "DEL_ART=n"
set /p "DEL_ART=Also delete local build artifacts (.venv, node_modules, .next, caches)? [y/N] "

echo Removing containers, network and data volumes...
call :compose down --volumes --remove-orphans || exit /b 1

echo Removing built alphaview images...
for /f "delims=" %%i in ('docker images -q --filter "reference=alphaview/*" 2^>nul') do docker image rm -f %%i >nul 2>nul
for /f "delims=" %%i in ('docker images -q --filter "reference=alphaview-*" 2^>nul') do docker image rm -f %%i >nul 2>nul

if /i "!DEL_ENV!"=="y" if exist .env del /f /q .env && echo Removed .env
if /i "!DEL_ENV!"=="yes" if exist .env del /f /q .env && echo Removed .env

set "ART=0"
if /i "!DEL_ART!"=="y" set "ART=1"
if /i "!DEL_ART!"=="yes" set "ART=1"
if "!ART!"=="1" (
  echo Removing local build artifacts...
  for %%d in (.venv node_modules apps\web\node_modules apps\web\.next .turbo apps\web\.turbo .pytest_cache .ruff_cache) do (
    if exist "%%d" rmdir /s /q "%%d"
  )
  for /d /r packages %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
  for /d /r services %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
)

echo.
echo Reset complete. Run start.bat to rebuild and start a fresh alphaview.
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
