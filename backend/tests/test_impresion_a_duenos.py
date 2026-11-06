"""El reporte que se le manda a los duenos tiene que salir CON color.

Owner, 2026-11-06, con el PDF que le llega a los duenos en la mano:
*«todavia se ve asi»* -- una planilla blanca, despues de todo el trabajo de
color de la semana.

No se habia roto nada: **Chrome imprime sin graficos de fondo por defecto** y
se llevaba puesto todo lo que distingue por lavado -- la banda de grupos, la
columna de rotulos, la cebra, las tarjetas de KPI. Los filetes sobrevivian,
porque un borde se imprime siempre, y por eso el PDF seguia siendo legible: no
habia error, no habia aviso, solo una hoja blanca donde habia un diseno.

Esa es la razon de ser de estas dos pruebas. Las dos cuidan algo que **no se
nota desde el codigo ni desde la pantalla**: hay que imprimir para verlo, y
quien imprime es el owner, una vez por semana, para mandarlo afuera.
"""
import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parents[2]
       / "frontend" / "app" / "globals.css")


def _bloque_print() -> str:
    """El contenido del `@media print { ... }`, con llaves balanceadas."""
    s = CSS.read_text(encoding="utf-8")
    i = s.index("@media print")
    j = s.index("{", i)
    nivel, k = 1, j + 1
    while nivel:
        if s[k] == "{":
            nivel += 1
        elif s[k] == "}":
            nivel -= 1
        k += 1
    return s[j + 1: k - 1]


def test_el_fondo_se_imprime_aunque_el_tilde_este_apagado():
    """Sin `print-color-adjust: exact` el reporte sale en blanco y negro.

    ⚠️ Si esta prueba falla, el sintoma NO es un error: es que los duenos
    reciben la misma hoja blanca de siempre y nadie se entera hasta que
    alguien lo dice. Medido sobre el PDF real del owner: sin la regla, de los
    rellenos de la hoja ninguno era de fondo; con ella aparecen los cinco
    lavados del diseno.
    """
    bloque = _bloque_print()
    assert re.search(r"(?<!-)\bprint-color-adjust\s*:\s*exact", bloque), (
        "falta `print-color-adjust: exact` en @media print: Chrome va a "
        "descartar TODOS los fondos del reporte")
    assert re.search(r"-webkit-print-color-adjust\s*:\s*exact", bloque), (
        "falta el prefijo -webkit-: Chrome lo sigue necesitando")


def test_el_papel_lo_elige_el_owner():
    """Oficio horizontal (owner, 2026-11-05: *«ponlo horizontal en oficio»*).

    La tabla principal son 14 columnas: en carta medía 1104px contra 1010 de
    hoja y salia cortada sin avisar. El papel no es una preferencia estetica
    -- es lo que hace que el reporte entre entero.
    """
    bloque = _bloque_print()
    assert re.search(r"@page\s*\{[^}]*size\s*:\s*legal\s+landscape", bloque), (
        "el reporte dejo de ser oficio horizontal: la tabla de 14 columnas "
        "no entra en carta y se recorta en silencio")
