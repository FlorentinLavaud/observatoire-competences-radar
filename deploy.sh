#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[deploy] Building Docker image using existing cache..."
docker compose build

echo "[deploy] Starting containers..."
docker compose up -d

echo "[deploy] Current containers:"
docker compose ps

echo "[deploy] Recent logs:"
docker compose logs --no-color --tail 30

echo "[deploy] Deployment completed."
