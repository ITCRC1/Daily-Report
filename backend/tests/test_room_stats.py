"""Motor de Room Stats (etapa 5): ADR/Occ/Yield por categoría, día real 2026-06-08.

overall.adr=386.46 reconcilia con el ADR ya validado en Revenue/Cash/OTB para
ese mismo día (Rooms=5023.96 / RN=13).
"""
import pytest

from app.engine.room_stats import CATEGORY_ORDER, room_stats_rollup

RECORDS_0608 = [
    {"short_description": "Agujas Villa", "room_revenue": 972.29,
     "stay_rooms": 4, "stay_persons": 7, "physical_rooms": 4},
    {"short_description": "Sirena Suites", "room_revenue": 1964.39,
     "stay_rooms": 5, "stay_persons": 8, "physical_rooms": 8},
    {"short_description": "Treehouse", "room_revenue": 2087.28,
     "stay_rooms": 4, "stay_persons": 5, "physical_rooms": 5},
    {"short_description": "5 Elements", "room_revenue": 0,
     "stay_rooms": 0, "stay_persons": 0, "physical_rooms": 5},
]


def test_todas_las_categorias_presentes_aunque_sin_actividad():
    """Corcovado Deluxe y Carate Deluxe no reportaron ese día (0 físicas) —
    deben aparecer igual, en cero, no desaparecer de la vista."""
    r = room_stats_rollup(RECORDS_0608)
    cats = {c["category"] for c in r["categories"]}
    assert cats == set(CATEGORY_ORDER)
    corcovado = next(c for c in r["categories"] if c["category"] == "Corcovado Deluxe")
    assert corcovado["physical_rooms"] == 0
    assert corcovado["revenue"] == 0.0


def test_overall_reconcilia_con_adr_ya_validado():
    """overall.adr debe coincidir con el ADR de Revenue/Cash/OTB para 06-08 (386.46)."""
    r = room_stats_rollup(RECORDS_0608)
    assert r["overall"]["revenue"] == pytest.approx(5023.96, abs=0.01)
    assert r["overall"]["stay_rooms"] == 13
    assert r["overall"]["physical_rooms"] == 22  # no 30 — 2 categorías sin inventario ese día
    assert r["overall"]["adr"] == pytest.approx(386.46, abs=0.01)
    assert r["overall"]["occupancy_pct"] == pytest.approx(13 / 22, abs=0.001)


def test_yield_index_relativo_al_adr_overall():
    r = room_stats_rollup(RECORDS_0608)
    treehouse = next(c for c in r["categories"] if c["category"] == "Treehouse")
    # ADR Treehouse (521.82) > ADR overall (386.46) → yield > 1
    assert treehouse["adr"] == pytest.approx(521.82, abs=0.01)
    assert treehouse["yield_index"] > 1.0
    agujas = next(c for c in r["categories"] if c["category"] == "Agujas Villa")
    # ADR Agujas (243.07) < ADR overall → yield < 1
    assert agujas["yield_index"] < 1.0


def test_categoria_desconocida_va_a_otros():
    r = room_stats_rollup([
        {"short_description": "Villa Fantasma", "room_revenue": 100.0,
         "stay_rooms": 1, "stay_persons": 1, "physical_rooms": 1},
    ])
    assert r["otros"] is not None
    assert r["otros"]["revenue"] == 100.0
    # no debe aparecer como una 7ma categoría "canónica"
    assert len(r["categories"]) == len(CATEGORY_ORDER)
