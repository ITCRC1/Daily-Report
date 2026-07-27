"""Tests de la reconciliación (§5.4) con datos sintéticos — no requiere archivos."""
from app.engine.reconcile import recon_kpis, reconcile
from app.ingest.opera import OperaHeader


def _h(tcode, ttype, total, gl=0.0):
    return OperaHeader(tcode=tcode, description=f"desc {tcode}", type=ttype,
                       total=total, guest_ledger=gl, package_ledger=0, ar_ledger=0, deposit_ledger=0)


def _i(tcode, cr=0.0, db=0.0):
    return {"tcode": tcode, "int_cr": cr, "int_db": db, "cuenta": "4x", "nombre": "n", "tc": 1}


def test_ok_revenue_cuadra():
    rows = reconcile([_h("1000", "REVENUE", 100.0)], [_i("1000", cr=100.0)])
    r = rows[0]
    assert r.estado == "OK"
    assert r.diferencia == 0.0


def test_discrepancia_revenue():
    rows = reconcile([_h("1000", "REVENUE", 100.0)], [_i("1000", cr=95.0)])
    assert rows[0].estado == "DISCREPANCIA"
    assert rows[0].diferencia == -5.0


def test_payment_regla_de_signo():
    # PAYMENT: integ = -int_db; OK si -int_db == opera.total
    rows = reconcile([_h("3700", "PAYMENT", -500.0)], [_i("3700", db=500.0)])
    assert rows[0].estado == "OK"
    assert rows[0].diferencia == 0.0


def test_falta_en_integrity():
    rows = reconcile([_h("2320", "REVENUE", 50.0)], [])
    assert rows[0].estado == "FALTA EN INTEGRITY"


def test_interno_no_es_faltante():
    rows = reconcile([_h("9910", "INTERNAL", 10.0)], [])
    assert rows[0].estado == "INTERNO"


def test_falta_en_opera():
    rows = reconcile([], [_i("7777", cr=30.0)])
    assert rows[0].estado == "FALTA EN OPERA"


def test_kpis():
    rows = reconcile(
        [_h("1000", "REVENUE", 100.0), _h("1050", "NON REVENUE", 10.0),
         _h("9910", "INTERNAL", 5.0)],
        [_i("1000", cr=100.0), _i("1050", cr=9.0)],
    )
    k = recon_kpis(rows)
    assert k["ok"] == 1          # 1000 cuadra
    assert k["discrepancia"] == 1  # 1050 difiere
    assert k["interno"] == 1     # 9910 interno
