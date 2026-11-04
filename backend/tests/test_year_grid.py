"""La reja anual: meses como COLUMNAS, y el layout viejo se sigue leyendo.

Owner, 2026-11-04: *«mejora el upload que los meses sean columnas y no a como
esta en este momento»*.

La plantilla propia era larga -- 13 departamentos x 12 meses = 156 renglones
para escribir 156 numeros, con el codigo repetido doce veces. Ahora es ancha,
que es como se ve en pantalla y como viene el archivo con el que se trabaja.

Lo que estas pruebas cuidan es el borde: que cambiar la forma de la plantilla
no deje afuera un archivo ya bajado, y que el viaje redondo siga siendo nulo.
"""
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.services import budget_service, forecast_service, year_grid


def _hoja(contenido: bytes):
    return load_workbook(BytesIO(contenido), data_only=False).active


FILAS = [
    ("0110", "Rooms", [427258.50, 416162.54, 423979.52, 319273.43, 119456.11,
                       79310.61, 105060.00, 123900.76, 39973.51, 0.0,
                       214401.88, 445348.60]),
    ("0140", "SPA", [6268.26, 10093.38, 10780.47, 6087.60, 1886.14, 1785.00,
                     4359.38, 5812.50, 5625.00, 0.0, 5625.00, 5812.50]),
]
STATS = {
    1: {"available_rooms": Decimal("930"), "rooms_occupied": Decimal("637"),
        "guests": Decimal("1050"), "occupancy_pct": Decimal("0.685"),
        "adr": Decimal("654.65")},
    11: {"available_rooms": Decimal("900"), "rooms_occupied": Decimal("375"),
         "guests": Decimal("620"), "occupancy_pct": Decimal("0.417"),
         "adr": Decimal("359.60")},
}


def test_la_plantilla_sale_con_los_meses_como_columnas():
    ws = _hoja(year_grid.build("Forecast 2026", FILAS, STATS))
    cab = [c.value for c in ws[1]]
    assert cab[:2] == ["Dept Code", "Dept Name"]
    assert cab[2:14] == year_grid.MESES
    assert len(cab) == 14, "un depto no puede ocupar mas de catorce columnas"


def test_los_dos_tabs_comparten_la_plantilla():
    """Invariante del diseno: 6.1 y 6.1.1 son el mismo panel. Si divergen, hay
    que llenar dos formatos distintos para el mismo grano."""
    assert forecast_service.HEADERS == budget_service.HEADERS == year_grid.WIDE_HEADERS


def test_el_viaje_redondo_es_nulo():
    """Construir la plantilla y leerla de vuelta no cambia un numero.

    Es la prueba que mas vale: la plantilla se baja prellenada, y si bajarla y
    subirla sin tocar nada moviera una cifra, el error entraria por el camino
    que nadie revisa -- y el total seguiria cuadrando.
    """
    amounts, stats, orden = year_grid.parse(_hoja(year_grid.build("X", FILAS, STATS)))
    assert orden == ["0110", "0140"], "se barajo el orden de los departamentos"
    for code, _nombre, montos in FILAS:
        for i, esperado in enumerate(montos, start=1):
            assert amounts[(code, i)] == Decimal(str(esperado)), f"{code} mes {i}"
    for mes, propios in STATS.items():
        for clave, valor in propios.items():
            assert stats[mes][clave] == valor, f"mes {mes} · {clave}"


def test_el_total_no_se_lee_como_un_departamento():
    """La plantilla trae una fila TOTAL con formulas. Si entrara como depto, el
    ano quedaria con el doble."""
    _amounts, _stats, orden = year_grid.parse(_hoja(year_grid.build("X", FILAS, STATS)))
    assert not any(c.upper().startswith("TOTAL") for c in orden)


def test_el_layout_VIEJO_se_sigue_leyendo():
    """Una plantilla bajada antes del cambio tiene que poder subirse.

    Sin esto, el archivo que alguien dejo a medio llenar el viernes no entra el
    lunes, y el unico aviso seria un ano cargado en cero.
    """
    wb = Workbook(); ws = wb.active
    ws.append(year_grid.LONG_HEADERS)
    ws.append(["0110", "Rooms", 1, 427258.50, 930, 637, 1050, 0.685, 654.65, 0, 0, 0])
    ws.append(["0110", "Rooms", 11, 214401.88, 900, 375, 620, 0.417, 359.60, 0, 0, 0])
    ws.append(["0140", "SPA", 1, 6268.26, None, None, None, None, None, 0, 0, 0])
    buf = BytesIO(); wb.save(buf)

    amounts, stats, orden = year_grid.parse(load_workbook(buf).active)
    assert orden == ["0110", "0140"]
    assert amounts[("0110", 1)] == Decimal("427258.5")
    assert amounts[("0110", 11)] == Decimal("214401.88")
    assert amounts[("0140", 1)] == Decimal("6268.26")
    assert stats[11]["rooms_occupied"] == Decimal("375")


def test_los_dos_layouts_se_distinguen_por_el_ENCABEZADO():
    ancho = _hoja(year_grid.build("X", FILAS, STATS))
    assert year_grid.es_ancho(ancho)

    wb = Workbook(); ws = wb.active
    ws.append(year_grid.LONG_HEADERS)
    ws.append(["0110", "Rooms", 1, 1.0, None, None, None, None, None, 0, 0, 0])
    buf = BytesIO(); wb.save(buf)
    assert not year_grid.es_ancho(load_workbook(buf).active)


def test_la_ocupacion_entra_como_fraccion_se_escriba_como_se_escriba():
    """0.417 y 41.7 son la misma ocupacion.

    La celda tiene formato de porcentaje, asi que Excel puede devolver
    cualquiera de las dos segun como la haya tipeado quien la lleno. Guardar
    41.7 donde se espera 0.417 multiplica la ocupacion por cien y el ADR deja
    de cuadrar contra el ingreso.
    """
    assert year_grid.pct(0.417) == Decimal("0.417")
    assert year_grid.pct(41.7) == Decimal("0.417")
    assert year_grid.pct("41.7%") == Decimal("0.417")
    # 100% justo sigue siendo una fraccion, no 0.01.
    assert year_grid.pct(1) == Decimal("1")
    assert year_grid.pct(None) is None


def test_lee_lo_que_excel_deja_caer_en_una_celda():
    """Numeros con moneda, miles, parentesis y el guion de 'sin dato'."""
    assert year_grid._num("$1,226.42") == Decimal("1226.42")
    assert year_grid._num("(500)") == Decimal("-500")
    assert year_grid._num("—") is None
    assert year_grid._num("") is None
    assert year_grid._num(0) == Decimal("0")


def test_una_columna_extra_no_corre_los_meses():
    """Los meses se ubican por su rotulo, no por su posicion: alguien va a
    agregar una columna de notas al final."""
    contenido = year_grid.build("X", FILAS, STATS)
    wb = load_workbook(BytesIO(contenido))
    ws = wb.active
    ws.cell(row=1, column=15, value="Notas")
    ws.cell(row=2, column=15, value="revisar con reservas")
    buf = BytesIO(); wb.save(buf)

    amounts, _stats, _orden = year_grid.parse(load_workbook(buf).active)
    assert amounts[("0110", 1)] == Decimal("427258.5")
    assert amounts[("0110", 12)] == Decimal("445348.6")


# --- Un solo camino de escritura -------------------------------------------

def _fuente(nombre: str) -> str:
    import pathlib
    return (pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
            / nombre).read_text(encoding="utf-8")


def test_un_solo_escritor_del_anio():
    """`_write_year` es el unico que inserta en la tabla mensual.

    ⚠️ Habia TRES caminos que escribian el anio -- la plantilla, el archivo
    Working y, al agregarse, el guardado desde la pantalla -- y ya habian
    empezado a divergir: el Working ponia Food/Beverage/Misc en cero mientras
    los otros los preservan. Tres escritores del mismo anio terminan diciendo
    tres cosas distintas, y en los tres el TOTAL cuadra: por eso no se nota.

    Si esta prueba falla con un `session.add` nuevo, no la relajes -- hace falta
    que ese camino pase por `_write_year`.
    """
    for nombre, modelo in (("forecast_service.py", "ForecastMonthly"),
                           ("budget_service.py", "BudgetMonthly")):
        src = _fuente(nombre)
        assert src.count(f"session.add({modelo}(") == 1, (
            f"{nombre}: hay mas de un lugar insertando {modelo}")


def test_los_tres_caminos_pasan_por_write_year():
    """Excel ancho, Excel viejo, Working y pantalla: la misma escritura."""
    src = _fuente("forecast_service.py")
    for fn in ("upload_and_replace", "_upload_working", "save_monthly"):
        i = src.index(f"async def {fn}(")
        j = src.find("\nasync def ", i + 1)
        cuerpo = src[i: j if j > 0 else len(src)]
        assert "_write_year(" in cuerpo, f"{fn} no pasa por _write_year"

    src = _fuente("budget_service.py")
    for fn in ("upload_and_replace", "save_monthly"):
        i = src.index(f"async def {fn}(")
        j = src.find("\nasync def ", i + 1)
        cuerpo = src[i: j if j > 0 else len(src)]
        assert "_write_year(" in cuerpo, f"budget · {fn} no pasa por _write_year"


def test_la_plantilla_nueva_no_destruye_el_desglose_de_fyb():
    """La reja ancha no puede expresar Food/Beverage/Misc, y la carga borra el
    anio entero: sin la foto previa, subirla los pondria en cero."""
    for nombre in ("forecast_service.py", "budget_service.py"):
        src = _fuente(nombre)
        assert "_snapshot_fbm" in src, f"{nombre}: falta preservar food/beverage/misc"
        i = src.index("async def _write_year(")
        j = src.find("\nasync def ", i + 1)
        assert "_snapshot_fbm(" in src[i:j], f"{nombre}: _write_year no repone el desglose"
