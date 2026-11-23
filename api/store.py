"""Document stores. Tests use memory. Render uses Postgres. The service sees the same shape either way."""

import copy
from pathlib import Path

from api.logic import COLLECTION_NAMES

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def _sql_statements(sql):
    """Split a migration file. psycopg runs one statement per execute call."""
    statements = []
    chunk = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        chunk.append(line)
        if line.strip().endswith(";"):
            statement = "\n".join(chunk).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            chunk = []
    tail = "\n".join(chunk).strip().rstrip(";").strip()
    if tail:
        statements.append(tail)
    return statements


def empty_state():
    return {"settings": None, "collections": {name: [] for name in COLLECTION_NAMES}}


class MemoryStore:
    def __init__(self):
        self.state = empty_state()

    def transaction(self, fn):
        state = copy.deepcopy(self.state)
        try:
            result = fn(state)
        except Exception as err:
            # Keep rate-limit bumps when a request is rejected.
            if err.__class__.__name__ == "ServiceError":
                self.state = state
            raise
        self.state = state
        return result


class PostgresStore:
    """One worker should serve the free web service. Writes take a transaction lock anyway."""

    def __init__(self, dsn):
        self.dsn = dsn
        self.conn = None

    def connect(self):
        import psycopg

        self.conn = psycopg.connect(self.dsn)
        self.conn.autocommit = False
        self.apply_migrations()
        return self

    def apply_migrations(self):
        files = sorted(MIGRATIONS.glob("*.sql"))
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  name TEXT PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            self.conn.commit()
            for path in files:
                cur.execute("SELECT 1 FROM schema_migrations WHERE name = %s", (path.name,))
                if cur.fetchone():
                    continue
                for statement in _sql_statements(path.read_text()):
                    cur.execute(statement)
                cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                self.conn.commit()

    def transaction(self, fn):
        from psycopg.types.json import Json

        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(8675309)")
                state = self._read(cur)
                try:
                    result = fn(state)
                except Exception as err:
                    if err.__class__.__name__ == "ServiceError":
                        self._write(cur, state, Json)
                        self.conn.commit()
                    else:
                        self.conn.rollback()
                    raise
                self._write(cur, state, Json)
            self.conn.commit()
            return result
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise

    def _read(self, cur):
        cur.execute("SELECT data FROM app_settings WHERE id = 1")
        row = cur.fetchone()
        settings = row[0] if row else None
        collections = {}
        for name in COLLECTION_NAMES:
            cur.execute(f"SELECT data FROM {name}")
            collections[name] = [item[0] for item in cur.fetchall()]
        return {"settings": settings, "collections": collections}

    def _write(self, cur, state, Json):
        cur.execute(
            """
            INSERT INTO app_settings (id, data) VALUES (1, %s)
            ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data
            """,
            (Json(state["settings"]),),
        )
        for name in COLLECTION_NAMES:
            rows = state["collections"][name]
            cur.execute(f"DELETE FROM {name}")
            for row in rows:
                cur.execute(
                    f"INSERT INTO {name} (id, data) VALUES (%s, %s)",
                    (row["id"], Json(row)),
                )


def load_catalog(path=None):
    import json

    data = json.loads((path or (ROOT / "data" / "listings.json")).read_text())
    catalog = {}
    categories = [row["id"] for row in data.get("categories", [])]
    for listing in data.get("listings", []):
        loc = listing.get("location") or {}
        catalog[listing["id"]] = {
            "id": listing["id"],
            "name": listing.get("name") or "",
            "email": listing.get("email") or "",
            "website": listing.get("website") or "",
            "phone": listing.get("phone") or "",
            "description": listing.get("description") or "",
            "costNotes": listing.get("costNotes") or "",
            "state": loc.get("state") or "",
            "county": loc.get("county") or "",
            "city": loc.get("city") or "",
            "category": listing.get("category") or "",
            "latitude": listing.get("latitude"),
            "longitude": listing.get("longitude"),
        }
    return {"listings": catalog, "categories": categories}


def load_site_modules(path=None):
    import json

    file_path = path or (ROOT / "data" / "site.json")
    if not file_path.exists():
        return None
    site = json.loads(file_path.read_text())
    return site.get("modules")
