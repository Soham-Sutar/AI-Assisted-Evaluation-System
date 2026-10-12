#!/bin/sh
set -e
echo "Waiting for database..."
python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.core.config import get_settings
e = create_engine(get_settings().database_url)
for i in range(40):
    try:
        e.connect().execute(text("SELECT 1")); sys.exit(0)
    except Exception:
        time.sleep(1.5)
sys.exit("database not reachable")
PY
alembic upgrade head
if [ "$SEED_ON_START" = "true" ]; then python -m scripts.seed --sheets; fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
