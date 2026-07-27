"""Motor de Cash (etapa 3): buckets de dos niveles (§5.5) contra el 2026-06-08 real.

Ese día solo hay 2 pagos en Opera (tcodes 3700 CASH CRC y 3721 BAC USD MC,
total Opera = -317.87). Validado por reconciliación: el pivote de cash en USD
(deb-cred, signo opuesto a revenue por §5.3) debe dar +317.87.
"""
import pytest

from app.engine.cash import (
    BANK_ONLY_BANKS,
    BANK_ONLY_TIPOS,
    CASH_RELEVANT_BANKS,
    cash_pivot,
    currency_basis_pivot,
    is_bank_only,
    is_cash_relevant,
    payment_lines_from_integrity,
)

# dim_payment_map real para los 2 tcodes del 06-08 (ver PaymentMap sembrado)
PAYMENT_MAP = {
    "3700": {"banco_codigo": "CASH", "tipo_pago": "Efectivo", "marca_metodo": "Cash",
             "cash_flow": "Real Cash", "canal": "Cash", "report_bucket": "Cash"},
    "3721": {"banco_codigo": "BAC", "tipo_pago": "Tarjeta", "marca_metodo": "MasterCard",
             "cash_flow": "Real Cash", "canal": "POS", "report_bucket": "BAC Cards POS"},
}

# líneas reales de stg_integrity_line del 2026-06-08 para esos tcodes
INTEGRITY_ROWS_0608 = [
    {"tcode": "3700", "deb_usd": 7.91, "cred_usd": 0.0, "deb_col": 3661.22, "cred_col": 0.0},
    {"tcode": "3721", "deb_usd": 309.96, "cred_usd": 0.0, "deb_col": 143468.09, "cred_col": 0.0},
]


def test_is_cash_relevant_amplio():
    for b in ("BAC", "BCR", "BNCR", "LAF", "CASH", "SINPE", "ROOM", "HOUSE", "AR"):
        assert is_cash_relevant(b)
    assert not is_cash_relevant("PAYPAL")  # fuera del set → no cash-relevant
    assert not is_cash_relevant(None)


def test_is_bank_only_estricto():
    assert is_bank_only("Tarjeta", "BAC")
    assert is_bank_only("Transferencia", "BNCR")
    assert not is_bank_only("Efectivo", "CASH")   # CASH no es banco real
    assert not is_bank_only("Tarjeta", "ROOM")    # ROOM no está en BANK_ONLY_BANKS


def test_pivot_reconcilia_con_opera_0608():
    """Total cash en USD debe cuadrar con |payment_total| de Opera (317.87)."""
    lines = payment_lines_from_integrity(INTEGRITY_ROWS_0608)
    p = cash_pivot(lines, PAYMENT_MAP)
    assert p["total"] == pytest.approx(317.87, abs=0.01)
    assert p["real_cash"] == pytest.approx(317.87, abs=0.01)
    assert p["non_cash"] == pytest.approx(0.0, abs=0.01)


def test_pivot_buckets_0608():
    lines = payment_lines_from_integrity(INTEGRITY_ROWS_0608)
    p = cash_pivot(lines, PAYMENT_MAP)
    assert p["by_bank"] == {"CASH": 7.91, "BAC": 309.96}
    assert p["by_brand"] == {"Cash": 7.91, "MasterCard": 309.96}
    assert p["by_bucket"] == {"Cash": 7.91, "BAC Cards POS": 309.96}
    assert p["by_channel"] == {"Cash": 7.91, "POS": 309.96}
    # cash-relevant amplio: ambos bancos (CASH y BAC) califican
    assert p["cash_relevant_total"] == pytest.approx(317.87, abs=0.01)
    # bank-only estricto: solo BAC+Tarjeta (CASH no es "banco real")
    assert p["bank_only_total"] == pytest.approx(309.96, abs=0.01)


# dim_payment_map real (ver query de sesión 2026-07-03): un tcode por
# tipo×moneda, más un Non-Cash (AR, moneda 'INTERNAL' -- sin moneda nativa real).
CURRENCY_BASIS_MAP = {
    "3700": {"tipo_pago": "Efectivo", "banco_codigo": "CASH", "cash_flow": "Real Cash", "moneda": "CRC"},
    "3701": {"tipo_pago": "Efectivo", "banco_codigo": "CASH", "cash_flow": "Real Cash", "moneda": "USD"},
    "3704": {"tipo_pago": "Tarjeta", "banco_codigo": "BAC", "cash_flow": "Real Cash", "moneda": "CRC"},
    "3721": {"tipo_pago": "Tarjeta", "banco_codigo": "BAC", "cash_flow": "Real Cash", "moneda": "USD"},
    "3800": {"tipo_pago": "Transferencia", "banco_codigo": "BCR", "cash_flow": "Real Cash", "moneda": "CRC"},
    "3801": {"tipo_pago": "Transferencia", "banco_codigo": "BCR", "cash_flow": "Real Cash", "moneda": "USD"},
    "3900": {"tipo_pago": "Transferencia", "banco_codigo": "SINPE", "cash_flow": "Real Cash", "moneda": "CRC"},
    "3702": {"tipo_pago": "Crédito", "banco_codigo": "AR", "cash_flow": "Non-Cash", "moneda": "INTERNAL"},
}


def test_currency_basis_categoriza_por_tipo_y_moneda_nativa():
    """Cada tcode aporta su monto en SU moneda nativa (nunca convertido) --
    Cards CRC y Cards USD son tcodes distintos, no la misma línea dos veces."""
    lines = payment_lines_from_integrity([
        {"tcode": "3700", "deb_usd": 10.0, "cred_usd": 0, "deb_col": 5000.0, "cred_col": 0},   # Cash CRC
        {"tcode": "3701", "deb_usd": 20.0, "cred_usd": 0, "deb_col": 9300.0, "cred_col": 0},    # Cash USD
        {"tcode": "3704", "deb_usd": 30.0, "cred_usd": 0, "deb_col": 14000.0, "cred_col": 0},   # Cards CRC
        {"tcode": "3721", "deb_usd": 40.0, "cred_usd": 0, "deb_col": 18600.0, "cred_col": 0},   # Cards USD
        {"tcode": "3800", "deb_usd": 50.0, "cred_usd": 0, "deb_col": 23000.0, "cred_col": 0},   # Transfers CRC
        {"tcode": "3801", "deb_usd": 60.0, "cred_usd": 0, "deb_col": 27000.0, "cred_col": 0},   # Transfers USD
        {"tcode": "3900", "deb_usd": 5.0, "cred_usd": 0, "deb_col": 2500.0, "cred_col": 0},     # SINPE CRC
        {"tcode": "3702", "deb_usd": 100.0, "cred_usd": 0, "deb_col": 46500.0, "cred_col": 0},  # Non-Cash (AR)
    ])
    p = currency_basis_pivot(lines, CURRENCY_BASIS_MAP)
    assert p["cash_crc"] == pytest.approx(5000.0)
    assert p["cash_usd"] == pytest.approx(20.0)
    assert p["cards_crc"] == pytest.approx(14000.0)
    assert p["cards_usd"] == pytest.approx(40.0)
    assert p["transfers_crc"] == pytest.approx(23000.0)
    assert p["transfers_usd"] == pytest.approx(60.0)
    assert p["sinpe_crc"] == pytest.approx(2500.0)
    assert p["sinpe_usd"] == pytest.approx(0.0)
    # Non-Cash siempre en USD, nunca en CRC (moneda='INTERNAL' -- sin moneda nativa real)
    assert p["non_cash_usd"] == pytest.approx(100.0)
    assert p["unmapped_currency"] == []


def test_currency_basis_total_real_cash_usd_excluye_columnas_crc():
    """Total Real Cash USD = suma de las columnas *_usd únicamente -- las
    columnas *_crc se muestran en su moneda nativa pero NO se convierten ni
    se suman al total (verificado contra el Excel real del owner, Jan-26:
    Cards USD 92,475.80 + Transfers USD 108,893.60 + Cash USD 3,555.74 +
    SINPE USD 0 = Total Real Cash USD 204,925.14 -- las columnas CRC de esa
    fila, ej. Cards CRC 1,903,464.53, quedan fuera del total)."""
    lines = payment_lines_from_integrity([
        {"tcode": "3704", "deb_usd": 0, "cred_usd": 0, "deb_col": 1903464.53, "cred_col": 0},
        {"tcode": "3721", "deb_usd": 92475.80, "cred_usd": 0, "deb_col": 0, "cred_col": 0},
        {"tcode": "3801", "deb_usd": 108893.60, "cred_usd": 0, "deb_col": 0, "cred_col": 0},
        {"tcode": "3701", "deb_usd": 3555.74, "cred_usd": 0, "deb_col": 0, "cred_col": 0},
        {"tcode": "3702", "deb_usd": 247290.38, "cred_usd": 0, "deb_col": 0, "cred_col": 0},
    ])
    p = currency_basis_pivot(lines, CURRENCY_BASIS_MAP)
    assert p["total_real_cash_usd"] == pytest.approx(204925.14, abs=0.01)
    assert p["total_non_cash_usd"] == pytest.approx(247290.38, abs=0.01)
    assert p["total_usd"] == pytest.approx(452215.52, abs=0.01)


def test_unmapped_tcode_no_se_descarta():
    """Un tcode de pago fuera del mapa no debe sumar a ningún bucket (se
    reporta aparte como UNMAPPED — ver cash_service, no se pierde en silencio)."""
    lines = payment_lines_from_integrity([
        {"tcode": "9999", "deb_usd": 50.0, "cred_usd": 0.0, "deb_col": 0, "cred_col": 0},
    ])
    p = cash_pivot(lines, PAYMENT_MAP)  # 9999 no está en PAYMENT_MAP
    assert p["total"] == 0.0
    assert p["by_bank"] == {}
