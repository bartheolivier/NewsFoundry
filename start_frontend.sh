#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PID_FILE="$PROJECT_DIR/.frontend.pid"
LOG_FILE="$FRONTEND_DIR/frontend.log"

NPM_BIN=$(which npm 2>/dev/null)
if [ -z "$NPM_BIN" ] && [ -x "$HOME/.nvm/versions/node/$(ls -1 $HOME/.nvm/versions/node 2>/dev/null | tail -n 1)/bin/npm" ]; then
    NPM_BIN="$HOME/.nvm/versions/node/$(ls -1 $HOME/.nvm/versions/node 2>/dev/null | tail -n 1)/bin/npm"
fi

if [ -z "$NPM_BIN" ]; then
    echo "❌ Erreur: 'npm' est introuvable."
    exit 1
fi

if lsof -i :3000 >/dev/null 2>&1 || ss -ltn 'sport = :3000' 2>/dev/null | grep -q 3000; then
    echo "⚠️ Le port 3000 est déjà utilisé. Le frontend semble déjà démarré."
    echo "   Pour l'arrêter : ./stop_frontend.sh"
    exit 0
fi

echo "🚀 Démarrage du frontend Next.js sur le port 3000..."
cd "$FRONTEND_DIR"
nohup "$NPM_BIN" run dev </dev/null > "$LOG_FILE" 2>&1 &
FRONTEND_PID=$!
disown $FRONTEND_PID 2>/dev/null
echo "$FRONTEND_PID" > "$PID_FILE"

# Attente active que Next.js soit prêt (max 15s)
for i in {1..30}; do
    if curl -s http://localhost:3000/ >/dev/null 2>&1; then
        echo "✅ Frontend Next.js opérationnel ! (PID: $FRONTEND_PID)"
        echo "   - Application : http://localhost:3000"
        echo "   - Logs        : frontend/frontend.log"
        exit 0
    fi
    sleep 0.5
done

echo "⚠️ Le frontend a démarré (PID: $FRONTEND_PID). Next.js finalise sa compilation."
echo "   - Application : http://localhost:3000"
echo "   - Logs        : tail -f frontend/frontend.log"
