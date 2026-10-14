#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Zippy Logistics setup"

if ! command -v pnpm &>/dev/null; then
  echo "pnpm not found. Install with: corepack enable"
  exit 1
fi

if ! command -v docker &>/dev/null; then
  echo "docker not found. Install Docker Engine."
  exit 1
fi

echo "==> Installing node dependencies"
pnpm install

if [ ! -f .env ]; then
  echo "==> Creating .env from template"
  cp .env.example .env
  echo "Edit .env and fill real secrets before running services."
fi

echo "==> Validating Docker Compose"
docker compose -f infra/docker/docker-compose.yml config > /dev/null

echo "==> M0 setup complete."
echo "Next: run 'pnpm dev' to start dev servers, or 'docker compose -f infra/docker/docker-compose.yml up -d' for infra."
