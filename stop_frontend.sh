#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/.frontend.pid"

STOPPED=false

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Arrêt du frontend Next.js (PID: $PID)..."
        kill "$PID" 2>/dev/null
        STOPPED=true
    fi
    rm -f "$PID_FILE"
fi

PORT_PIDS=$(lsof -t -i :3000 2>/dev/null || fuser 3000/tcp 2>/dev/null)
if [ -n "$PORT_PIDS" ]; then
    echo "Fermeture des processus résiduels sur le port 3000 ($PORT_PIDS)..."
    kill -9 $PORT_PIDS 2>/dev/null
    STOPPED=true
fi

if [ "$STOPPED" = true ]; then
    echo "✅ Frontend Next.js arrêté avec succès."
else
    echo "ℹ️ Le frontend Next.js n'était pas en cours d'exécution."
fi
