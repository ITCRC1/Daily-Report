"""Regenera el backup lógico completo de la DB de prod -> db/backups/prod_data_latest.sql
Se corre A MANO (antes lo disparaba un hook pre-commit, que ya no existe; además el
.sql quedó fuera de git -- ver db/backups/README.md). Version-independiente (server
Postgres 18): recorre pg_tables y arma INSERTs con session_replication_role=replica.

URL de prod: env DAILY_OPS_PROD_URL, o el archivo db/backups/.prod_conn (gitignored).
Si no hay URL o no hay red -> avisa y termina OK (no bloquea el commit)."""
import datetime
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONN_FILE = ROOT / "db" / "backups" / ".prod_conn"
OUT = ROOT / "db" / "backups" / "prod_data_latest.sql"


def _skip(msg: str):
    print(f"[backup] omitido: {msg}")
    sys.exit(0)


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return "'" + v.isoformat() + "'"
    if isinstance(v, uuid.UUID):
        return "'" + str(v) + "'"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    try:
        import psycopg2
    except ImportError:
        _skip("psycopg2 no disponible")

    url = os.environ.get("DAILY_OPS_PROD_URL")
    if not url and CONN_FILE.exists():
        url = CONN_FILE.read_text(encoding="utf-8").strip()
    if not url:
        _skip("sin URL de prod (.prod_conn ni env DAILY_OPS_PROD_URL)")
    url = url.replace("+psycopg2", "").replace("+asyncpg", "")

    try:
        conn = psycopg2.connect(url, connect_timeout=10)
    except Exception as e:  # noqa: BLE001
        _skip(f"no se pudo conectar a prod ({e})")

    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    tables = [r[0] for r in cur.fetchall()]

    # `alembic_version` se EXCLUYE a propósito: el restore corre primero
    # `alembic upgrade head`, que ya deja esa fila puesta. Incluirla hacía que
    # el INSERT chocara con la PK y, con `ON_ERROR_STOP=1`, abortara TODO el
    # restore dejando la base vacía (probado). La versión queda de referencia
    # en el encabezado, que es donde sirve: para saber contra qué esquema
    # restaurar.
    schema_version = ""
    if "alembic_version" in tables:
        tables.remove("alembic_version")
        try:
            cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
            row = cur.fetchone()
            schema_version = row[0] if row else ""
        except Exception:  # noqa: BLE001
            schema_version = ""

    lines = ["-- DAILY-OPS prod backup (logical, data-only) -- auto (pre-commit hook)",
             f"-- schema (alembic head): {schema_version or 'desconocido'}",
             "-- Restaurar en una DB con el esquema YA migrado a esa revision:",
             "--   alembic upgrade head && psql \"$URL\" -v ON_ERROR_STOP=1 -f este_archivo.sql",
             "SET session_replication_role = replica;", ""]
    total = 0
    for t in tables:
        cur.execute(f'SELECT * FROM "{t}"')
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        if not rows:
            continue
        collist = ", ".join(f'"{c}"' for c in cols)
        for row in rows:
            vals = ", ".join(lit(v) for v in row)
            lines.append(f'INSERT INTO "{t}" ({collist}) VALUES ({vals});')
        lines.append("")
        total += len(rows)
    lines.append("SET session_replication_role = DEFAULT;")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    conn.close()
    print(f"[backup] OK: {total} filas -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
