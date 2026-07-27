"""Motor de Gate (etapa 8, §2.7): suave vs duro, con/sin override."""
from app.engine.gate import evaluate_gate


def test_gate_suave_siempre_permite():
    r = evaluate_gate(kpi_discrepancia=2, kpi_faltante=1, gate_hard=False)
    assert r.allowed is True
    assert r.open_issues == 3


def test_gate_suave_sin_excepciones():
    r = evaluate_gate(kpi_discrepancia=0, kpi_faltante=0, gate_hard=False)
    assert r.allowed is True
    assert r.open_issues == 0


def test_gate_duro_sin_excepciones_permite():
    r = evaluate_gate(kpi_discrepancia=0, kpi_faltante=0, gate_hard=True)
    assert r.allowed is True


def test_gate_duro_bloquea_sin_override():
    r = evaluate_gate(kpi_discrepancia=2, kpi_faltante=0, gate_hard=True, override_flag=False)
    assert r.allowed is False
    assert "Blocked" in r.reason
    assert r.open_issues == 2


def test_gate_duro_permite_con_override():
    r = evaluate_gate(kpi_discrepancia=2, kpi_faltante=1, gate_hard=True, override_flag=True)
    assert r.allowed is True
    assert "override" in r.reason.lower()
    assert r.open_issues == 3
