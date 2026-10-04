#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  État des services NewsFoundry"
echo "=========================================="

# 1. PostgreSQL
echo -n "PostgreSQL (port 5433)      : "
if ss -ltn 'sport = :5433' 2>/dev/null | grep -q 5433 || nc -z localhost 5433 2>/dev/null; then
    echo "🟢 ACTIF"
else
    echo "🔴 ARRÊTÉ"
fi

# 2. Backend
echo -n "Backend FastAPI (port 8000) : "
if curl -s http://localhost:8000/ >/dev/null 2>&1; then
    echo "🟢 ACTIF (http://localhost:8000/docs)"
else
    echo "🔴 ARRÊTÉ"
fi

# 3. Frontend
echo -n "Frontend Next.js (port 3000): "
if curl -s http://localhost:3000/ >/dev/null 2>&1; then
    echo "🟢 ACTIF (http://localhost:3000)"
else
    echo "🔴 ARRÊTÉ"
fi

echo "=========================================="
