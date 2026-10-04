#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Arrêt de tous les services NewsFoundry"
echo "=========================================="

echo ""
echo "1/3. Arrêt du Frontend Next.js..."
"$PROJECT_DIR/stop_frontend.sh"

echo ""
echo "2/3. Arrêt du Backend FastAPI..."
"$PROJECT_DIR/stop_backend.sh"

echo ""
echo "3/3. Arrêt de PostgreSQL..."
"$PROJECT_DIR/stop_db.sh"

echo ""
echo "=========================================="
echo "  🛑 Tous les services sont arrêtés."
echo "=========================================="
