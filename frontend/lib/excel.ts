/**
 * Bajar a Excel — el método general que usan todos los tabs.
 *
 * `tableToSheet` lee una <table> del DOM y la convierte en la hoja que espera
 * `POST /export/table/excel`. Eso hace que agregar el botón a un tab nuevo sea
 * una línea, en vez de escribir un exportador por pantalla (son 40+ tablas
 * entre tabs y sub-tabs, y cada exportador propio se iría desfasando del
 * formato de los demás).
 *
 * Se exporta lo que está en pantalla a propósito: el Excel tiene que decir lo
 * mismo que el usuario vio. Los números se parsean de vuelta a número (no van
 * como texto), así en Excel se suman y filtran normal.
 */
import { API_URL } from "@/lib/api";

export type ExcelColumnType = "text" | "money" | "pct" | "int" | "number" | "date";

export type ExcelColumn = { label: string; type: ExcelColumnType; width?: number };
export type ExcelGroup = { label: string; span: number };
export type ExcelSheet = {
  name: string;
  title?: string;
  subtitle?: string;
  caption?: string;
  header_groups?: ExcelGroup[];
  columns: ExcelColumn[];
  rows: (string | number | null)[][];
  total_rows?: number[];
  notes?: string[];
};

const MISSING = new Set(["", "—", "-", "–", "n/a", "N/A"]);

/** "$1,234.56" -> 1234.56 · "(1,234.56)" -> -1234.56 · "12.3%" -> 0.123 */
function parseCell(raw: string): { value: string | number | null; type: ExcelColumnType } {
  const texto = raw.replace(/\s+/g, " ").trim();
  if (MISSING.has(texto)) return { value: null, type: "text" };

  const esPct = texto.endsWith("%");
  const negativoPorParentesis = /^\(.*\)$/.test(texto);
  let limpio = texto
    .replace(/^\((.*)\)$/, "$1")
    .replace(/[$\s%]/g, "")
    .replace(/,/g, "");

  if (limpio === "" || !/^-?\d*\.?\d+$/.test(limpio)) {
    // ISO date: se deja como texto para no romper la zona horaria al convertir.
    return { value: texto, type: "text" };
  }
  let n = parseFloat(limpio);
  if (Number.isNaN(n)) return { value: texto, type: "text" };
  if (negativoPorParentesis) n = -n;
  if (esPct) return { value: n / 100, type: "pct" };
  if (texto.includes("$")) return { value: n, type: "money" };
  return { value: n, type: Number.isInteger(n) && !texto.includes(".") ? "int" : "number" };
}

/** Gana el tipo numérico más frecuente de la columna; si no hay ninguno, texto. */
function columnType(tipos: ExcelColumnType[]): ExcelColumnType {
  const conteo = new Map<ExcelColumnType, number>();
  for (const t of tipos) if (t !== "text") conteo.set(t, (conteo.get(t) ?? 0) + 1);
  if (conteo.size === 0) return "text";
  return [...conteo.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

function cellText(el: Element): string {
  return (el as HTMLElement).innerText ?? el.textContent ?? "";
}

/**
 * Resuelve el <thead> a una grilla, respetando colSpan Y rowSpan.
 *
 * El rowSpan importa: en el cuadro del Tab 3 la primera columna es
 * `<th rowSpan={2}>Revenue Center</th>`, así que vive en la PRIMERA fila del
 * encabezado y no en la última. Leer sólo la última fila devolvía 14 rótulos
 * para 15 columnas de datos y los corría todos un lugar a la izquierda.
 */
function headerGrid(table: HTMLTableElement): { labels: string[]; groups: ExcelGroup[] } {
  const filas = Array.from(table.querySelectorAll("thead tr"));
  if (filas.length === 0) return { labels: [], groups: [] };

  const grid: (string | undefined)[][] = [];
  filas.forEach((tr, r) => {
    grid[r] = grid[r] ?? [];
    let c = 0;
    for (const th of Array.from(tr.children)) {
      while (grid[r][c] !== undefined) c++; // saltar lo que ocupa un rowSpan de arriba
      const celda = th as HTMLTableCellElement;
      const cs = Math.max(1, Number(celda.colSpan || 1));
      const rs = Math.max(1, Number(celda.rowSpan || 1));
      const texto = cellText(th).trim();
      for (let dr = 0; dr < rs; dr++) {
        const rr = r + dr;
        grid[rr] = grid[rr] ?? [];
        for (let dc = 0; dc < cs; dc++) grid[rr][c + dc] = texto;
      }
      c += cs;
    }
  });

  const nCols = Math.max(...grid.map((g) => g.length));
  const labels = Array.from({ length: nCols }, (_, i) => {
    for (let r = grid.length - 1; r >= 0; r--) {
      const v = grid[r]?.[i];
      if (v) return v;
    }
    return "";
  });

  // Grupos: la primera fila, comprimiendo columnas consecutivas con el mismo
  // rótulo. Una celda con rowSpan (mismo texto que su columna) va en blanco,
  // para no repetir el rótulo arriba de sí mismo.
  const groups: ExcelGroup[] = [];
  if (grid.length > 1) {
    for (let i = 0; i < nCols; i++) {
      const bruto = grid[0]?.[i] ?? "";
      const label = bruto && bruto === labels[i] ? "" : bruto;
      const previo = groups[groups.length - 1];
      if (previo && previo.label === label && bruto === (grid[0]?.[i - 1] ?? "")) previo.span += 1;
      else groups.push({ label, span: 1 });
    }
  }
  return { labels, groups };
}

/**
 * Serializa una <table> renderizada: los encabezados salen de la grilla del
 * <thead> (colSpan + rowSpan) y los grupos de su primera fila (TODAY / MONTH TO
 * DAY / FULL MONTH RESULT). Detecta filas de total por el texto.
 */
export function tableToSheet(table: HTMLTableElement, sheet: Partial<ExcelSheet> & { name: string }): ExcelSheet {
  const { labels: columnas, groups: grupos } = headerGrid(table);

  const filasCuerpo = Array.from(table.querySelectorAll("tbody tr"));
  const anchoDatos = Math.max(0, ...filasCuerpo.map((tr) => tr.children.length));
  const nCols = Math.max(columnas.length, anchoDatos);
  while (columnas.length < nCols) columnas.push("");
  const rows: (string | number | null)[][] = [];
  const tiposPorColumna: ExcelColumnType[][] = columnas.map(() => []);
  const total_rows: number[] = [];

  filasCuerpo.forEach((tr, i) => {
    const celdas = Array.from(tr.children);
    const fila: (string | number | null)[] = [];
    celdas.forEach((td, c) => {
      const { value, type } = parseCell(cellText(td));
      fila.push(value);
      if (tiposPorColumna[c]) tiposPorColumna[c].push(type);
    });
    rows.push(fila);
    const primera = cellText(celdas[0] ?? tr).trim().toUpperCase();
    if (/^(GRAND\s+)?TOTAL/.test(primera) || primera.startsWith("TOTAL ")) total_rows.push(i);
  });

  return {
    columns: columnas.map((label, i) => ({ label, type: columnType(tiposPorColumna[i] ?? []) })),
    rows,
    total_rows,
    ...(grupos.some((g) => g.span > 1) ? { header_groups: grupos } : {}),
    ...sheet,
    name: sheet.name,
  };
}

/**
 * Nombre de hoja deducido del título que ya está arriba de la tabla en la
 * página (`.print-table-title`, un heading, o un div de rótulo). Así cada tab
 * hereda hojas con nombre propio sin configurar nada.
 */
const SELECTOR_TITULO = ".print-table-title, h1, h2, h3, h4";

function tituloCercano(table: HTMLTableElement): string | null {
  // 1) hermano anterior del contenedor de la tabla, subiendo hasta 3 niveles
  let nodo: HTMLElement | null = table;
  for (let nivel = 0; nivel < 3 && nodo; nivel++) {
    let prev = nodo.previousElementSibling;
    while (prev) {
      if (prev.matches?.(SELECTOR_TITULO)) return cellText(prev).trim() || null;
      const dentro = prev.querySelector?.(SELECTOR_TITULO);
      if (dentro) return cellText(dentro).trim() || null;
      prev = prev.previousElementSibling;
    }
    nodo = nodo.parentElement;
  }
  return null;
}

/** Recorta a algo usable como nombre de hoja (Excel corta en 31). */
function nombreCorto(texto: string): string {
  const limpio = texto.replace(/\s*[·(§].*$/, "").replace(/[⚠]/g, "").replace(/\s+/g, " ").trim();
  return (limpio || texto).slice(0, 31);
}

/** Serializa TODAS las <table> que haya dentro de un contenedor. */
export function containerToSheets(
  root: HTMLElement,
  nombrar?: (i: number, t: HTMLTableElement) => string | undefined,
): ExcelSheet[] {
  return Array.from(root.querySelectorAll("table")).map((el, i) => {
    const table = el as HTMLTableElement;
    const explicito = nombrar?.(i, table);
    const titulo = tituloCercano(table);
    return tableToSheet(table, {
      name: explicito || (titulo ? nombreCorto(titulo) : `Tabla ${i + 1}`),
      ...(titulo ? { caption: titulo } : {}),
    });
  });
}

/** Pide el .xlsx al backend y dispara la descarga. Devuelve el error, si hubo. */
export async function downloadExcel(payload: {
  filename: string;
  title: string;
  subtitle?: string;
  sheets: ExcelSheet[];
}): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/export/table/excel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detalle = await res.text().catch(() => "");
      return `API ${res.status}${detalle ? `: ${detalle.slice(0, 160)}` : ""}`;
    }
    const disposition = res.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = match ? match[1] : `${payload.filename}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return null;
  } catch (e: unknown) {
    return e instanceof Error ? e.message : "Error desconocido";
  }
}
