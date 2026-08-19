"use client";

import { useEffect, useRef, useState } from "react";
import { useBusinessDate } from "@/lib/useBusinessDate";
import { useSubtabs } from "@/lib/useSubtabs";
import { API_URL } from "@/lib/api";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ALL_SUBTABS = [
  { id: "8.1", label: "8.1 ONTB Report" },
  { id: "8.2", label: "8.2 Dashboard" },
  { id: "8.3", label: "8.3 Daily Heatmap" },
  { id: "8.4", label: "8.4 Pacing" },
  { id: "8.5", label: "8.5 Revenue Trend" },
  { id: "8.5.1", label: "8.5.1 Análisis 2027" },
  { id: "8.6", label: "8.6 Occupancy Trend" },
  { id: "8.7", label: "8.7 Variance Breakdown" },
];
// Tabs que van al PDF (8.1–8.6, cada uno en su hoja). 8.5.1 y 8.7 quedan solo
// en pantalla (el set de impresión que definió el owner es 8.1–8.6).
const PRINT_TABS = ALL_SUBTABS.filter((s) => s.id !== "8.7" && s.id !== "8.5.1");

type Metrics = {
  total_revenue: number; rooms_only: number; rooms_avail: number;
  rooms_occ: number; guests: number; adr_total: number; adr_only: number; occ: number;
};
type MonthData = {
  month: number; budget: Metrics; otb: Metrics; diff: Metrics;
  sales_on_property: number; net_gap: number;
  prev_total_revenue?: number | null; otb_move?: number | null; occ_move?: number | null;
};
type Report = {
  year: number; snapshot_date: string | null; compare_snapshot_date?: string | null;
  months: MonthData[];
  net_gap_total: number; budget_total_revenue: number; otb_total_revenue: number;
  otb_move_total?: number | null;
};

const money = (v: number) =>
  v < 0 ? `(${Math.round(Math.abs(v)).toLocaleString()})` : Math.round(v).toLocaleString();
const dec = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 1 });
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const neg = (v: number) => (v < 0 ? "text-red-600" : "");

const th = "px-2 py-1.5 text-right text-[11px] font-medium text-ink/70";
const thl = "px-3 py-1.5 text-left text-[11px] font-medium text-ink/70";
const tdL = "px-3 py-1 text-left text-ink/85 whitespace-nowrap";

// Colapso por cuartos (Q1-Q4): cada mes o un cuarto agregado
type Col =
  | { kind: "m"; month: MonthData; label: string }
  | { kind: "q"; q: number; months: MonthData[]; label: string };

function buildCols(months: MonthData[], collapsed: number[]): Col[] {
  const cols: Col[] = [];
  for (let q = 1; q <= 4; q++) {
    const qm = months.slice((q - 1) * 3, q * 3);
    if (collapsed.includes(q)) cols.push({ kind: "q", q, months: qm, label: `Q${q}` });
    else qm.forEach((mo, i) => cols.push({ kind: "m", month: mo, label: MONTHS[(q - 1) * 3 + i] }));
  }
  return cols;
}

function useQuarters() {
  const [collapsed, setCollapsed] = useState<number[]>([]);
  const toggle = (q: number) => setCollapsed((c) => (c.includes(q) ? c.filter((x) => x !== q) : [...c, q]));
  return { collapsed, toggle };
}

function QuarterBar({ collapsed, toggle }: { collapsed: number[]; toggle: (q: number) => void }) {
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-ink/60">
      <span>Quarters:</span>
      {[1, 2, 3, 4].map((q) => {
        const c = collapsed.includes(q);
        return (
          <button key={q} onClick={() => toggle(q)}
            className={`rounded px-2 py-0.5 font-mono ${c ? "bg-accent/30 text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}
            title={c ? `Expand Q${q}` : `Collapse Q${q} into its total`}>
            {c ? "＋" : "－"} Q{q}
          </button>
        );
      })}
      <span className="text-ink/45">— collapse (＋) to roll a quarter into one column</span>
    </div>
  );
}

const qsum = (ms: MonthData[], get: (d: MonthData) => number) => ms.reduce((s, x) => s + get(x), 0);
const qAdr = (ms: MonthData[], side: "budget" | "otb", kind: "total" | "only") => {
  const rev = qsum(ms, (d) => (kind === "total" ? d[side].total_revenue : d[side].rooms_only));
  const occ = qsum(ms, (d) => d[side].rooms_occ);
  return occ ? rev / occ : 0;
};
const qOcc = (ms: MonthData[], side: "budget" | "otb") => {
  const o = qsum(ms, (d) => d[side].rooms_occ), a = qsum(ms, (d) => d[side].rooms_avail);
  return a ? o / a : 0;
};

function weekAgo(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

export default function OnTheBooksPage() {
  const anchor = useBusinessDate();
  const year = Number(anchor.slice(0, 4)) || 2026;
  const { subtabs: SUBTABS, tab, setTab } = useSubtabs(ALL_SUBTABS, "8.1");
  const [data, setData] = useState<Report | null>(null);
  const [err, setErr] = useState("");
  // corte FINAL (as_of) y corte INICIAL (compare_to) — gobiernan todos los sub-tabs
  const [dateTo, setDateTo] = useState<string>(anchor);
  const [dateFrom, setDateFrom] = useState<string>(weekAgo(anchor));
  // Recalculate: fuerza re-fetch desde el backend (recomputa en vivo desde la DB)
  const [refreshKey, setRefreshKey] = useState(0);
  const [recalcMsg, setRecalcMsg] = useState("");
  const recalcPending = useRef(false);
  const recalc = () => { recalcPending.current = true; setRecalcMsg("Recalculating…"); setRefreshKey((k) => k + 1); };

  // Default: comparar los DOS cortes más recientes (this week vs last week)
  useEffect(() => {
    let live = true;
    fetch(`${API_URL}/ontb/pacing?year=${year}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((p) => {
        if (!live) return;
        const snaps: string[] = (p.snapshots || []).map((s: { snapshot_date: string }) => s.snapshot_date);
        if (snaps.length >= 2) { setDateTo(snaps[snaps.length - 1]); setDateFrom(snaps[snaps.length - 2]); }
        else if (snaps.length === 1) { setDateTo(snaps[0]); setDateFrom(weekAgo(snaps[0])); }
        else { setDateTo(anchor); setDateFrom(weekAgo(anchor)); }
      })
      .catch(() => { if (live) { setDateTo(anchor); setDateFrom(weekAgo(anchor)); } });
    return () => { live = false; };
  }, [anchor]);

  useEffect(() => {
    if (!dateTo) return;
    let live = true;
    setData(null); setErr("");
    const qs = `year=${year}&as_of=${dateTo}${dateFrom ? `&compare_to=${dateFrom}` : ""}`;
    fetch(`${API_URL}/ontb?${qs}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!live) return;
        if (d.detail) { setErr(d.detail); } else { setData(d); }
        if (recalcPending.current) {
          recalcPending.current = false;
          setRecalcMsg(`✓ Recalculated ${new Date().toLocaleTimeString()}`);
        }
      })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [year, dateTo, dateFrom, refreshKey]);

  const moved = data?.otb_move_total;

  return (
    <section className="w-[calc(100vw-1.5rem)] -translate-x-1/2 relative left-1/2 space-y-4">
      {/* Encabezado solo visible al imprimir (Ctrl+P) -- va en la 1ra hoja del PDF */}
      <div className="print-header-block hidden print:flex print:flex-col print:items-center print:border-b print:border-ink/15">
        <div className="print-subtitle uppercase tracking-wide text-ink/60">Corcovado Wilderness Lodge</div>
        <div className="print-title font-bold">On the Books — Budget vs OTB {year}</div>
        <div className="print-date font-extrabold tracking-tight">OTB cut: {data?.snapshot_date ?? dateTo}</div>
      </div>

      <div className="print:hidden">
        <h1 className="text-xl font-semibold text-ink">Tab 8 · On the Books</h1>
        <p className="text-xs text-ink/60">
          Budget vs On-The-Books pacing ({year}, COWLCR){data?.snapshot_date && (
            <> · OTB cut <b className="text-ink/75">{data.snapshot_date}</b></>
          )}. Replaces the manual Excel + PDF report.
          <br />
          <span className="text-amber-700/80">Nota: ADR/Occupancy del OTB son <b>gross of comps</b> — el forecast de Opera (history_forecast) no trae market_code para netear cortesías/in-house. No comparar 1:1 con el ADR neto de Tabs 6.6 / 7.3.</span>
        </p>
      </div>

      {/* Selector de cortes (fecha inicial + final) que gobierna todos los sub-tabs */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-ink/10 bg-[#f2f1ec] px-3 py-2 text-xs">
        <span className="font-medium text-ink/75">OTB cut:</span>
        <label className="flex items-center gap-1 text-ink/70">from
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
        <label className="flex items-center gap-1 text-ink/70">to
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
        {data && (
          <span className="text-ink/60">
            Final cut <b className="text-ink/85">{data.snapshot_date ?? "—"}</b>
            {data.compare_snapshot_date
              ? <> vs initial <b className="text-ink/85">{data.compare_snapshot_date}</b>
                  {moved != null && <> · OTB moved <b className={moved < 0 ? "text-red-600" : "text-emerald-600"}>{moved >= 0 ? "+" : ""}${money(moved)}</b></>}</>
              : <span className="text-ink/45"> · no earlier cut yet (only one snapshot ingested so far)</span>}
          </span>
        )}
        <span className="ml-auto flex items-center gap-2">
          {tab === "8.1" && (
            <button onClick={() => window.print()}
              className="rounded bg-ink/5 px-2.5 py-1 text-ink/85 hover:bg-ink/8"
              title="Imprime los tabs 8.1–8.6, cada uno en su hoja (Ctrl+P → Guardar como PDF)">
              🖨️ Imprimir PDF
            </button>
          )}
          <button onClick={recalc}
            className="rounded bg-accent/80 px-2.5 py-1 text-white hover:bg-accent"
            title="Re-pull the report from the backend (recomputes live from the database)">
            ↻ Recalculate
          </button>
          {recalcMsg && <span className={recalcMsg.startsWith("✓") ? "text-emerald-600" : "text-ink/60"}>{recalcMsg}</span>}
        </span>
      </div>

      <nav className="flex flex-wrap gap-1 border-b border-ink/10 pb-2">
        {SUBTABS.map((s) => (
          <button key={s.id} onClick={() => setTab(s.id)}
            className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
            {s.label}
          </button>
        ))}
      </nav>

      {err && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700">
          No OTB data yet — ingest a day with history_forecast files first. ({err})
        </div>
      )}

      {/* En PANTALLA se ve solo el sub-tab activo; al IMPRIMIR se muestran los 6
          (8.1–8.6), cada uno en su propia hoja. Todos van montados para que sus
          datos ya estén cargados cuando se dispara el print. */}
      {PRINT_TABS.map((s, i) => (
        <div key={s.id} className={`${tab === s.id ? "" : "hidden"} print:block ${i > 0 ? "print-page-break" : ""}`}>
          <div className="hidden print:block print-table-title mb-1">{s.label}</div>
          {s.id === "8.1" && data && <ONTBReport data={data} />}
          {s.id === "8.2" && data && <Dashboard data={data} />}
          {s.id === "8.3" && <Heatmap year={year} asOf={dateTo} refreshKey={refreshKey} />}
          {s.id === "8.4" && <Pacing refreshKey={refreshKey} year={year} />}
          {s.id === "8.5" && data && <RevenueTrend data={data} />}
          {s.id === "8.6" && data && <OccupancyTrend data={data} />}
        </div>
      ))}
      {/* 8.5.1 Análisis 2027 — solo en pantalla; compara OTB 2027 vs 2026 (fijo,
          independiente del selector de Día). */}
      <div className={`${tab === "8.5.1" ? "" : "hidden"} print:hidden`}>
        <Analisis2027 asOf={dateTo} refreshKey={refreshKey} />
      </div>
      {/* 8.7 solo en pantalla — no entra al PDF (pedido del owner). */}
      <div className={`${tab === "8.7" ? "" : "hidden"} print:hidden`}>
        {data && <VariancePie data={data} />}
      </div>
    </section>
  );
}

/* ---------- 8.1 ONTB Report ---------- */
function ONTBReport({ data }: { data: Report }) {
  const { collapsed, toggle } = useQuarters();
  const cols = buildCols(data.months, collapsed);
  const all = data.months;
  const sum = (get: (d: MonthData) => number) => qsum(all, get);
  const qbg = "bg-[#e8e7e0]";
  const move = data.otb_move_total;        // this week vs last week (OTB)
  const hasWoW = move != null && data.compare_snapshot_date != null;

  const Row = (
    label: string,
    get: (d: MonthData) => number,
    fmt: (v: number) => string,
    opts?: { total?: boolean; indent?: boolean; money?: boolean; qv?: (ms: MonthData[]) => number },
  ) => (
    <tr className="border-t border-ink/8">
      <td className={`${tdL} sticky left-0 z-10 bg-[#f9f9f7] ${opts?.indent ? "pl-6 text-ink/70" : ""}`}>{label}</td>
      {cols.map((c, i) => {
        const v = c.kind === "m" ? get(c.month) : (opts?.qv ? opts.qv(c.months) : qsum(c.months, get));
        return (
          <td key={i} className={`px-2 py-1 text-right ${c.kind === "q" ? `${qbg} font-medium` : ""} ${opts?.money ? neg(v) : ""}`}>{fmt(v)}</td>
        );
      })}
      <td className={`px-2 py-1 text-right font-medium border-l border-ink/10 ${opts?.total ? neg(sum(get)) : "text-ink/45"}`}>
        {opts?.total ? fmt(sum(get)) : "—"}
      </td>
    </tr>
  );

  const groupHead = (label: string, cls: string) => (
    <tr className="bg-[#f2f1ec]">
      <td className={`sticky left-0 z-10 bg-[#f2f1ec] px-3 py-1.5 text-left text-[11px] font-bold uppercase tracking-wide ${cls}`} colSpan={cols.length + 2}>{label}</td>
    </tr>
  );

  return (
    <div className="space-y-1">
      <QuarterBar collapsed={collapsed} toggle={toggle} />
      <div className="overflow-auto rounded-lg border border-ink/10 max-h-[72vh]">
        <table className="w-full text-xs">
          <thead className="bg-[#fcfcfb]">
            <tr>
              <th className={`${thl} sticky left-0 top-0 z-30 bg-[#fcfcfb]`}>Metric</th>
              {cols.map((c, i) => (
                <th key={i} className={`${th} sticky top-0 z-20 ${c.kind === "q" ? `${qbg} text-ink/85` : "bg-[#fcfcfb]"}`}>{c.label}</th>
              ))}
              <th className={`${th} sticky top-0 z-20 bg-[#fcfcfb] border-l border-ink/10`}>Total</th>
            </tr>
          </thead>
          <tbody>
            {groupHead("Budget", "text-sky-700")}
            {Row("Total Revenue", (d) => d.budget.total_revenue, (v) => `$${money(v)}`, { total: true, money: true })}
            {Row("Rooms Only", (d) => d.budget.rooms_only, (v) => `$${money(v)}`, { total: true, money: true })}
            {Row("Rooms Available", (d) => d.budget.rooms_avail, (v) => dec(v), { total: true })}
            {Row("Rooms Occupied", (d) => d.budget.rooms_occ, (v) => dec(v), { total: true })}
            {Row("Guests", (d) => d.budget.guests, (v) => dec(v), { total: true })}
            {Row("ADR Total", (d) => d.budget.adr_total, (v) => `$${money(v)}`, { money: true, qv: (ms) => qAdr(ms, "budget", "total") })}
            {Row("ADR Only", (d) => d.budget.adr_only, (v) => `$${money(v)}`, { money: true, qv: (ms) => qAdr(ms, "budget", "only") })}
            {Row("Occupancy %", (d) => d.budget.occ, (v) => pct(v), { qv: (ms) => qOcc(ms, "budget") })}

            {groupHead("On The Books (OTB)", "text-emerald-700")}
            {Row("Total Revenue", (d) => d.otb.total_revenue, (v) => `$${money(v)}`, { total: true, money: true })}
            {Row("Rooms Only", (d) => d.otb.rooms_only, (v) => `$${money(v)}`, { total: true, money: true })}
            {Row("Rooms Occupied", (d) => d.otb.rooms_occ, (v) => dec(v), { total: true })}
            {Row("Guests", (d) => d.otb.guests, (v) => dec(v), { total: true })}
            {Row("ADR Total", (d) => d.otb.adr_total, (v) => `$${money(v)}`, { money: true, qv: (ms) => qAdr(ms, "otb", "total") })}
            {Row("ADR Only", (d) => d.otb.adr_only, (v) => `$${money(v)}`, { money: true, qv: (ms) => qAdr(ms, "otb", "only") })}
            {Row("Occupancy %", (d) => d.otb.occ, (v) => pct(v), { qv: (ms) => qOcc(ms, "otb") })}
            {Row("Sales on Property", (d) => d.sales_on_property, (v) => `$${money(v)}`, { total: true, indent: true, money: true })}

            {groupHead("Diff (OTB − Budget)", "text-amber-700")}
            {Row("Total Revenue", (d) => d.diff.total_revenue, (v) => `$${money(v)}`, { total: true, money: true })}
            {Row("Rooms Only", (d) => d.diff.rooms_only, (v) => `$${money(v)}`, { total: true, money: true })}
            {Row("Rooms Occupied", (d) => d.diff.rooms_occ, (v) => dec(v), { total: true, money: true })}
            {Row("Guests", (d) => d.diff.guests, (v) => dec(v), { total: true, money: true })}
            {Row("ADR Total", (d) => d.diff.adr_total, (v) => `$${money(v)}`, { money: true, qv: (ms) => qAdr(ms, "otb", "total") - qAdr(ms, "budget", "total") })}
            {Row("ADR Only", (d) => d.diff.adr_only, (v) => `$${money(v)}`, { money: true, qv: (ms) => qAdr(ms, "otb", "only") - qAdr(ms, "budget", "only") })}
            {Row("Occupancy %", (d) => d.diff.occ, (v) => pct(v), { money: true, qv: (ms) => qOcc(ms, "otb") - qOcc(ms, "budget") })}

            <tr className="border-t-2 border-ink/15 bg-emerald-900/20 font-bold">
              <td className="sticky left-0 z-10 bg-[#0f1a15] px-3 py-2 text-left text-emerald-700">NET GAP</td>
              {cols.map((c, i) => {
                const v = c.kind === "m" ? c.month.net_gap : qsum(c.months, (d) => d.net_gap);
                return <td key={i} className={`px-2 py-2 text-right ${c.kind === "q" ? qbg : ""} ${neg(v)}`}>${money(v)}</td>;
              })}
              <td className={`px-2 py-2 text-right border-l border-ink/10 ${neg(data.net_gap_total)}`}>${money(data.net_gap_total)}</td>
            </tr>

            {/* This week vs Last week — movimiento del OTB entre cortes */}
            {groupHead("This Week vs Last Week (OTB movement)", "text-fuchsia-300")}
            {hasWoW ? (
              <tr className="border-t border-ink/8 font-medium">
                <td className={`${tdL} sticky left-0 z-10 bg-[#f9f9f7]`}>
                  OTB Δ <span className="text-ink/60">({data.compare_snapshot_date} → {data.snapshot_date})</span>
                </td>
                {cols.map((c, i) => {
                  const v = c.kind === "m" ? (c.month.otb_move ?? 0) : qsum(c.months, (d) => d.otb_move ?? 0);
                  return (
                    <td key={i} className={`px-2 py-1 text-right ${c.kind === "q" ? qbg : ""} ${v < 0 ? "text-red-600" : v > 0 ? "text-emerald-600" : "text-ink/60"}`}>
                      {v > 0 ? "+" : ""}{v === 0 ? "$0" : `$${money(v)}`}
                    </td>
                  );
                })}
                <td className={`px-2 py-1 text-right border-l border-ink/10 ${move! < 0 ? "text-red-600" : move! > 0 ? "text-emerald-600" : "text-ink/60"}`}>
                  {move! > 0 ? "+" : ""}${money(move!)}
                </td>
              </tr>
            ) : (
              <tr className="border-t border-ink/8">
                <td className="px-3 py-2 text-left text-amber-700/80 text-[11px]" colSpan={cols.length + 2}>
                  Pick an earlier &quot;from&quot; cut with an ingested snapshot to see this week vs last week. Only one snapshot exists so far.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {hasWoW && (
        <div className={`rounded-lg border px-3 py-2 text-sm font-semibold ${move! > 0 ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700" : move! < 0 ? "border-red-500/30 bg-red-500/10 text-red-600" : "border-ink/12 bg-ink/4 text-ink/75"}`}>
          {move! > 0 ? "▲ IMPROVING" : move! < 0 ? "▼ DECLINING" : "▬ FLAT"} — On-The-Books {move! > 0 ? "grew" : move! < 0 ? "dropped" : "held"} by {move! >= 0 ? "+" : ""}${money(move!)} vs last week ({data.compare_snapshot_date} → {data.snapshot_date}).
        </div>
      )}
    </div>
  );
}

/* ---------- 8.2 Dashboard ---------- */
function Dashboard({ data }: { data: Report }) {
  const { collapsed, toggle } = useQuarters();
  const cols = buildCols(data.months, collapsed);
  const qbg = "bg-[#e8e7e0]";
  // Total Revenue: Forecast = OTB Total Revenue + Sales on Property (Excel Dashboard r4).
  // Se muestran los DOS componentes por separado para que el forecast no se lea
  // como un solo numero magico: OTB (del archivo de OPERA) + On-Property (12.6%
  // del rooms forecast, estimado por el sistema, NO viene en el archivo).
  const otbRev = (d: MonthData) => d.otb.total_revenue;
  const onProp = (d: MonthData) => d.sales_on_property;
  const forecast = (d: MonthData) => d.otb.total_revenue + d.sales_on_property;
  const budget = (d: MonthData) => d.budget.total_revenue;
  const sumB = qsum(data.months, budget);
  const sumOTB = qsum(data.months, otbRev);
  const sumOnProp = qsum(data.months, onProp);
  const sumF = qsum(data.months, forecast);
  const sumG = data.net_gap_total;
  // Rooms Only: Budget vs OTB (sin on-property, es ingreso de habitaciones puro)
  const rBudget = (d: MonthData) => d.budget.rooms_only;
  const rForecast = (d: MonthData) => d.otb.rooms_only;
  const rGap = (d: MonthData) => d.otb.rooms_only - d.budget.rooms_only;
  const sumRB = qsum(data.months, rBudget);
  const sumRF = qsum(data.months, rForecast);
  const sumRG = sumRF - sumRB;

  const Row = (label: string, cls: string, get: (d: MonthData) => number, total: number, strong = false) => (
    <tr className={strong ? "border-t-2 border-ink/15 bg-emerald-900/20 font-bold" : "border-t border-ink/8"}>
      <td className={strong ? "px-3 py-2 text-left text-emerald-700" : `${tdL} ${cls}`}>{label}</td>
      {cols.map((c, i) => {
        const v = c.kind === "m" ? get(c.month) : qsum(c.months, get);
        return <td key={i} className={`px-2 py-1.5 text-right ${c.kind === "q" ? `${qbg} font-medium` : ""} ${neg(v)}`}>${money(v)}</td>;
      })}
      <td className={`px-2 py-1.5 text-right font-medium border-l border-ink/10 ${neg(total)}`}>${money(total)}</td>
    </tr>
  );

  const groupHead = (label: string) => (
    <tr className="bg-[#f2f1ec]">
      <td className="px-3 py-1.5 text-left text-[11px] font-bold uppercase tracking-wide text-ink/70" colSpan={cols.length + 2}>{label}</td>
    </tr>
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card label="Revenue Budget (year)" value={`$${money(sumB)}`} tone="sky" />
        <Card label="Revenue Forecast (OTB + on-property)" value={`$${money(sumF)}`} tone="emerald"
              sub={`$${money(sumOTB)} OTB ＋ $${money(sumOnProp)} on-property`} />
        <Card label="Total NET GAP (year)" value={`$${money(sumG)}`} tone={sumG < 0 ? "red" : "emerald"} />
        <Card label="Rooms Only gap (OTB − Budget)" value={`$${money(sumRG)}`} tone={sumRG < 0 ? "red" : "emerald"} />
      </div>
      <QuarterBar collapsed={collapsed} toggle={toggle} />
      <div className="overflow-x-auto rounded-lg border border-ink/10">
        <table className="w-full text-xs">
          <thead className="bg-[#fcfcfb]">
            <tr>
              <th className={thl}>Metric</th>
              {cols.map((c, i) => <th key={i} className={`${th} ${c.kind === "q" ? `${qbg} text-ink/85` : ""}`}>{c.label}</th>)}
              <th className={`${th} border-l border-ink/10`}>Total</th>
            </tr>
          </thead>
          <tbody>
            {groupHead("Total Revenue")}
            {Row("Revenue Budget", "text-sky-700", budget, sumB)}
            {Row("OTB Revenue (OPERA file)", "text-ink/60", otbRev, sumOTB)}
            {Row("＋ On-Property (12.6% est.)", "text-ink/60", onProp, sumOnProp)}
            {Row("＝ Revenue Forecast", "text-emerald-700 font-medium", forecast, sumF)}
            {Row("NET GAP", "", (d) => d.net_gap, sumG, true)}

            {groupHead("Rooms Only")}
            {Row("Rooms Only Budget", "text-sky-700", rBudget, sumRB)}
            {Row("Rooms Only Forecast (OTB)", "text-emerald-700", rForecast, sumRF)}
            {Row("Rooms Only Gap", "", rGap, sumRG, true)}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-ink/60">
        <b>Revenue Forecast = OTB Revenue (del archivo de OPERA) ＋ On-Property.</b> On-Property = 12.6% del rooms
        forecast, estimado por el sistema — NO viene en el archivo, por eso la suma cruda del reporte de OPERA da
        el renglón OTB, no el forecast total. Rooms Only compara el budget de habitaciones vs lo que está on the books (sin on-property).
      </p>
    </div>
  );
}

function Card({ label, value, tone, sub }: { label: string; value: string; tone: "sky" | "emerald" | "red"; sub?: string }) {
  const c = { sky: "text-sky-700", emerald: "text-emerald-700", red: "text-red-600" }[tone];
  return (
    <div className="rounded-lg border border-ink/10 bg-[#f2f1ec] p-3">
      <div className="text-[11px] uppercase tracking-wide text-ink/60">{label}</div>
      <div className={`mt-1 text-lg font-bold ${c}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[10px] text-ink/60">{sub}</div>}
    </div>
  );
}

/* ---------- 8.3 Daily Heatmap ---------- */
type HeatDay = { day: number; occ: number | null; sold: number | null; avail: number | null; risk: string | null; action: string | null };
type HeatMonth = {
  month: number; name: string; days: HeatDay[];
  otb_occ: number; budget_occ: number; variance: number;
  noches: number; pax: number; adr: number;
  budget_noches: number; budget_pax: number; budget_adr: number;
};
type HeatData = { year: number; snapshot_date: string | null; months: HeatMonth[] };

const RISK_BG: Record<string, string> = {
  CRITICAL: "bg-red-900 text-red-100",
  HIGH: "bg-red-600/80 text-white",
  MID: "bg-amber-500/80 text-black",
  OK: "bg-emerald-600/80 text-white",
};

function Heatmap({ year, asOf, refreshKey }: { year: number; asOf: string; refreshKey: number }) {
  const [d, setD] = useState<HeatData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true; setD(null); setErr("");
    fetch(`${API_URL}/ontb/heatmap?year=${year}${asOf ? `&as_of=${asOf}` : ""}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((x) => { if (!live) return; if (x.detail) setErr(x.detail); else setD(x); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [year, asOf, refreshKey]);

  if (err) return <div className="text-xs text-amber-700">No daily OTB data yet. ({err})</div>;
  if (!d) return <div className="text-xs text-ink/60">Loading…</div>;
  if (!d.snapshot_date) return <div className="text-xs text-amber-700">No OTB snapshot yet — ingest a day with history_forecast files.</div>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink/70">
        <span>OTB daily occupancy — snapshot <b className="text-ink/85">{d.snapshot_date}</b>. Occ% = Rooms Sold / Inventory.</span>
        <span className="flex items-center gap-2">
          {["OK", "MID", "HIGH", "CRITICAL"].map((k) => (
            <span key={k} className={`rounded px-1.5 py-0.5 ${RISK_BG[k]}`}>{k}</span>
          ))}
        </span>
        <span className="text-ink/60">Action: OK→HOLD · MID→WATCH · HIGH→RATE · CRITICAL→PUSH</span>
      </div>
      <div className="print-heatmap-wrap overflow-x-auto rounded-lg border border-ink/10">
        <table className="print-heatmap text-[10px]">
          <thead className="bg-[#fcfcfb]">
            <tr>
              <th rowSpan={2} className="sticky left-0 bg-[#fcfcfb] px-2 py-1 text-left text-ink/70">Month</th>
              {Array.from({ length: 31 }, (_, i) => <th rowSpan={2} key={i} className="w-7 px-0.5 py-1 text-center text-ink/60 align-bottom">{i + 1}</th>)}
              <th colSpan={4} className="border-l border-ink/12 px-2 py-1 text-center text-[10px] font-bold uppercase tracking-wide text-emerald-700">Forecast (OTB)</th>
              <th colSpan={4} className="border-l border-ink/12 px-2 py-1 text-center text-[10px] font-bold uppercase tracking-wide text-sky-700">Budget</th>
              <th rowSpan={2} className="border-l border-ink/12 px-2 py-1 text-right align-bottom text-ink/70">Occ&nbsp;Var</th>
            </tr>
            <tr>
              <th className="border-l border-ink/12 px-2 py-0.5 text-right text-emerald-700/70">Noches</th>
              <th className="px-2 py-0.5 text-right text-emerald-700/70">Pax</th>
              <th className="px-2 py-0.5 text-right text-emerald-700/70">ADR</th>
              <th className="px-2 py-0.5 text-right text-emerald-700/70">Occ%</th>
              <th className="border-l border-ink/12 px-2 py-0.5 text-right text-sky-700/70">Noches</th>
              <th className="px-2 py-0.5 text-right text-sky-700/70">Pax</th>
              <th className="px-2 py-0.5 text-right text-sky-700/70">ADR</th>
              <th className="px-2 py-0.5 text-right text-sky-700/70">Occ%</th>
            </tr>
          </thead>
          <tbody>
            {d.months.map((mo) => (
              <tr key={mo.month} className="border-t border-ink/8">
                <td className="sticky left-0 bg-[#f9f9f7] px-2 py-1 text-left text-ink/75 whitespace-nowrap">{mo.name}</td>
                {Array.from({ length: 31 }, (_, i) => {
                  const cell = mo.days[i];
                  if (!cell || cell.occ === null) return <td key={i} className="w-7" />;
                  return (
                    <td key={i} className={`w-7 px-0.5 py-1 text-center ${RISK_BG[cell.risk || "OK"]}`}
                      title={`${mo.name} ${cell.day}: ${cell.sold}/${cell.avail} · ${cell.risk} · ${cell.action}`}>
                      {Math.round((cell.occ || 0) * 100)}
                    </td>
                  );
                })}
                <td className="border-l border-ink/12 px-2 py-1 text-right text-ink/85">{dec(mo.noches)}</td>
                <td className="px-2 py-1 text-right text-ink/85">{dec(mo.pax)}</td>
                <td className="px-2 py-1 text-right text-ink/85">${money(mo.adr)}</td>
                <td className="px-2 py-1 text-right font-medium text-emerald-700">{pct(mo.otb_occ)}</td>
                <td className="border-l border-ink/12 px-2 py-1 text-right text-ink/70">{dec(mo.budget_noches)}</td>
                <td className="px-2 py-1 text-right text-ink/70">{dec(mo.budget_pax)}</td>
                <td className="px-2 py-1 text-right text-ink/70">${money(mo.budget_adr)}</td>
                <td className="px-2 py-1 text-right font-medium text-sky-700">{pct(mo.budget_occ)}</td>
                <td className={`border-l border-ink/12 px-2 py-1 text-right font-medium ${mo.variance < 0 ? "text-red-600" : "text-emerald-600"}`}>
                  {mo.variance >= 0 ? "+" : ""}{pct(mo.variance)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-ink/60">Numbers = daily occupancy %. Right columns = monthly Noches / Pax / ADR / Occ% for <span className="text-emerald-700">Forecast (OTB)</span> vs <span className="text-sky-700">Budget</span>, plus occupancy variance (percentage points). Hover a cell for rooms sold/available and the recommended action.</p>
    </div>
  );
}

/* ---------- 8.4 Pacing ---------- */
type Snap = { snapshot_date: string; otb_total_revenue: number; delta: number | null };
type PacingData = { snapshots: Snap[]; count: number };

function Pacing({ refreshKey, year }: { refreshKey: number; year: number }) {
  const [d, setD] = useState<PacingData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    fetch(`${API_URL}/ontb/pacing?year=${year}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((x) => { if (!live) return; if (x.detail) setErr(x.detail); else setD(x); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [refreshKey, year]);

  if (err) return <div className="text-xs text-amber-700">({err})</div>;
  if (!d) return <div className="text-xs text-ink/60">Loading…</div>;

  const max = Math.max(1, ...d.snapshots.map((s) => s.otb_total_revenue));

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink/70">
        Total On-The-Books revenue by weekly snapshot — how the year&apos;s bookings pace week over week.
        {d.count < 2 && <span className="text-amber-700"> Accumulating: {d.count} snapshot so far. The trend fills in as more days are ingested each week.</span>}
      </p>
      <div className="space-y-1.5">
        {d.snapshots.map((s) => (
          <div key={s.snapshot_date} className="flex items-center gap-3">
            <span className="w-24 text-right text-xs text-ink/75">{s.snapshot_date}</span>
            <div className="relative h-6 flex-1 rounded bg-[#f2f1ec]">
              <div className="h-6 rounded bg-emerald-600/70" style={{ width: `${(s.otb_total_revenue / max) * 100}%` }} />
              <span className="absolute inset-y-0 left-2 flex items-center text-[11px] text-ink">${money(s.otb_total_revenue)}</span>
            </div>
            <span className={`w-28 text-right text-xs ${s.delta === null ? "text-ink/45" : neg(s.delta)}`}>
              {s.delta === null ? "—" : `${s.delta >= 0 ? "+" : ""}$${money(s.delta)}`}
            </span>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-ink/60">Right column = change vs the previous snapshot (week-over-week booking pace).</p>
    </div>
  );
}

/* ---------- 8.5 Revenue Trend (OTB Forecast vs Budget + 2-per moving avg) ---------- */
function RevenueTrend({ data }: { data: Report }) {
  const m = data.months;
  // Mes "actual" = mes del snapshot OTB (as of). El GAP solo se muestra del mes
  // actual en adelante; en meses ya cerrados/pasados se oculta (pedido del owner).
  const curMonth = data.snapshot_date ? new Date(data.snapshot_date + "T00:00:00").getMonth() + 1 : 1;
  const budget = m.map((d) => d.budget.total_revenue);
  const forecast = m.map((d) => d.otb.total_revenue);
  // media móvil de 2 períodos del Forecast (arranca en el 2º mes)
  const ma = forecast.map((v, i) => (i === 0 ? null : (v + forecast[i - 1]) / 2));

  const W = 1120, H = 470, L = 70, R = 20, T = 40, B = 70;
  const plotW = W - L - R, plotH = H - T - B;
  const rawMax = Math.max(1, ...budget, ...forecast);
  const yMax = Math.ceil(rawMax / 100000) * 100000;
  const band = plotW / 12;
  const barW = band * 0.30;
  const y = (v: number) => T + plotH - (v / yMax) * plotH;
  const cx = (i: number) => L + i * band + band / 2;
  const kfmt = (v: number) => `$${Math.round(v / 1000).toLocaleString()}k`;

  const gridY = Array.from({ length: yMax / 100000 + 1 }, (_, i) => i * 100000);
  const maPts = ma.map((v, i) => (v === null ? null : `${cx(i)},${y(v)}`)).filter(Boolean).join(" ");

  return (
    <div className="space-y-2 max-w-[1500px] mx-auto">
      <div className="rounded-lg border border-ink/10 bg-[#f9f9f7] p-3">
        <div className="mb-1 text-center text-sm font-semibold text-ink/90">OTB Revenue trending versus Budget {data.year}</div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[760px]" role="img">
            {/* gridlines + y labels */}
            {gridY.map((g) => (
              <g key={g}>
                <line x1={L} y1={y(g)} x2={W - R} y2={y(g)} stroke="#e1e0d9" />
                <text x={L - 8} y={y(g) + 3} textAnchor="end" fontSize="10" fill="#898781">${(g / 1000).toLocaleString()}k</text>
              </g>
            ))}
            {/* bars */}
            {m.map((d, i) => {
              const bx = cx(i) - barW - 2;
              const fx = cx(i) + 2;
              return (
                <g key={i}>
                  <rect x={bx} y={y(budget[i])} width={barW} height={T + plotH - y(budget[i])} fill="#2a78d6">
                    <title>{`${MONTHS[i]} Budget: $${money(budget[i])}`}</title>
                  </rect>
                  <rect x={fx} y={y(forecast[i])} width={barW} height={T + plotH - y(forecast[i])} fill="#eb6834">
                    <title>{`${MONTHS[i]} Forecast (OTB): $${money(forecast[i])}`}</title>
                  </rect>
                  {/* budget value label (azul) */}
                  <text x={bx + barW / 2} y={y(budget[i]) - 4} textAnchor="middle" fontSize="9" fill="#52514e">{kfmt(budget[i])}</text>
                  {/* forecast value label */}
                  <text x={fx + barW / 2} y={y(forecast[i]) - 4} textAnchor="middle" fontSize="9" fill="#52514e">{kfmt(forecast[i])}</text>
                  {/* gap (budget shortfall) label — solo mes actual en adelante */}
                  {budget[i] - forecast[i] > 15000 && (i + 1) >= curMonth && (
                    <text x={cx(i)} y={T + plotH + 30} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#f87171">GAP {kfmt(budget[i] - forecast[i])}</text>
                  )}
                  {/* month label */}
                  <text x={cx(i)} y={T + plotH + 15} textAnchor="middle" fontSize="11" fill="#52514e">{MONTHS[i]}</text>
                </g>
              );
            })}
            {/* 2-period moving average line of forecast */}
            <polyline points={maPts} fill="none" stroke="#d03b3b" strokeWidth="2.5" strokeDasharray="8 4" />
            {ma.map((v, i) => v === null ? null : <circle key={i} cx={cx(i)} cy={y(v)} r="2.5" fill="#d03b3b" />)}
          </svg>
        </div>
        {/* legend */}
        <div className="mt-1 flex flex-wrap items-center justify-center gap-4 text-[11px] text-ink/75">
          <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm" style={{ background: "#2a78d6" }} /> Revenue Budget</span>
          <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm" style={{ background: "#eb6834" }} /> Revenue Forecast (OTB)</span>
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-5" style={{ background: "#d03b3b" }} /> 2-per. Moving Avg (Forecast)</span>
        </div>
      </div>
      <p className="text-[11px] text-ink/60">
        Forecast = On-The-Books total revenue (snapshot {data.snapshot_date}). GAP = Budget shortfall vs Forecast. Hover a bar for the exact amount.
      </p>
    </div>
  );
}

/* ---------- 8.5.1 Análisis 2027 (OTB 2027 vs 2026, mismo snapshot) ---------- */
function Analisis2027({ asOf, refreshKey }: { asOf: string; refreshKey: number }) {
  const [y27, setY27] = useState<Report | null>(null);
  const [y26, setY26] = useState<Report | null>(null);
  const [err, setErr] = useState("");
  const [metric, setMetric] = useState<"total" | "rooms">("total");
  const { collapsed, toggle } = useQuarters();
  useEffect(() => {
    if (!asOf) return;
    let live = true; setErr(""); setY27(null); setY26(null);
    const q = (yr: number) => `${API_URL}/ontb?year=${yr}&as_of=${asOf}`;
    Promise.all([
      fetch(q(2027), { cache: "no-store" }).then((r) => r.json()),
      fetch(q(2026), { cache: "no-store" }).then((r) => r.json()),
    ])
      .then(([a, b]) => { if (!live) return; setY27(a); setY26(b); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [asOf, refreshKey]);

  if (err) return <div className="text-xs text-amber-700">({err})</div>;
  if (!y27 || !y26) return <div className="text-xs text-ink/60">Loading…</div>;

  const field: "total_revenue" | "rooms_only" = metric === "total" ? "total_revenue" : "rooms_only";
  const budget27 = MONTHS.map((_, i) => y27.months[i]?.budget[field] ?? 0);
  const rev26 = MONTHS.map((_, i) => y26.months[i]?.otb[field] ?? 0);
  const rev27 = MONTHS.map((_, i) => y27.months[i]?.otb[field] ?? 0);
  const has27 = rev27.some((v) => v > 0);
  const totalB27 = budget27.reduce((a, b) => a + b, 0);
  const total26 = rev26.reduce((a, b) => a + b, 0);
  const total27 = rev27.reduce((a, b) => a + b, 0);
  const gapBudget = total27 - totalB27; // OTB 2027 vs Budget 2027

  // Colores vivos; orden pedido: Budget 2027 · OTB 2026 · OTB 2027.
  const seriesMeta = [
    { label: "Budget 2027", color: "#2a78d6" },
    { label: "OTB 2026", color: "#8C9196" },
    { label: "OTB 2027", color: "#eb6834" },
  ];
  // Columnas: cuarto colapsado = 1 columna (suma de sus 3 meses); si no, 3 meses.
  const s3 = (arr: number[], idxs: number[]) => idxs.reduce((a, i) => a + arr[i], 0);
  const cols: { label: string; vals: number[]; q: number }[] = [];
  for (let q = 1; q <= 4; q++) {
    const idxs = [0, 1, 2].map((k) => (q - 1) * 3 + k);
    if (collapsed.includes(q)) {
      cols.push({ label: `Q${q}`, vals: [s3(budget27, idxs), s3(rev26, idxs), s3(rev27, idxs)], q });
    } else {
      idxs.forEach((i) => cols.push({ label: MONTHS[i], vals: [budget27[i], rev26[i], rev27[i]], q }));
    }
  }
  const fyVals = [totalB27, total26, total27]; // Full Year (escala propia, eje derecho)

  const FY_W = 1.6; // ancho de la columna Full Year, en unidades de "band"
  const W = 1600, H = 520, L = 70, R = 74, T = 40, B = 70;
  const plotW = W - L - R, plotH = H - T - B, y0 = T + plotH;
  const N = cols.length;
  const band = plotW / (N + FY_W);
  const barW = band * 0.26;
  const gap = band * 0.06;
  const groupW = seriesMeta.length * barW + (seriesMeta.length - 1) * gap;
  const cx = (i: number) => L + i * band + band / 2;
  const kfmt = (v: number) => `$${Math.round(v / 1000).toLocaleString()}k`;
  const mfmt = (v: number) => (v >= 1000000 ? `$${(v / 1000000).toFixed(2)}M` : v <= 0 ? "$0" : kfmt(v));
  // Escala IZQUIERDA (meses / cuartos)
  const rawMax = Math.max(1, ...cols.flatMap((c) => c.vals));
  const lStep = rawMax <= 700000 ? 100000 : rawMax <= 1400000 ? 200000 : 500000;
  const yMax = Math.ceil(rawMax / lStep) * lStep;
  const y = (v: number) => y0 - (v / yMax) * plotH;
  const gridY = Array.from({ length: Math.floor(yMax / lStep) + 1 }, (_, i) => i * lStep);
  // Columna Full Year — escala DERECHA propia (el total anual no aplasta los períodos)
  const fyX0 = L + N * band;
  const fyCx = fyX0 + (band * FY_W) / 2;
  const fyRawMax = Math.max(1, ...fyVals);
  const fyStep = fyRawMax <= 3000000 ? 1000000 : 2000000;
  const fyMax = Math.ceil(fyRawMax / fyStep) * fyStep;
  const fyY = (v: number) => y0 - (v / fyMax) * plotH;
  const fyTicks = Array.from({ length: Math.floor(fyMax / fyStep) + 1 }, (_, i) => i * fyStep);
  // Separadores gruesos entre cuartos (donde cambia el cuarto de una columna a la otra)
  const dividers: number[] = [];
  for (let i = 0; i < cols.length - 1; i++) if (cols[i].q !== cols[i + 1].q) dividers.push(L + (i + 1) * band);
  const metricLbl = metric === "total" ? "Full Revenue" : "Rooms Revenue";

  return (
    <div className="space-y-2">
      <div className="rounded-lg border border-ink/10 bg-[#f9f9f7] p-3">
        <div className="mb-1 text-center text-sm font-semibold text-ink/90">Análisis 2027 — Budget 2027 · OTB 2026 · OTB 2027 · {metricLbl} (snapshot {y27.snapshot_date ?? asOf})</div>
        {!has27 && (
          <div className="mb-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-700">
            Aún no hay OTB 2027 en este snapshot. Subí el archivo de forecast que incluya fechas 2027 (re-corré el reporte OPERA con horizonte hasta 2027+) y volvé a cargar el día.
          </div>
        )}
        <div className="mb-2 flex flex-wrap items-center gap-x-5 gap-y-2">
          <div className="flex items-center gap-1">
            {(["total", "rooms"] as const).map((mk) => (
              <button key={mk} onClick={() => setMetric(mk)}
                className={`rounded px-2.5 py-1 text-[11px] ${metric === mk ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
                {mk === "total" ? "Full Revenue" : "Rooms Revenue"}
              </button>
            ))}
          </div>
          <QuarterBar collapsed={collapsed} toggle={toggle} />
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[760px]" role="img">
            {/* fondo sutil de la zona Full Year (escala propia) */}
            <rect x={fyX0} y={T} width={W - R - fyX0} height={plotH} fill="#ffffff08" />
            {/* gridlines + eje IZQUIERDO (períodos) */}
            {gridY.map((g) => (
              <g key={g}>
                <line x1={L} y1={y(g)} x2={W - R} y2={y(g)} stroke="#e1e0d9" />
                <text x={L - 8} y={y(g) + 3} textAnchor="end" fontSize="10" fill="#898781">${(g / 1000).toLocaleString()}k</text>
              </g>
            ))}
            {/* eje DERECHO (escala Full Year) */}
            {fyTicks.map((t, i) => (
              <text key={i} x={W - R + 6} y={fyY(t) + 3} textAnchor="start" fontSize="9" fill="#898781">{mfmt(t)}</text>
            ))}
            {/* separadores entre cuartos — rojo negrita */}
            {dividers.map((dx, i) => (
              <line key={i} x1={dx} y1={T} x2={dx} y2={y0} stroke="#d03b3b" strokeWidth={3} />
            ))}
            {/* divisor Full Year — rojo más grueso */}
            <line x1={fyX0} y1={T - 8} x2={fyX0} y2={y0} stroke="#dc2626" strokeWidth={4.5} />
            {/* barras por período (escala izquierda) */}
            {cols.map((c, i) => {
              const gx = cx(i) - groupW / 2;
              return (
                <g key={i}>
                  {seriesMeta.map((s, si) => {
                    const bx = gx + si * (barW + gap);
                    const v = c.vals[si];
                    const topY = y(v);
                    const lx = bx + barW / 2;
                    return (
                      <g key={si}>
                        <rect x={bx} y={topY} width={barW} height={y0 - topY} fill={s.color}>
                          <title>{`${c.label} ${s.label}: $${money(v)}`}</title>
                        </rect>
                        {v > 0 && (
                          <text x={lx} y={topY - 5} textAnchor="middle" fontSize="9" fontWeight="600" fill="#0b0b0b">{kfmt(v)}</text>
                        )}
                      </g>
                    );
                  })}
                  <text x={cx(i)} y={y0 + 15} textAnchor="middle" fontSize="11" fill="#ffffffaa">{c.label}</text>
                </g>
              );
            })}
            {/* columna Full Year (escala derecha) */}
            {(() => {
              const gx = fyCx - groupW / 2;
              return (
                <g>
                  {seriesMeta.map((s, si) => {
                    const bx = gx + si * (barW + gap);
                    const v = fyVals[si];
                    const topY = fyY(v);
                    const lx = bx + barW / 2;
                    return (
                      <g key={si}>
                        <rect x={bx} y={topY} width={barW} height={y0 - topY} fill={s.color}>
                          <title>{`Full Year ${s.label}: $${money(v)}`}</title>
                        </rect>
                        {v > 0 && (
                          <text x={lx} y={topY - 5} textAnchor="middle" fontSize="9" fontWeight="700" fill="#0b0b0b">{mfmt(v)}</text>
                        )}
                      </g>
                    );
                  })}
                  <text x={fyCx} y={y0 + 15} textAnchor="middle" fontSize="11" fontWeight="700" fill="#52514e">Full Year</text>
                </g>
              );
            })()}
          </svg>
        </div>
        <div className="mt-1 flex flex-wrap items-center justify-center gap-4 text-[11px] text-ink/75">
          {seriesMeta.map((s) => (
            <span key={s.label} className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm" style={{ background: s.color }} /> {s.label}</span>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-3 text-[11px]">
        <div className="rounded-lg border border-ink/10 bg-[#f2f1ec] px-3 py-2"><span className="text-ink/60">Budget 2027:</span> <b className="text-sky-700">${money(totalB27)}</b></div>
        <div className="rounded-lg border border-ink/10 bg-[#f2f1ec] px-3 py-2"><span className="text-ink/60">OTB 2026:</span> <b className="text-ink/75">${money(total26)}</b></div>
        <div className="rounded-lg border border-ink/10 bg-[#f2f1ec] px-3 py-2"><span className="text-ink/60">OTB 2027:</span> <b className="text-orange-300">${money(total27)}</b></div>
        <div className="rounded-lg border border-ink/10 bg-[#f2f1ec] px-3 py-2"><span className="text-ink/60">OTB 2027 vs Budget:</span> <b className={gapBudget >= 0 ? "text-emerald-700" : "text-red-600"}>{gapBudget >= 0 ? "+" : "−"}${money(Math.abs(gapBudget))}</b></div>
      </div>
      <p className="text-[11px] text-ink/60">
        {metricLbl} por {cols.length === 12 ? "mes" : "período"} (snapshot {y27.snapshot_date ?? asOf}): <span className="text-sky-700">Budget 2027</span> · <span className="text-ink/75">OTB 2026</span> · <span className="text-orange-300">OTB 2027</span>. Toggle <b>Full/Rooms Revenue</b> y colapsá cuartos (＋Q) para ver el total del trimestre. Las líneas gruesas separan los cuartos; la columna <b>Full Year</b> (tras la línea gruesa) es el total anual y usa su <b>propia escala</b> (eje derecho), para no aplastar los meses. "OTB 2027 vs Budget" = cuánto falta reservar para llegar al presupuesto.
      </p>
    </div>
  );
}

/* ---------- 8.6 Occupancy Trend (% Budget vs % Forecast, líneas) ---------- */
function OccupancyTrend({ data }: { data: Report }) {
  const m = data.months;
  const budget = m.map((d) => d.budget.occ);
  const forecast = m.map((d) => d.otb.occ);

  const W = 1120, H = 450, L = 55, R = 20, T = 40, B = 60;
  const plotW = W - L - R, plotH = H - T - B;
  const yMax = 1.0; // 100%
  const band = plotW / 12;
  const cx = (i: number) => L + i * band + band / 2;
  const y = (v: number) => T + plotH - (v / yMax) * plotH;
  const poly = (arr: number[]) => arr.map((v, i) => `${cx(i)},${y(v)}`).join(" ");
  const grid = Array.from({ length: 10 }, (_, i) => (i + 1) / 10);

  return (
    <div className="space-y-2 max-w-[1500px] mx-auto">
      <div className="rounded-lg border border-ink/10 bg-[#f9f9f7] p-3">
        <div className="mb-1 text-center text-sm font-semibold text-ink/90">OTB Occupancy trending versus Budget {data.year}</div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[760px]" role="img">
            {grid.map((g) => (
              <g key={g}>
                <line x1={L} y1={y(g)} x2={W - R} y2={y(g)} stroke="#e1e0d9" />
                <text x={L - 8} y={y(g) + 3} textAnchor="end" fontSize="10" fill="#898781">{Math.round(g * 100)}%</text>
              </g>
            ))}
            {/* budget line */}
            <polyline points={poly(budget)} fill="none" stroke="#2a78d6" strokeWidth="2.5" />
            {/* forecast line */}
            <polyline points={poly(forecast)} fill="none" stroke="#eb6834" strokeWidth="2.5" />
            {m.map((d, i) => (
              <g key={i}>
                <circle cx={cx(i)} cy={y(budget[i])} r="3" fill="#2a78d6" />
                <circle cx={cx(i)} cy={y(forecast[i])} r="3" fill="#eb6834" />
                {/* labels: forecast above, budget below */}
                <text x={cx(i)} y={y(forecast[i]) - 7} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#eb6834">{Math.round(forecast[i] * 100)}%</text>
                <text x={cx(i)} y={y(budget[i]) + 14} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#2a78d6">{Math.round(budget[i] * 100)}%</text>
                <text x={cx(i)} y={T + plotH + 16} textAnchor="middle" fontSize="11" fill="#52514e">{MONTHS[i]}</text>
              </g>
            ))}
          </svg>
        </div>
        <div className="mt-1 flex flex-wrap items-center justify-center gap-4 text-[11px] text-ink/75">
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-5" style={{ background: "#2a78d6" }} /> % Budget {data.year}</span>
          <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-5" style={{ background: "#eb6834" }} /> % Forecast (OTB) {data.year}</span>
        </div>
      </div>
      <p className="text-[11px] text-ink/60">Monthly occupancy: Budget vs On-The-Books forecast (snapshot {data.snapshot_date}).</p>
    </div>
  );
}

/* ---------- 8.7 Variance Breakdown (pie del déficit por mes) ---------- */
// Orden categórico validado (separación para daltonismo comprobada, no elegida
// a ojo): los 8 primeros son los slots canónicos; del 9 al 12 son pasos más
// débiles, a propósito, porque a esa altura las porciones son minúsculas.
// NOTA(bismark): 12 porciones superan lo que cualquier paleta distingue de un
// vistazo. Si el pie suele pasar de ~8 categorías, conviene agrupar la cola en
// "Otros" en vez de seguir sumando colores.
const PIE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
  "#4a3aa7", "#e34948", "#86b6ef", "#c98500", "#9085e9", "#898781"];

function VariancePie({ data }: { data: Report }) {
  const m = data.months;
  // déficit por mes = -net_gap donde el OTB va por DEBAJO del budget (net_gap < 0)
  const slices = m
    .map((d) => ({ name: MONTHS[d.month - 1], val: d.net_gap < 0 ? -d.net_gap : 0, gap: d.net_gap }))
    .filter((s) => s.val > 0)
    .sort((a, b) => b.val - a.val);
  const total = slices.reduce((s, x) => s + x.val, 0);

  const cx = 170, cy = 170, r = 150;
  let ang = -Math.PI / 2;
  const paths = slices.map((s, i) => {
    const frac = s.val / total;
    const a0 = ang, a1 = ang + frac * 2 * Math.PI;
    ang = a1;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const large = frac > 0.5 ? 1 : 0;
    const mid = (a0 + a1) / 2;
    const lx = cx + r * 0.6 * Math.cos(mid), ly = cy + r * 0.6 * Math.sin(mid);
    return { d: `M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} Z`, color: PIE_COLORS[i % PIE_COLORS.length], frac, lx, ly, s };
  });

  if (!slices.length) return <div className="text-xs text-emerald-700">No shortfall — On-The-Books meets or beats budget in every month. 🎉</div>;

  return (
    <div className="space-y-2">
      <div className="rounded-lg border border-ink/10 bg-[#f9f9f7] p-3">
        <div className="mb-2 text-center text-sm font-semibold text-ink/90">Variance breakdown — where the year&apos;s gap comes from</div>
        <div className="flex flex-col items-center gap-6 md:flex-row md:items-start md:justify-center">
          <svg viewBox="0 0 340 340" className="w-[300px] shrink-0" role="img">
            {paths.map((p, i) => (
              <g key={i}>
                <path d={p.d} fill={p.color} stroke="#f9f9f7" strokeWidth="1.5" />
                {p.frac > 0.05 && (
                  <text x={p.lx} y={p.ly} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#000">{Math.round(p.frac * 100)}%</text>
                )}
              </g>
            ))}
          </svg>
          <div className="w-full max-w-sm">
            <table className="w-full text-xs">
              <thead><tr className="text-ink/60">
                <th className="px-2 py-1 text-left">Month</th>
                <th className="px-2 py-1 text-right">Shortfall</th>
                <th className="px-2 py-1 text-right">% of gap</th>
              </tr></thead>
              <tbody>
                {paths.map((p, i) => (
                  <tr key={i} className="border-t border-ink/8">
                    <td className="px-2 py-1 text-left">
                      <span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: p.color }} />
                      {p.s.name}
                    </td>
                    <td className="px-2 py-1 text-right text-red-600">${money(p.s.val)}</td>
                    <td className="px-2 py-1 text-right text-ink/75">{Math.round(p.frac * 100)}%</td>
                  </tr>
                ))}
                <tr className="border-t border-ink/15 font-bold">
                  <td className="px-2 py-1 text-left">Total gap</td>
                  <td className="px-2 py-1 text-right text-red-600">${money(total)}</td>
                  <td className="px-2 py-1 text-right">100%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <p className="text-[11px] text-ink/60">
        Only months where On-The-Books is <b>below</b> budget (NET GAP &lt; 0). Shows which months drive the year&apos;s revenue shortfall — where the remaining risk sits (snapshot {data.snapshot_date}).
      </p>
    </div>
  );
}
