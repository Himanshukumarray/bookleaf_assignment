"""Docker-free local PostgreSQL 16 + pgvector for development (uses the `pgserver` package).

    pip install pgserver
    python scripts/dev_postgres.py

Keeps the server running until Ctrl+C and prints the DATABASE_URL to put in backend/.env.
Not for production: use a managed PostgreSQL with the pgvector extension there.
"""
import asyncio
import time
from pathlib import Path

import asyncpg
import pgserver

DB_NAME = "bookleaf_support"
# Outside the repo on purpose: OneDrive-synced folders cause "sharing violation" crashes in PostgreSQL.
DATA_DIR = Path.home() / ".bookleaf_pgdata"


async def ensure_database(admin_uri: str) -> None:
    conn = await asyncpg.connect(admin_uri)
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", DB_NAME):
            await conn.execute(f"CREATE DATABASE {DB_NAME}")
    finally:
        await conn.close()


def main() -> None:
    server = pgserver.get_server(DATA_DIR, cleanup_mode=None)
    admin_uri = server.get_uri()
    asyncio.run(ensure_database(admin_uri))
    url = admin_uri.replace("postgresql://", "postgresql+asyncpg://").rsplit("/", 1)[0] + f"/{DB_NAME}"
    print("PostgreSQL is running. Put this in backend/.env:\n")
    print(f"DATABASE_URL={url}\n")
    print("Press Ctrl+C to stop.", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.cleanup()


if __name__ == "__main__":
    main()
