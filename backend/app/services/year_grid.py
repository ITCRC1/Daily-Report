"""La reja anual depto x mes: una sola forma para Budget (6.1) y Forecast (6.1.1).

Owner, 2026-11-04, mirando el Tab 6.1.1: *«mejora el upload que los meses sean
columnas y no a como esta en este momento»*.

## Que cambio

La plantilla propia era **larga**: un renglon por (departamento, mes) -- 13
departamentos x 12 meses = 156 filas para escribir 156 numeros, con el codigo y
el nombre repetidos doce veces cada uno. Ahora es **ancha**: un renglon por
departamento y doce columnas de mes, que es como se ve en pantalla, como viene
el archivo Working y como esta armado el Excel con el que el owner trabaja.

Pegar un ano entero desde su hoja pasa de ser un reacomodo manual a un
copy-paste de un bloque.

## Que NO cambio

- **El layout largo se sigue leyendo.** Una plantilla bajada antes de hoy tiene
  que poder subirse; si no, el archivo que alguien dejo a medio llenar el
  viernes no entra el lunes.
- **El layout Working** (linea de ingreso x mes) lo detecta cada servicio antes
  de llegar aca, y no se toca.
- **Budget y Forecast comparten plantilla**, que es un invariante con prueba
  propia (`test_plantilla_identica_a_la_del_budget`). Por eso la reja vive aca
  y no duplicada en los dos servicios.

## Food / Beverage / Misc

El layout largo tenia tres columnas por fila para el desglose de F&B. La reja
ancha no puede expresarlas -- serian 36 columnas mas -- y **nada en el sistema
las lee**: solo se devuelven en el JSON del resumen. El desglose real vive como
departamentos propios (`FB-FOOD`, `FB-BEV`, `FB-MISC`), que es lo que carga el
archivo Working.

⚠️ Por eso la subida ancha **las preserva** en vez de ponerlas en cero: la
carga es un reemplazo total del ano, asi que el servicio las fotografia antes
de borrar y las repone. Una plantilla que no puede expresar un dato no tiene
derecho a destruirlo.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

#: Las doce columnas de mes, en orden. El indice + 1 es el numero de mes.
MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

#: Encabezado de la reja ancha. `HEADERS` de los dos servicios apunta aca.
WIDE_HEADERS = ["Dept Code", "Dept Name", *MESES]

#: El layout viejo, que se sigue aceptando al subir.
LONG_HEADERS = ["Dept Code", "Dept Name", "Mes", "Amount USD", "Available Rooms",
                "Rooms Occupied", "Guests", "Occupancy %", "ADR",
                "Food", "Beverage", "Misc"]

#: Los estadisticos son por MES, no por departamento: van en un bloque aparte,
#: debajo de la reja, con las mismas columnas de mes. Al escribir en la base se
#: guardan en la fila de Rooms (`DEPT_STATS`), igual que hace el layout Working.
STATS = [
    ("Available Rooms", "available_rooms"),
    ("Occupied Rooms", "rooms_occupied"),
    ("Guests", "guests"),
    ("% Occupancy", "occupancy_pct"),
    ("ADR", "adr"),
]
STATS_POR_ETIQUETA = {e.lower(): c for e, c in STATS}

#: El departamento que lleva los estadisticos del mes.
DEPT_STATS = "0110"

_MARCA_STATS = "Statistics"
_AZUL = "2D3A5C"


def _num(v) -> Decimal | None:
    """Un numero de una celda, o None si la celda no trae nada util.

    Acepta lo que Excel deja caer en una celda: numeros, texto con separadores
    de miles, simbolo de moneda, porcentaje y el guion que la pantalla usa para
    "sin dato".
    """
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = str(v).strip()
    if not s or s in {"-", "—", "–", "n/a", "N/A"}:
        return None
    s = s.replace("$", "").replace("%", "").replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def pct(v) -> Decimal | None:
    """La ocupacion, siempre como FRACCION.

    ⚠️ Se guarda 0.417, no 41.7 -- la pantalla multiplica por 100 para
    mostrarla. Pero en la plantilla la celda tiene formato de porcentaje, y
    quien la llena a mano puede escribir `41.7` tanto como `41.7%`. Un valor
    por encima de 1.5 no puede ser una fraccion de ocupacion, asi que se
    interpreta como puntos porcentuales. El limite es 1.5 y no 1 a proposito:
    deja pasar un 100% justo y un sobre-vendido leve sin convertirlo en 0.01.
    """
    n = _num(v)
    if n is None:
        return None
    return n / Decimal("100") if n > Decimal("1.5") else n


def _fila_de_encabezado(ws, primera: str) -> int | None:
    """La fila donde empieza la reja, buscada por su PRIMERA celda.

    Buscada y no asumida en la fila 1: un archivo que paso por Excel puede
    traer un titulo arriba, y fallar por eso obliga a rehacer el archivo por
    una fila en blanco.
    """
    for fila in ws.iter_rows(min_row=1, max_row=40, max_col=1, values_only=False):
        c = fila[0].value
        if c is not None and str(c).strip().lower() == primera.lower():
            return fila[0].row
    return None


def es_ancho(ws) -> bool:
    """¿Es la reja ancha? Se decide por el encabezado, no por el nombre."""
    r = _fila_de_encabezado(ws, "Dept Code")
    if r is None:
        return False
    cab = [str(c.value).strip().lower() if c.value else "" for c in ws[r]]
    # La marca es que la tercera columna sea un mes y no "Mes"/"Amount USD".
    return len(cab) >= 3 and cab[2] in {m.lower() for m in MESES}


def parse(ws) -> tuple[dict, dict, list[str]]:
    """Lee la reja (ancha o larga) y devuelve lo mismo en los dos casos.

    Returns:
        amounts: `{(dept_code, month): Decimal}`
        stats:   `{month: {clave: Decimal}}`
        orden:   los `dept_code` en el orden en que venian, para no barajar la
                 pantalla al guardar.
    """
    return _parse_ancho(ws) if es_ancho(ws) else _parse_largo(ws)


def _parse_ancho(ws) -> tuple[dict, dict, list[str]]:
    r0 = _fila_de_encabezado(ws, "Dept Code")
    cab = [str(c.value).strip() if c.value is not None else "" for c in ws[r0]]
    # Las columnas de mes se ubican por su rotulo: si alguien agrega una columna
    # de notas al final, o reordena, sigue leyendo bien.
    col_mes = {}
    for i, texto in enumerate(cab):
        for m, nombre in enumerate(MESES, start=1):
            if texto.lower() == nombre.lower():
                col_mes[m] = i
    amounts: dict[tuple[str, int], Decimal] = {}
    stats: dict[int, dict] = {}
    orden: list[str] = []

    en_stats = False
    for fila in ws.iter_rows(min_row=r0 + 1, values_only=True):
        if not fila:
            continue
        etiqueta = str(fila[0]).strip() if fila[0] is not None else ""
        if not etiqueta:
            continue
        if etiqueta.lower() == _MARCA_STATS.lower():
            en_stats = True
            continue
        if en_stats:
            clave = STATS_POR_ETIQUETA.get(etiqueta.lower())
            if clave is None:
                continue
            for m, i in col_mes.items():
                v = pct(fila[i]) if clave == "occupancy_pct" else _num(fila[i])
                if v is not None:
                    stats.setdefault(m, {})[clave] = v
            continue
        # Fila de departamento. El TOTAL de la plantilla no es un depto.
        if etiqueta.upper().startswith("TOTAL"):
            continue
        code = etiqueta
        if code not in orden:
            orden.append(code)
        for m, i in col_mes.items():
            amounts[(code, m)] = _num(fila[i]) or Decimal("0")
    return amounts, stats, orden


def _parse_largo(ws) -> tuple[dict, dict, list[str]]:
    r0 = _fila_de_encabezado(ws, "Dept Code") or 1
    amounts: dict[tuple[str, int], Decimal] = {}
    stats: dict[int, dict] = {}
    orden: list[str] = []
    for r in ws.iter_rows(min_row=r0 + 1, values_only=True):
        if not r or r[0] is None:
            continue
        v = (list(r) + [None] * 12)[:12]
        code = str(v[0]).strip()
        if _num(v[2]) is None:
            continue
        month = int(_num(v[2]))
        if not 1 <= month <= 12:
            continue
        if code not in orden:
            orden.append(code)
        amounts[(code, month)] = _num(v[3]) or Decimal("0")
        propios = {
            "available_rooms": _num(v[4]), "rooms_occupied": _num(v[5]),
            "guests": _num(v[6]), "occupancy_pct": pct(v[7]), "adr": _num(v[8]),
        }
        for clave, valor in propios.items():
            if valor is not None:
                stats.setdefault(month, {})[clave] = valor
    return amounts, stats, orden


def build(titulo: str, filas: list[tuple[str, str, list[float]]],
          stats_por_mes: dict[int, dict]) -> bytes:
    """La plantilla ancha, prellenada.

    Args:
        filas: `(dept_code, dept_name, [12 montos])`, en el orden a mostrar.
        stats_por_mes: `{month: {clave: valor}}`.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append(WIDE_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=_AZUL)
        cell.alignment = Alignment(horizontal="center")

    for code, nombre, montos in filas:
        ws.append([code, nombre, *[float(x or 0) for x in montos]])
    # El total se escribe como FORMULA, no como numero: el archivo se llena a
    # mano y un total congelado deja de cuadrar en cuanto se toca una celda.
    r_total = ws.max_row + 1
    ws.cell(row=r_total, column=1, value="TOTAL").font = Font(bold=True)
    for m in range(1, 13):
        L = get_column_letter(2 + m)
        c = ws.cell(row=r_total, column=2 + m,
                    value=f"=SUM({L}2:{L}{r_total - 1})")
        c.font = Font(bold=True)

    ws.append([])
    r_marca = ws.max_row + 1
    ws.cell(row=r_marca, column=1, value=_MARCA_STATS).font = Font(bold=True, color="FFFFFF")
    for col in range(1, len(WIDE_HEADERS) + 1):
        ws.cell(row=r_marca, column=col).fill = PatternFill("solid", fgColor=_AZUL)
    for etiqueta, clave in STATS:
        fila = [etiqueta, ""]
        for m in range(1, 13):
            v = (stats_por_mes.get(m) or {}).get(clave)
            fila.append(float(v) if v is not None else None)
        ws.append(fila)
        if clave == "occupancy_pct":
            for col in range(3, 15):
                ws.cell(row=ws.max_row, column=col).number_format = "0.0%"

    ws.freeze_panes = "C2"
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 26
    for col in range(3, 15):
        ws.column_dimensions[get_column_letter(col)].width = 13

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
