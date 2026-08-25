"use client";

import { useState } from "react";
import { downloadExcel, type ExcelSheet } from "@/lib/excel";

/**
 * Botón "bajar a Excel" — el mismo en todos los tabs.
 *
 * Dos formas de usarlo:
 *  - `sheets`: el tab arma las hojas él mismo (control total).
 *  - `target`: un id de contenedor; toma todas las <table> que haya adentro.
 *
 * Se oculta al imprimir (`print:hidden`) y se deshabilita mientras genera.
 */
export default function ExcelButton({
  filename,
  title,
  subtitle,
  sheets,
  target,
  sheetNames,
  label = "Bajar a Excel",
  className = "",
}: {
  filename: string;
  title: string;
  subtitle?: string;
  sheets?: ExcelSheet[] | (() => ExcelSheet[]);
  target?: string;
  sheetNames?: string[];
  label?: string;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    setBusy(true);
    setErr("");
    try {
      let hojas: ExcelSheet[] = [];
      if (sheets) {
        hojas = typeof sheets === "function" ? sheets() : sheets;
      } else if (target) {
        const root = document.getElementById(target);
        if (!root) {
          setErr("No encontré la tabla en la página.");
          return;
        }
        const { containerToSheets } = await import("@/lib/excel");
        hojas = containerToSheets(root, (i) => sheetNames?.[i]);
      }
      hojas = hojas.filter((h) => h.rows.length > 0);
      if (hojas.length === 0) {
        setErr("No hay datos para exportar todavía.");
        return;
      }
      const error = await downloadExcel({ filename, title, subtitle, sheets: hojas });
      if (error) setErr(error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="print:hidden inline-flex items-center gap-2">
      <button
        onClick={run}
        disabled={busy}
        title="Descargar esta vista en Excel"
        className={`rounded border border-ink/12 bg-panel px-3 py-1.5 text-xs font-medium text-ink/80 hover:bg-ink/5 hover:text-ink disabled:opacity-50 ${className}`}
      >
        {busy ? "Generando…" : `⬇ ${label}`}
      </button>
      {err && <span className="text-[11px] text-rose-600">{err}</span>}
    </span>
  );
}
