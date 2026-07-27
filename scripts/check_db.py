"""Chequeo rápido de una base DAILY-OPS: revisión de esquema + conteo de filas.

Sirve para (a) verificar que el deploy quedó bien, (b) comparar una base contra
otra antes de migrar datos.

    python scripts/check_db.py "postgresql://user:pass@host:port/railway"
"""
import sys

# Las que importan para saber si "está todo": master data + ingesta + auditoría.
TABLES = [
    "dim_property", "dim_department", "dim_payment_map", "dim_room_category",
    "dim_calendar", "app_user", "role", "app_config",
    "budget_monthly", "fact_budget", "fact_revenue_actual_daily",
    "stg_integrity_line", "fact_opera_txn", "fact_opera_txn_detail",
    "fact_room_stat", "fact_pos_check", "fact_bill_line",
    "fact_otb_daily", "fact_otb_monthly", "ingest_batch",
    "audit_run", "audit_finding",
]


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: python scripts/check_db.py <DATABASE_URL>", file=sys.stderr)
        sys.exit(2)
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 no está instalado — usá el python del venv del backend", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1].replace("+psycopg2", "").replace("+asyncpg", "")
    conn = psycopg2.connect(url, connect_timeout=20)
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.alembic_version')")
    if cur.fetchone()[0] is None:
        print("SIN ESQUEMA — falta `alembic upgrade head`")
        sys.exit(1)
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    print(f"alembic head: {row[0] if row else '(vacío)'}")

    total = 0
    for t in TABLES:
        cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
        if cur.fetchone()[0] is None:
            print(f"  {t:<24} (no existe)")
            continue
        cur.execute(f'SELECT count(*) FROM "{t}"')
        n = cur.fetchone()[0]
        total += n
        print(f"  {t:<24} {n}")
    print(f"total (tablas listadas): {total}")
    conn.close()


if __name__ == "__main__":
    main()
