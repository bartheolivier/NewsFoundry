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

"$PG_CTL" -D "$PGDATA" status
