#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Démarrage de tous les services NewsFoundry"
echo "=========================================="

echo ""
echo "1/3. Base de données PostgreSQL (port 5433)..."
"$PROJECT_DIR/start_db.sh"

echo ""
echo "2/3. Backend FastAPI (port 8000)..."
"$PROJECT_DIR/start_backend.sh"

echo ""
echo "3/3. Frontend Next.js (port 3000)..."
"$PROJECT_DIR/start_frontend.sh"

echo ""
echo "=========================================="
echo "  🎉 Tous les services sont lancés !"
echo "  - Application Web : http://localhost:3000"
echo "  - API Backend     : http://localhost:8000"
echo "  - Swagger Docs    : http://localhost:8000/docs"
echo "  - PostgreSQL      : localhost:5433"
echo "  - Statut global   : ./status_all.sh"
echo "  - Arrêt global    : ./stop_all.sh"
echo "=========================================="
