#!/usr/bin/env bash
set -euo pipefail

# Single-command deployment script for Jarvis Personal Assistant
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Deploying Jarvis..."

# 1. Verify Docker and Docker Compose are available
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Error: Docker is not installed or not in PATH."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "❌ Error: Docker Compose is not installed."
  exit 1
fi

# 2. Ensure local data directory exists for SQLite volume mount
mkdir -p data

# 3. Build and start the container in detached mode
echo "📦 Building and starting container..."
$COMPOSE_CMD up -d --build --remove-orphans

# 4. Wait for health check
echo "⏳ Waiting for Jarvis API to become healthy..."
MAX_RETRIES=20
COUNT=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
    echo "⚠️  Jarvis did not respond to /health in time. Check logs with:"
    echo "    $COMPOSE_CMD logs -f"
    exit 1
  fi
  sleep 1
done

echo "✅ Jarvis is live and healthy!"
echo "🌐 Web UI:  http://localhost:8000"
echo "🩺 Health:  http://localhost:8000/health"
echo "📜 Logs:    $COMPOSE_CMD logs -f"
echo "🛑 Stop:    $COMPOSE_CMD down"
