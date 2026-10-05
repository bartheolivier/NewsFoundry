#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
PID_FILE="$PROJECT_DIR/.backend.pid"
LOG_FILE="$BACKEND_DIR/backend.log"

UV_BIN=$(which uv 2>/dev/null)
if [ -z "$UV_BIN" ] && [ -x "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
fi

if [ -z "$UV_BIN" ]; then
    echo "❌ Erreur: 'uv' est introuvable."
    exit 1
fi

if lsof -i :8000 >/dev/null 2>&1 || ss -ltn 'sport = :8000' 2>/dev/null | grep -q 8000; then
    echo "⚠️ Le port 8000 est déjà utilisé. Le backend semble déjà démarré."
    echo "   Pour l'arrêter : ./stop_backend.sh"
    exit 0
fi

echo "🚀 Démarrage du backend FastAPI sur le port 8000..."
cd "$BACKEND_DIR"
setsid nohup "$UV_BIN" run --env-file .env python src/main.py </dev/null > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
disown $BACKEND_PID 2>/dev/null
echo "$BACKEND_PID" > "$PID_FILE"

# Attente active que le serveur soit prêt (max 10s)
for i in {1..20}; do
    if curl -s http://localhost:8000/ >/dev/null 2>&1; then
        echo "✅ Backend FastAPI opérationnel ! (PID: $BACKEND_PID)"
        echo "   - API          : http://localhost:8000"
        echo "   - Swagger Docs : http://localhost:8000/docs"
        echo "   - Logs         : backend/backend.log"
        exit 0
    fi
    sleep 0.5
done

echo "⚠️ Le backend a démarré (PID: $BACKEND_PID), mais met un instant à répondre."
echo "   Consultez les logs : tail -f backend/backend.log"
