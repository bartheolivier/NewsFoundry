#!/bin/bash
PGDATA="$HOME/.local/share/newsfoundry_pgdata"
PG_CTL="/usr/lib/postgresql/16/bin/pg_ctl"

if [ ! -x "$PG_CTL" ]; then
    PG_CTL=$(which pg_ctl 2>/dev/null)
fi

if [ -z "$PG_CTL" ]; then
    echo "Erreur: pg_ctl introuvable."
    exit 1
fi

echo "Démarrage de PostgreSQL sur le port 5433..."
"$PG_CTL" -D "$PGDATA" -o "-p 5433 -k $PGDATA" -l "$PGDATA/postgres.log" start
