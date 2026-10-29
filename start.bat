@echo off
rem Start every alphaview microservice with Docker Compose.
rem Usage: start.bat [up^|stop^|restart^|logs [service]^|status]
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "COMPOSE=docker compose -f infra\docker-compose.yml --env-file .env -p alphaview"
set "CMD=%~1"
if "%CMD%"=="" set "CMD=up"

where docker >nul 2>nul || (echo error: Docker is not installed. Install Docker Desktop: https://docs.docker.com/get-docker/ & exit /b 1)
docker compose version >nul 2>nul || (echo error: Docker Compose v2 is required. & exit /b 1)
docker info >nul 2>nul || (echo error: Docker daemon is not running. Start Docker Desktop and retry. & exit /b 1)

if /i "%CMD%"=="up"      goto :up
if /i "%CMD%"=="start"   goto :up
if /i "%CMD%"=="stop"    goto :stop
if /i "%CMD%"=="down"    goto :stop
if /i "%CMD%"=="restart" goto :restart
if /i "%CMD%"=="logs"    goto :logs
if /i "%CMD%"=="status"  goto :status
if /i "%CMD%"=="ps"      goto :status
echo error: unknown command "%CMD%". Use: up ^| stop ^| restart ^| logs [service] ^| status
exit /b 1

:stop
%COMPOSE% down
exit /b %errorlevel%

:status
%COMPOSE% ps
exit /b %errorlevel%

:logs
%COMPOSE% logs -f --tail=100 %2
exit /b %errorlevel%

:restart
%COMPOSE% down
goto :up

:up
if not exist .env call :make_env || exit /b 1
%COMPOSE% up -d --build --remove-orphans || exit /b 1
<nul set /p "=Waiting for services to become healthy"
for /l %%i in (1,1,100) do (
  curl.exe -fsS http://localhost:8000/health >nul 2>nul && goto :ready
  <nul set /p "=."
  timeout /t 3 /nobreak >nul
)
echo.
%COMPOSE% ps
echo error: gateway did not become healthy in time. Inspect with: start.bat logs
exit /b 1

:ready
echo  ready.
echo.
echo alphaview is running
echo   Web app      http://localhost:3000
echo   API gateway  http://localhost:8000
echo   Temporal UI  http://localhost:8080
echo.
echo Stop with: start.bat stop   ^|   Logs: start.bat logs [service]
exit /b 0

:make_env
echo Creating .env with freshly generated secrets...
rem Fernet key = urlsafe base64 of 32 random bytes.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$rng=[Security.Cryptography.RandomNumberGenerator]::Create();" ^
  "$j=New-Object byte[] 48; $rng.GetBytes($j); $jwt=([Convert]::ToBase64String($j)) -replace '[+/=]','';" ^
  "$k=New-Object byte[] 32; $rng.GetBytes($k); $key=[Convert]::ToBase64String($k).Replace('+','-').Replace('/','_');" ^
  "(Get-Content .env.example) -replace '^JWT_SECRET=.*',('JWT_SECRET='+$jwt) -replace '^ENCRYPTION_KEY=.*',('ENCRYPTION_KEY='+$key) | Set-Content -Encoding ascii .env"
exit /b %errorlevel%
