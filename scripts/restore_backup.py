"""Restaura db/backups/prod_data_latest.sql en una base ya migrada — SIN psql.

`SETUP_OTRA_PC.md` restaura con `psql -f`, pero psql solo existe donde hay un
PostgreSQL instalado localmente. Para cargar la base de Railway desde una PC que
solo tiene Python, este script hace lo mismo hablando por psycopg2 (la misma
dependencia que ya usa Alembic).

Uso:
    python scripts/restore_backup.py "postgresql://user:pass@host:port/railway"
    python scripts/restore_backup.py "$URL" --file db/backups/prod_data_2026-07-11.sql

Sin URL en la línea de comandos toma la env `DAILY_OPS_TARGET_URL`.

El dump NO es idempotente (son INSERTs sin ON CONFLICT): correrlo dos veces
duplica filas. Por eso el script se planta si la base ya tiene datos, salvo
`--force`.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUMP = ROOT / "db" / "backups" / "prod_data_latest.sql"
# Muestra de control: si alguna de estas tiene filas, la base NO está vacía.
PROBE_TABLES = ("stg_integrity_line", "fact_budget", "audit_run", "dim_property")
# Sentencias por viaje al servidor. 500 mantiene cada lote en ~130 KB.
BATCH = 500


def die(msg: str) -> None:
    print(f"[restore] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def statements(path: Path):
    """Corta el dump en sentencias. No basta con partir por líneas: un valor de
    texto (un comentario de hallazgo, por ejemplo) puede traer saltos de línea
    adentro. Se acumula hasta cerrar la sentencia con `;` Y tener las comillas
    balanceadas — el dump escapa la comilla simple duplicándola, así que la
    paridad del conteo alcanza."""
    buf = ""
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not buf and (not line.strip() or line.lstrip().startswith("--")):
                continue
            buf += line
            if buf.rstrip().endswith(";") and buf.count("'") % 2 == 0:
                yield buf.strip()
                buf = ""
    if buf.strip():
        yield buf.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Restaura el backup lógico en una base vacía ya migrada.")
    ap.add_argument("url", nargs="?", help="URL Postgres destino (o env DAILY_OPS_TARGET_URL)")
    ap.add_argument("--file", default=str(DEFAULT_DUMP), help="dump a restaurar")
    ap.add_argument("--force", action="store_true", help="restaurar aunque la base ya tenga datos")
    args = ap.parse_args()

    try:
        import psycopg2
    except ImportError:
        die("psycopg2 no está instalado — usá el python del venv del backend "
            "(backend\\.venv\\Scripts\\python.exe)")

    url = args.url or os.environ.get("DAILY_OPS_TARGET_URL")
    if not url:
        die("falta la URL destino (argumento o env DAILY_OPS_TARGET_URL)")
    url = url.replace("+psycopg2", "").replace("+asyncpg", "")

    dump = Path(args.file)
    if not dump.is_absolute():
        dump = ROOT / dump
    if not dump.exists():
        die(f"no existe el dump: {dump}")

    conn = psycopg2.connect(url, connect_timeout=20)
    conn.autocommit = True
    cur = conn.cursor()

    # 1) La base tiene que estar migrada (el dump no crea tablas) y vacía.
    cur.execute("SELECT to_regclass('public.alembic_version')")
    if cur.fetchone()[0] is None:
        die("la base no tiene esquema — corré primero `alembic upgrade head`")
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    target_rev = row[0] if row else None

    head = ""
    with dump.open(encoding="utf-8") as fh:
        for line in fh:
            if "alembic head" in line:
                head = line.split(":")[-1].strip()
                break
    if head and target_rev and head != target_rev:
        die(f"revisión no coincide: el dump espera '{head}' y la base está en "
            f"'{target_rev}'. Migrá a esa revisión antes de restaurar.")

    existing = 0
    for t in PROBE_TABLES:
        cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
        if cur.fetchone()[0] is None:
            continue
        cur.execute(f'SELECT count(*) FROM "{t}"')
        existing += cur.fetchone()[0]
    if existing and not args.force:
        die(f"la base ya tiene datos ({existing} filas en {', '.join(PROBE_TABLES)}). "
            "El dump duplicaría todo. Vaciala o pasá --force si sabés lo que hacés.")

    # 2) FKs desactivadas mientras se insertan (el dump no viene ordenado por
    #    dependencias). Requiere superusuario — en Railway el usuario por
    #    defecto lo es; si no, avisa y sigue (puede fallar por orden de FKs).
    try:
        cur.execute("SET session_replication_role = replica")
    except Exception as e:  # noqa: BLE001
        print(f"[restore] AVISO: no pude desactivar las FKs ({e}). "
              "Si falla algún INSERT por FK, restaurá con un usuario superusuario.")

    # 3) Datos, en UNA transacción: o entra todo o no entra nada.
    #
    # Se mandan de a LOTES, no de a una: contra una base remota (el proxy de
    # Railway) cada sentencia suelta es un viaje de ida y vuelta, y 58k viajes
    # tardan más de una hora. psycopg2 acepta varias sentencias separadas por
    # ';' en un solo execute() -- 58k INSERTs pasan a ser ~120 viajes.
    conn.autocommit = False
    inserted = 0
    lote: list[str] = []
    primera_del_lote = 0

    def _volcar() -> None:
        if lote:
            cur.execute("\n".join(lote))
            lote.clear()

    try:
        for stmt in statements(dump):
            if stmt.lower().startswith("set session_replication_role"):
                continue  # ya lo pusimos arriba, fuera de la transacción
            if not lote:
                primera_del_lote = inserted + 1
            lote.append(stmt)
            if stmt.lstrip().upper().startswith("INSERT"):
                inserted += 1
            if len(lote) >= BATCH:
                _volcar()
                print(f"[restore] {inserted} filas...")
        _volcar()
        conn.commit()
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        die(f"falló y se revirtió TODO (base intacta): {e}\n"
            f"  en el lote de las filas {primera_del_lote}-{inserted + 1}")
    finally:
        conn.autocommit = True
        try:
            cur.execute("SET session_replication_role = DEFAULT")
        except Exception:  # noqa: BLE001
            pass

    print(f"[restore] OK: {inserted} filas insertadas desde {dump.name}")
    for t in PROBE_TABLES:
        cur.execute(f'SELECT count(*) FROM "{t}"')
        print(f"[restore]   {t}: {cur.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
