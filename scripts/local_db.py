"""
local_db.py — run the local development Postgres.

pgserver ships PostgreSQL binaries as a pip package, so this needs no Docker,
no Homebrew and no system Postgres. The server lives in .pgdata/ (gitignored)
and stops when this process stops, so keep it running in its own terminal:

    .venv/bin/python scripts/local_db.py

It prints the DSN to put in .env as DATABASE_URL. get_client() picks Postgres
whenever DATABASE_URL is set, and falls back to Supabase otherwise.

    --migrate   apply migrations/*.sql in order, then exit
    --dsn       print the DSN and exit
"""

import pathlib
import sys
import time

import pgserver

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / ".pgdata"


def server():
    DATA_DIR.mkdir(exist_ok=True)
    return pgserver.get_server(str(DATA_DIR))


def migrate(db) -> int:
    files = sorted((DATA_DIR.parent / "migrations").glob("*.sql"))
    failed = 0
    for f in files:
        try:
            db.psql(f.read_text())
            print(f"  applied {f.name}")
        except Exception as e:
            print(f"  FAILED  {f.name}: {str(e)[:200]}")
            failed += 1
    print(f"{len(files) - failed}/{len(files)} migrations applied")
    return failed


if __name__ == "__main__":
    db = server()
    if "--dsn" in sys.argv:
        print(db.get_uri())
        sys.exit(0)
    if "--migrate" in sys.argv:
        sys.exit(1 if migrate(db) else 0)
    print(f"Postgres running.\nDATABASE_URL={db.get_uri()}\nCtrl-C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopped")
