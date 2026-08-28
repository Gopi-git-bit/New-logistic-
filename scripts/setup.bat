@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo ==^> Zippy Logistics setup (Windows)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo pnpm not found. Install with: corepack enable
  exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
  echo docker not found. Install Docker Engine.
  exit /b 1
)

echo ==^> Installing node dependencies
pnpm install

if not exist .env (
  echo ==^> Creating .env from template
  copy .env.example .env
  echo Edit .env and fill real secrets before running services.
)

echo ==^> Validating Docker Compose
docker compose -f "infra\docker\docker-compose.yml" config >nul

echo ==^> M0 setup complete.
echo Next: run 'pnpm dev' to start dev servers, or 'docker compose -f infra/docker/docker-compose.yml up -d' for infra.
