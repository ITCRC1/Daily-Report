"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import ExcelButton from "@/components/ExcelButton";
import { useSubtabs } from "@/lib/useSubtabs";
import RevenueActualDaily from "@/components/RevenueActualDaily";
import DailyBudget from "@/components/DailyBudget";

type Row = Record<string, string | null> & { id: string };
type Col = { key: string; label: string; required?: boolean };

const ALL_SUBTABS = [
  { id: "6.1", label: "6.1 Monthly Budget" },
  { id: "6.1.1", label: "6.1.1 Forecast" },
  { id: "6.2", label: "6.2 Cash Mapping" },
  { id: "6.3", label: "6.3 Integrity Mapping" },
  { id: "6.4", label: "6.4 Daily Revenue by Day/Dept" },
  { id: "6.5", label: "6.5 Daily Budget by Day/Dept" },
  { id: "6.6", label: "6.6 Rooms Statistics YTD" },
  { id: "6.7", label: "6.7 Rooms Mapping" },
  { id: "6.8", label: "6.8 Market Codes Mapping" },
  { id: "6.9", label: "6.9 Parámetros / Cuentas" },
  { id: "6.10", label: "6.10 Weekly Calendar" },
];

// The `key`s must match the real backend fields 1:1 (columns of
// dim_payment_map/dim_department/dim_room_category) -- don't translate them,
// only the `label` shown in the column header.
const PAYMENT_MAP_COLS: Col[] = [
  { key: "transaction_code", label: "TCode", required: true },
  { key: "code", label: "Code" },
  { key: "description", label: "Description" },
  { key: "banco_codigo", label: "Bank" },
  { key: "banco_nombre", label: "Bank (name)" },
  { key: "moneda", label: "Currency" },
  { key: "tipo_pago", label: "Payment Type" },
  { key: "marca_metodo", label: "Brand/Method" },
  { key: "grupo", label: "Group" },
  { key: "cash_flow", label: "Cash Flow" },
  { key: "canal", label: "Channel" },
  { key: "report_bucket", label: "Bucket" },
];

const DEPARTMENT_COLS: Col[] = [
  { key: "cuenta_nature", label: "Nature (9-char)" },
  { key: "cost_center", label: "Cost Center (4-dig)" },
  { key: "outlet_name", label: "Outlet" },
  { key: "output_column", label: "Output Column", required: true },
];

const ROOM_CATEGORY_COLS: Col[] = [
  { key: "code2", label: "Code2 (Opera)", required: true },
  { key: "report_name", label: "Name (report)" },
  { key: "opera_short_desc", label: "Opera Short Desc" },
  { key: "room_class", label: "Room Class (STATISTICS)" },
  { key: "integrity_string", label: "Integrity String (ref.)" },
  { key: "units", label: "Units" },
];

// KPI Group is free text on purpose (§3.2, Tab 3.2 Market Segment) -- a code
// with a KPI Group not seen elsewhere just becomes its own channel row; a
// blank one falls into "Unmapped" (visible, never dropped silently).
const MARKET_CODE_COLS: Col[] = [
  { key: "code", label: "Market Code (Opera)", required: true },
  { key: "name", label: "Name" },
  { key: "kpi_group", label: "KPI Group (channel)" },
];

type BudgetMonthlyRow = {
  dept_code: string | null; dept_name: string | null; month: number; amount_usd: number;
  available_rooms: number | null; rooms_occupied: number | null; guests: number | null;
  occupancy_pct: number | null; adr: number | null;
};
type BudgetDailyRow = {
  date: string; dept_code: string | null; dept_name: string | null; amount_usd: number;
};

const MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const money = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const valueColor = (v: number) => (v < 0 ? "!text-rose-600" : "");
const bTh = "px-4 py-3 text-left font-medium text-ink/70 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-ink/70 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-ink/85";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-ink/85";

// 6.1 Budget y 6.1.1 Forecast son el mismo panel con distinto endpoint: mismo
// grano (depto x mes), misma plantilla y mismo reemplazo total del anio.
function YearBudget({ kind = "budget" }: { kind?: "budget" | "forecast" }) {
  const isForecast = kind === "forecast";
  const endpoint = `/master-data/${kind}`;
  const noun = isForecast ? "forecast" : "budget";
  const Noun = isForecast ? "Forecast" : "Budget";
  const [year, setYear] = useState(new Date().getFullYear());
  const [rows, setRows] = useState<BudgetMonthlyRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}${endpoint}?year=${year}`, { cache: "no-store" });
      setRows(res.ok ? await res.json() : []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [year, endpoint]);

  useEffect(() => { load(); }, [load]);

  async function downloadTemplate() {
    setMsg("Preparing template…");
    try {
      // fetch (not a plain <a href>) so a backend failure surfaces as a
      // message here instead of a blank browser tab.
      const res = await fetch(`${API_URL}${endpoint}/template?year=${year}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `${Noun}_${year}_template.xlsx`;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      setMsg("");
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
  }

  async function upload(file: File) {
    setUploading(true); setMsg("Uploading…");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}${endpoint}/upload?year=${year}`, { method: "POST", body: form });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setMsg(`Loaded: ${body.rows_loaded} rows${body.dept_codes_no_reconocidos?.length ? ` (⚠ unrecognized codes: ${body.dept_codes_no_reconocidos.join(", ")})` : ""}.`);
      await load();
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setUploading(false);
    }
  }

  // Pivot: dept -> [amount per month 1..12]
  const byDept = new Map<string, { name: string; amounts: number[] }>();
  for (const r of rows) {
    const key = r.dept_code ?? "—";
    const entry = byDept.get(key) ?? { name: r.dept_name ?? "", amounts: Array(12).fill(0) };
    entry.amounts[r.month - 1] = r.amount_usd;
    byDept.set(key, entry);
  }
  const totals = Array(12).fill(0);
  for (const { amounts } of byDept.values()) amounts.forEach((a, i) => (totals[i] += a));

  // Monthly stats (go in the Rooms row -- unique per month, not per dept)
  const stats = {
    available_rooms: Array(12).fill(null) as (number | null)[],
    rooms_occupied: Array(12).fill(null) as (number | null)[],
    guests: Array(12).fill(null) as (number | null)[],
    occupancy_pct: Array(12).fill(null) as (number | null)[],
    adr: Array(12).fill(null) as (number | null)[],
  };
  for (const r of rows) {
    if (r.available_rooms === null) continue;
    const i = r.month - 1;
    stats.available_rooms[i] = r.available_rooms;
    stats.rooms_occupied[i] = r.rooms_occupied;
    stats.guests[i] = r.guests;
    stats.occupancy_pct[i] = r.occupancy_pct;
    stats.adr[i] = r.adr;
  }
  const hasStats = stats.available_rooms.some((v) => v !== null);
  const availTotal = stats.available_rooms.reduce((a: number, v) => a + (v ?? 0), 0);
  const occTotal = stats.rooms_occupied.reduce((a: number, v) => a + (v ?? 0), 0);
  const guestsTotal = stats.guests.reduce((a: number, v) => a + (v ?? 0), 0);
  const occPctTotal = availTotal ? occTotal / availTotal : 0;
  const adrTotal = occTotal
    ? stats.adr.reduce((a: number, v, i) => a + (v ?? 0) * (stats.rooms_occupied[i] ?? 0), 0) / occTotal
    : 0;
  const STAT_TOTALS: Record<string, number> = {
    available_rooms: availTotal, rooms_occupied: occTotal, guests: guestsTotal,
    occupancy_pct: occPctTotal, adr: adrTotal,
  };
  const STAT_ROWS: { key: keyof typeof stats; label: string; fmt: (v: number) => string }[] = [
    { key: "available_rooms", label: "Available Rooms", fmt: (v) => intFmt(v) },
    { key: "rooms_occupied", label: "Occupied Rooms", fmt: (v) => intFmt(v) },
    { key: "guests", label: "Guests", fmt: (v) => intFmt(v) },
    { key: "occupancy_pct", label: "% Occupancy", fmt: (v) => `${(v * 100).toFixed(1)}%` },
    { key: "adr", label: "ADR", fmt: (v) => `$${money(v)}` },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-ink/75">
          Year:
          <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value, 10) || year)}
            className="w-24 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
        <button onClick={downloadTemplate}
          className="rounded bg-ink/5 px-3 py-1.5 text-xs font-medium text-white hover:bg-ink/8">
          📥 Download {year} template
        </button>
        <label className="cursor-pointer rounded bg-accent px-3 py-1.5 text-xs font-medium text-white">
          {uploading ? "Uploading…" : "📤 Upload filled template"}
          <input type="file" accept=".xlsx" className="hidden" disabled={uploading}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
        </label>
      </div>
      <p className="text-[11px] text-ink/60">
        Cycle: download the template (comes pre-filled with what&apos;s already loaded for the year), fill
        it out in Excel, and upload it again — this fully replaces that year&apos;s {noun}{" "}
        {isForecast ? "(full-year replacement)" : '("annual reset")'}.
      </p>
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}
      {loading && <div className="text-xs text-ink/60">Loading…</div>}

      {byDept.size > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="bg-[#fcfcfb]">
              <tr>
                <th className={bTh}>Dept</th>
                {MESES.map((m) => <th key={m} className={bThN}>{m}</th>)}
                <th className={bThN}>Total</th>
              </tr>
            </thead>
            <tbody>
              {[...byDept.entries()].map(([code, { name, amounts }]) => (
                <tr key={code} className="border-t border-ink/8">
                  <td className={bTd}>{code} · {name}</td>
                  {amounts.map((a, i) => <td key={i} className={`${bTdN} ${valueColor(a)}`}>{a ? `$${money(a)}` : <span className="text-ink/45">—</span>}</td>)}
                  <td className={`${bTdN} font-medium ${valueColor(amounts.reduce((a, b) => a + b, 0))}`}>${money(amounts.reduce((a, b) => a + b, 0))}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={bTd}>TOTAL</td>
                {totals.map((t, i) => <td key={i} className={`${bTdN} ${valueColor(t)}`}>${money(t)}</td>)}
                <td className={`${bTdN} ${valueColor(totals.reduce((a, b) => a + b, 0))}`}>${money(totals.reduce((a, b) => a + b, 0))}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <div className="rounded-lg border border-dashed border-ink/12 bg-[#fcfcfb]/50 p-4 text-xs text-ink/60">
          No {noun} loaded for {year} yet.
        </div>
      )}

      {hasStats && (
        <div className="overflow-x-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="bg-[#fcfcfb]">
              <tr>
                <th className={bTh}>Statistics</th>
                {MESES.map((m) => <th key={m} className={bThN}>{m}</th>)}
                <th className={bThN}>Total</th>
              </tr>
            </thead>
            <tbody>
              {STAT_ROWS.map(({ key, label, fmt }) => (
                <tr key={key} className="border-t border-ink/8">
                  <td className={bTd}>{label}</td>
                  {stats[key].map((v, i) => (
                    <td key={i} className={`${bTdN} ${v !== null ? valueColor(v) : ""}`}>{v !== null ? fmt(v) : <span className="text-ink/45">—</span>}</td>
                  ))}
                  <td className={`${bTdN} font-medium ${valueColor(STAT_TOTALS[key])}`}>{fmt(STAT_TOTALS[key])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

type RoomStatCategory = {
  category: string; units: number; revenue: number; revenue_pct: number;
  stay_rooms: number; stay_persons: number; physical_rooms: number;
  occupancy_pct: number; adr: number; yield_index: number;
};
type RoomStatOpeningRow = {
  id: string | null; room_category: string; units: number; anchor_date: string | null;
  revenue: number; stay_rooms: number; stay_persons: number; physical_rooms: number;
};
type YtdCompsLine = {
  stay_rooms: number; stay_persons: number; revenue: number;
  anchor_rooms: number; post_cutoff_rooms: number; cutoff: string | null;
};
type YtdNet = {
  revenue: number; stay_rooms: number; stay_persons: number; physical_rooms: number;
  occupancy_pct: number; adr: number; units: number;
};

const COMPS_SENTINEL = "Comps/In-House";

function RoomStatsYtd() {
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10));
  const [ytd, setYtd] = useState<{ categories: RoomStatCategory[]; overall: RoomStatCategory; comps_line?: YtdCompsLine; net?: YtdNet } | null>(null);
  const [openings, setOpenings] = useState<RoomStatOpeningRow[]>([]);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<RoomStatOpeningRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const loadYtd = useCallback(async (d: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/master-data/room-stats/ytd?as_of=${d}`, { cache: "no-store" });
      setYtd(res.ok ? await res.json() : null);
    } catch {
      setYtd(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOpenings = useCallback(async () => {
    const res = await fetch(`${API_URL}/master-data/room-stats/opening`, { cache: "no-store" });
    setOpenings(res.ok ? await res.json() : []);
  }, []);

  useEffect(() => { loadYtd(asOf); }, [asOf, loadYtd]);
  useEffect(() => { loadOpenings(); }, [loadOpenings]);

  function startEdit() {
    setDraft(openings.map((o) => ({ ...o, anchor_date: o.anchor_date ?? asOf })));
    setEditing(true);
    setMsg("");
  }

  // Los campos numéricos del draft se guardan como STRING mientras se editan
  // (para poder tipear/pegar libremente sin que se reformatee en cada tecla);
  // se parsean acá, tolerando comas/espacios de un copy-paste de Excel.
  const toNum = (v: unknown) => {
    const n = Number(String(v ?? "").replace(/[,\s]/g, ""));
    return Number.isFinite(n) ? n : 0;
  };

  async function saveOpenings() {
    setSaving(true); setMsg("");
    try {
      const items = draft.map((d) => ({
        room_category: d.room_category, anchor_date: d.anchor_date,
        revenue: toNum(d.revenue), stay_rooms: toNum(d.stay_rooms),
        stay_persons: toNum(d.stay_persons), physical_rooms: toNum(d.physical_rooms),
      }));
      const res = await fetch(`${API_URL}/master-data/room-stats/opening`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setOpenings(body);
      setEditing(false);
      setMsg("Cutoff saved.");
      await loadYtd(asOf);
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  }

  function updateDraft(cat: string, field: keyof RoomStatOpeningRow, value: string) {
    // Guarda el valor crudo (string) -- no se convierte a número en cada tecla,
    // así se puede tipear un decimal o pegar "300,034.32" sin pelear con el input.
    setDraft((prev) => prev.map((d) => d.room_category === cat
      ? ({ ...d, [field]: value } as RoomStatOpeningRow)
      : d));
  }

  // Pegar una COLUMNA de Excel (varios valores separados por salto de línea o
  // tab) en un campo: rellena hacia abajo desde la fila donde se pegó. Devuelve
  // true si consumió el pegado (para preventDefault); false si era un solo valor.
  function pasteColumn(startCat: string, field: keyof RoomStatOpeningRow, text: string): boolean {
    const vals = text.split(/[\r\n\t]+/).map((s) => s.trim()).filter((s) => s.length > 0);
    if (vals.length <= 1) return false;
    setDraft((prev) => {
      const idx = prev.findIndex((d) => d.room_category === startCat);
      if (idx < 0) return prev;
      const next = [...prev];
      for (let i = 0; i < vals.length && idx + i < next.length; i++) {
        next[idx + i] = { ...next[idx + i], [field]: vals[i] } as RoomStatOpeningRow;
      }
      return next;
    });
    return true;
  }

  const rows = ytd?.categories ?? [];
  const overall = ytd?.overall;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-ink/70">
          YTD as of:{" "}
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)}
            className="ml-1 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
        {!editing ? (
          <button onClick={startEdit} className="rounded bg-ink/5 px-2.5 py-1 text-[11px] text-ink/75 hover:text-ink">
            ✎ Edit cutoff / anchor
          </button>
        ) : (
          <div className="flex gap-1.5">
            <button onClick={saveOpenings} disabled={saving} className="rounded bg-accent px-2.5 py-1 text-[11px] text-white disabled:opacity-50">
              {saving ? "Saving…" : "Save cutoff"}
            </button>
            <button onClick={() => setEditing(false)} className="rounded bg-ink/5 px-2.5 py-1 text-[11px] text-ink/75">Cancel</button>
          </div>
        )}
        {loading && <span className="text-xs text-ink/60">Loading…</span>}
      </div>
      <p className="text-[11px] text-ink/60">
        Real accumulation (fact_room_stat, statroomtype XML ingestion from Tab 1) on top of an editable YTD
        anchor per category — the anchor represents the accumulated total up to its date; any day ingested
        AFTER the anchor is summed automatically, with nothing to re-load. Adjust the anchor here whenever
        Bismark brings a new cutoff. The editable <span className="text-amber-700">Comps / In-House</span> row
        holds the accumulated complimentary/house-use up to the cutoff; from the cutoff onward it's read live
        from Opera STATISTICS (COM/INHOUSE). El pie se lee como una suma: NET (habitaciones que pagan, ADR limpio) + Comps/In-House = TOTAL (habitaciones ocupadas).
      </p>
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}

      {editing ? (
        <div className="overflow-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="bg-[#fcfcfb]">
              <tr>
                <th className={bTh}>Category</th>
                <th className={bTh}>Anchor (date)</th>
                <th className={bThN}>Total Nights (accum.)</th>
                <th className={bThN}>Nights Occupied (accum.)</th>
                <th className={bThN}>Revenue (accum.)</th>
                <th className={bThN}>Pax (accum.)</th>
              </tr>
            </thead>
            <tbody>
              {draft.map((d) => {
                const isComps = d.room_category === COMPS_SENTINEL;
                return (
                <tr key={d.room_category} className={`border-t border-ink/8 ${isComps ? "bg-[#fbf3e6]" : ""}`}>
                  <td className={`${bTd} ${isComps ? "text-amber-700 font-medium" : ""}`}>
                    {isComps ? "Comps / In-House" : d.room_category}
                    {isComps && <span className="ml-1 block text-[10px] text-amber-700/50">acumulado hasta el corte (RN, revenue, pax)</span>}
                  </td>
                  <td className={bTd}>
                    <input type="date" value={d.anchor_date ?? ""} onChange={(e) => updateDraft(d.room_category, "anchor_date", e.target.value)}
                      className="rounded border border-ink/12 bg-[#f9f9f7] px-1.5 py-1 text-ink" />
                  </td>
                  {(["physical_rooms", "stay_rooms", "revenue", "stay_persons"] as const).map((f) => (
                    <td key={f} className={bTdN}>
                      {isComps && f === "physical_rooms" ? (
                        <span className="text-ink/45">—</span>
                      ) : (
                        <input type="text" inputMode="decimal"
                          value={String(d[f] ?? "")}
                          onChange={(e) => updateDraft(d.room_category, f, e.target.value)}
                          onPaste={(e) => {
                            if (pasteColumn(d.room_category, f, e.clipboardData.getData("text"))) e.preventDefault();
                          }}
                          className="w-28 rounded border border-ink/12 bg-[#f9f9f7] px-1.5 py-1 text-right text-ink" />
                      )}
                    </td>
                  ))}
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-ink/10 shadow-lg">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-[#dfeafc] to-[#fcfcfb]">
              <tr>
                <th className={bTh}>Room Category</th>
                <th className={bThN}>Units</th>
                <th className={bThN}>Total Nights</th>
                <th className={bThN}>Total Nights Occupied</th>
                <th className={bThN}>Occupancy</th>
                <th className={bThN}>Total Revenue</th>
                <th className={bThN}>ADR</th>
                <th className={bThN}>Total Pax</th>
                <th className={bThN}>% of Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.category} className="border-t border-ink/8">
                  <td className={bTd}>{c.category}</td>
                  <td className={bTdN}>{intFmt(c.units)}</td>
                  <td className={bTdN}>{intFmt(c.physical_rooms)}</td>
                  <td className={bTdN}>{intFmt(c.stay_rooms)}</td>
                  <td className={bTdN}>{(c.occupancy_pct * 100).toFixed(1)}%</td>
                  <td className={`${bTdN} ${valueColor(c.revenue)}`}>${money(c.revenue)}</td>
                  <td className={`${bTdN} ${valueColor(c.adr)}`}>${money(c.adr)}</td>
                  <td className={bTdN}>{intFmt(c.stay_persons)}</td>
                  <td className={bTdN}>{(c.revenue_pct * 100).toFixed(1)}%</td>
                </tr>
              ))}
              {/* Pie del reporte (pedido del owner 2026-07-11): se lee de abajo
                  hacia el total como una SUMA -> NET (habitaciones que pagan) +
                  Comps/In-House = TOTAL (habitaciones ocupadas). Antes el orden
                  era Total(gross) -> Comps -> Net (resta), y confundía. */}
              {ytd?.net && ytd?.comps_line && ytd.comps_line.stay_rooms > 0 && (
                <tr className="border-t-2 border-ink/15 bg-[#e8f0fb] font-bold text-emerald-700/90">
                  <td className={bTd}>NET (revenue rooms)</td>
                  <td className={bTdN}>{intFmt(ytd.net.units)}</td>
                  <td className={bTdN}>{intFmt(ytd.net.physical_rooms)}</td>
                  <td className={bTdN}>{intFmt(ytd.net.stay_rooms)}</td>
                  <td className={bTdN}>{(ytd.net.occupancy_pct * 100).toFixed(1)}%</td>
                  <td className={`${bTdN} ${valueColor(ytd.net.revenue)}`}>${money(ytd.net.revenue)}</td>
                  <td className={`${bTdN} ${valueColor(ytd.net.adr)}`}>${money(ytd.net.adr)}</td>
                  <td className={bTdN}>{intFmt(ytd.net.stay_persons)}</td>
                  <td className={bTdN}>—</td>
                </tr>
              )}
              {ytd?.comps_line && ytd.comps_line.stay_rooms > 0 && (
                <tr className="border-t border-ink/10 bg-[#fbf3e6] italic text-amber-700/80">
                  <td className={bTd}>+ Comps / In-House <span className="not-italic text-[10px] text-amber-700/50">(anchor {intFmt(ytd.comps_line.anchor_rooms)} + post-cutoff {intFmt(ytd.comps_line.post_cutoff_rooms)})</span></td>
                  <td className={bTdN}>—</td>
                  <td className={bTdN}>—</td>
                  <td className={bTdN}>{intFmt(ytd.comps_line.stay_rooms)}</td>
                  <td className={bTdN}>—</td>
                  <td className={`${bTdN} ${valueColor(ytd.comps_line.revenue)}`}>${money(ytd.comps_line.revenue)}</td>
                  <td className={bTdN}>—</td>
                  <td className={bTdN}>{intFmt(ytd.comps_line.stay_persons)}</td>
                  <td className={bTdN}>—</td>
                </tr>
              )}
              {overall && (
                <tr className="border-t-2 border-ink/20 bg-[#fcfcfb] font-bold">
                  <td className={bTd}>TOTAL (occupied = Net + Comps)</td>
                  <td className={bTdN}>{intFmt(rows.reduce((a, c) => a + c.units, 0))}</td>
                  <td className={bTdN}>{intFmt(overall.physical_rooms)}</td>
                  <td className={bTdN}>{intFmt(overall.stay_rooms)}</td>
                  <td className={bTdN}>{(overall.occupancy_pct * 100).toFixed(1)}%</td>
                  <td className={`${bTdN} ${valueColor(overall.revenue)}`}>${money(overall.revenue)}</td>
                  <td className={`${bTdN} ${valueColor(overall.adr)}`}>${money(overall.adr)}</td>
                  <td className={bTdN}>{intFmt(overall.stay_persons)}</td>
                  <td className={bTdN}>100.0%</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function emptyRow(cols: Col[]): Record<string, string> {
  return Object.fromEntries(cols.map((c) => [c.key, ""]));
}

// ---- Tab 6.10 Weekly Calendar ----------------------------------------------
// Rangos semanales EDITABLES (fecha inicio/fin) que alimentan Tab 4 (Weekly
// Revenue). El label se deriva SOLO de num+fechas (no se escribe a mano) y se
// muestra en vivo mientras se edita. dim_calendar (por día) es otra tabla, no
// se toca acá.
type WeekRow = { id: string; week_num: string; week_start: string; week_end: string; week_label: string };

const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Espeja engine/week_calendar.py::build_label (Python %d-%b-%Y) para el preview.
function fmtWeekLabel(weekNum: string, startIso: string, endIso: string): string {
  const fmt = (iso: string) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) return iso || "—";
    return `${m[3]}-${MONTHS_EN[parseInt(m[2], 10) - 1]}-${m[1]}`;
  };
  const w = String(weekNum).padStart(2, "0");
  return `W${w} | ${fmt(startIso)} to ${fmt(endIso)}`;
}

function WeekCalendarPanel() {
  const [rows, setRows] = useState<WeekRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ week_start: string; week_end: string }>({ week_start: "", week_end: "" });
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API_URL}/master-data/week-calendar`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      setRows(await res.json());
    } catch {
      setError("No se pudo cargar el calendario semanal.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function startEdit(r: WeekRow) {
    setEditing(r.id);
    setDraft({ week_start: r.week_start, week_end: r.week_end });
    setMsg(""); setError("");
  }

  async function save(r: WeekRow) {
    if (draft.week_end < draft.week_start) { setError("La fecha de fin no puede ser anterior a la de inicio."); return; }
    setSaving(true); setError("");
    try {
      const res = await fetch(`${API_URL}/master-data/week-calendar/${r.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: draft.week_start, week_end: draft.week_end }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setEditing(null);
      setMsg(`Semana ${r.week_num} actualizada. Tab 4 usará el nuevo rango.`);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function recalculate() {
    if (!confirm(
      "Recalcular regenera TODAS las semanas al corte estándar Viernes→Jueves (2025-2027).\n\n" +
      "Cualquier ajuste manual de rango se PERDERÁ.\n\n¿Continuar?"
    )) return;
    setRecalculating(true); setMsg(""); setError("");
    try {
      const res = await fetch(`${API_URL}/master-data/week-calendar/recalculate`, { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setEditing(null);
      setMsg(`Recalculado: ${body.count} semanas al corte estándar.`);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRecalculating(false);
    }
  }

  const th = "px-2 py-1.5 text-left font-medium text-ink/70 whitespace-nowrap";
  const td = "px-2 py-1 text-ink/85";
  const inp = "w-full min-w-[130px] rounded border border-ink/12 bg-[#f9f9f7] px-1.5 py-1 text-ink";

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-ink/60">
        Rangos semanales que usa <span className="text-ink/75">Tab 4 · Weekly Revenue</span> (resuelve la semana
        de una fecha por rango: inicio ≤ fecha ≤ fin). Editá la <span className="text-ink/75">fecha de inicio y
        de fin</span> de una semana para generarla con un rango distinto — el reporte se sincroniza solo. El{" "}
        <span className="text-ink/75">Label</span> se recalcula automáticamente. <span className="text-amber-700">
        Recalcular</span> regenera todo al corte estándar Viernes→Jueves. (No afecta el calendario por día
        <span className="text-ink/60"> dim_calendar</span>, que es una tabla aparte.)
      </p>

      <div className="flex items-center justify-between">
        <span className="text-xs text-ink/60">{rows.length} semanas</span>
        <button onClick={recalculate} disabled={recalculating}
          className="rounded bg-ink/5 px-3 py-1.5 text-xs font-medium text-ink/75 hover:text-ink disabled:opacity-50">
          {recalculating ? "Recalculando…" : "🔄 Recalcular (estándar Vie→Jue)"}
        </button>
      </div>

      {error && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">{error}</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}
      {loading && <div className="text-xs text-ink/60">Cargando…</div>}

      <div className="overflow-x-auto rounded-lg border border-ink/10">
        <table className="w-full text-sm">
          <thead className="bg-[#fcfcfb]">
            <tr>
              <th className={th}>Week #</th>
              <th className={th}>Week Start (Vie)</th>
              <th className={th}>Week End (Jue)</th>
              <th className={th}>Label (automático)</th>
              <th className={th}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isEd = editing === r.id;
              const livePreview = isEd ? fmtWeekLabel(r.week_num, draft.week_start, draft.week_end) : r.week_label;
              return (
                <tr key={r.id} className={`border-t border-ink/8 ${isEd ? "bg-accent/5" : ""}`}>
                  <td className={`${td} font-medium`}>{r.week_num}</td>
                  <td className={td}>
                    {isEd ? (
                      <input type="date" value={draft.week_start}
                        onChange={(e) => setDraft({ ...draft, week_start: e.target.value })} className={inp} />
                    ) : r.week_start}
                  </td>
                  <td className={td}>
                    {isEd ? (
                      <input type="date" value={draft.week_end}
                        onChange={(e) => setDraft({ ...draft, week_end: e.target.value })} className={inp} />
                    ) : r.week_end}
                  </td>
                  <td className={`${td} ${isEd ? "text-amber-700" : "text-ink/70"}`}>{livePreview}</td>
                  <td className={td}>
                    {isEd ? (
                      <div className="flex gap-1">
                        <button onClick={() => save(r)} disabled={saving}
                          className="rounded bg-accent px-2 py-1 text-[11px] text-white disabled:opacity-50">Guardar</button>
                        <button onClick={() => setEditing(null)}
                          className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75">✕</button>
                      </div>
                    ) : (
                      <button onClick={() => startEdit(r)}
                        className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:text-ink">Editar</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableTable({ cols, endpoint }: { cols: Col[]; endpoint: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null); // id of the row being edited, "new" for create
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API_URL}${endpoint}`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      setRows(await res.json());
    } catch {
      setError("Could not load.");
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => { load(); }, [load]);

  function startEdit(row: Row) {
    setEditing(row.id);
    setDraft(Object.fromEntries(cols.map((c) => [c.key, row[c.key] ?? ""])));
    setError("");
  }

  function startCreate() {
    setEditing("new");
    setDraft(emptyRow(cols));
    setError("");
  }

  function cancel() {
    setEditing(null);
    setError("");
  }

  async function save() {
    const missing = cols.find((c) => c.required && !draft[c.key]?.trim());
    if (missing) { setError(`${missing.label} is required.`); return; }
    setSaving(true); setError("");
    try {
      const isNew = editing === "new";
      const res = await fetch(`${API_URL}${endpoint}${isNew ? "" : `/${editing}`}`, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setEditing(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this row?")) return;
    try {
      const res = await fetch(`${API_URL}${endpoint}/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(String(res.status));
      await load();
    } catch {
      setError("Could not delete.");
    }
  }

  const th = "px-2 py-1.5 text-left font-medium text-ink/70 whitespace-nowrap";
  const td = "px-2 py-1 text-ink/85";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-ink/60">{rows.length} row{rows.length === 1 ? "" : "s"}</span>
        {editing !== "new" && (
          <button onClick={startCreate} className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white">
            + Add
          </button>
        )}
      </div>

      {error && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">{error}</div>}
      {loading && <div className="text-xs text-ink/60">Loading…</div>}

      <div className="overflow-x-auto rounded-lg border border-ink/10">
        <table className="w-full text-sm">
          <thead className="bg-[#fcfcfb]">
            <tr>
              {cols.map((c) => <th key={c.key} className={th}>{c.label}</th>)}
              <th className={th}></th>
            </tr>
          </thead>
          <tbody>
            {editing === "new" && (
              <tr className="border-t border-ink/8 bg-accent/5">
                {cols.map((c) => (
                  <td key={c.key} className={td}>
                    <input value={draft[c.key] ?? ""} onChange={(e) => setDraft({ ...draft, [c.key]: e.target.value })}
                      className="w-full min-w-[80px] rounded border border-ink/12 bg-[#f9f9f7] px-1.5 py-1 text-ink" />
                  </td>
                ))}
                <td className={td}>
                  <div className="flex gap-1">
                    <button onClick={save} disabled={saving} className="rounded bg-accent px-2 py-1 text-[11px] text-white disabled:opacity-50">Save</button>
                    <button onClick={cancel} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75">✕</button>
                  </div>
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-ink/8">
                {cols.map((c) => (
                  <td key={c.key} className={td}>
                    {editing === r.id ? (
                      <input value={draft[c.key] ?? ""} onChange={(e) => setDraft({ ...draft, [c.key]: e.target.value })}
                        className="w-full min-w-[80px] rounded border border-ink/12 bg-[#f9f9f7] px-1.5 py-1 text-ink" />
                    ) : (
                      r[c.key] ?? <span className="text-ink/45">—</span>
                    )}
                  </td>
                ))}
                <td className={td}>
                  {editing === r.id ? (
                    <div className="flex gap-1">
                      <button onClick={save} disabled={saving} className="rounded bg-accent px-2 py-1 text-[11px] text-white disabled:opacity-50">Save</button>
                      <button onClick={cancel} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75">✕</button>
                    </div>
                  ) : (
                    <div className="flex gap-1">
                      <button onClick={() => startEdit(r)} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:text-ink">Edit</button>
                      <button onClick={() => remove(r.id)} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:text-red-600">Delete</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type Param = {
  key: string; label: string; group: string; affects: string; help: string;
  type: string; default: string; value: string; is_default: boolean;
};

// 6.9 — parámetros del sistema editables sin re-deploy (config_service /
// app_config). Resuelve el riesgo de que un nombre de cuenta de Integrity
// hardcodeado se rompa en silencio si Bismark lo renombra.
function ParamsPanel() {
  const [params, setParams] = useState<Param[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/master-data/params`, { cache: "no-store" });
      const data: Param[] = res.ok ? await res.json() : [];
      setParams(data);
      setDraft(Object.fromEntries(data.map((p) => [p.key, p.value])));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function save(key: string) {
    setMsg("");
    const res = await fetch(`${API_URL}/master-data/params/${key}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: draft[key] ?? "" }),
    });
    if (res.ok) {
      setMsg(`✓ ${key} guardado`);
      await load();
    } else {
      const b = await res.json().catch(() => ({}));
      setMsg(`Error: ${b.detail || res.status}`);
    }
  }

  async function reset(key: string) {
    setMsg("");
    const res = await fetch(`${API_URL}/master-data/params/${key}`, { method: "DELETE" });
    if (res.ok) {
      setMsg(`✓ ${key} restaurado al valor por defecto`);
      await load();
    } else {
      setMsg(`Error al restaurar ${key}`);
    }
  }

  const groups = [...new Set(params.map((p) => p.group))];

  return (
    <div className="max-w-3xl space-y-6">
      <div className="rounded-lg border border-ink/10 bg-[#fcfcfb]/40 p-3 text-xs text-ink/70">
        Parámetros del sistema, editables sin re-deploy. Los{" "}
        <b className="text-ink/85">nombres de cuenta</b> deben coincidir EXACTO con Integrity —
        si se renombra una cuenta allá, corregila aquí y el reporte vuelve a encontrarla.
        <b className="text-ink/85"> Restaurar</b> vuelve al valor de fábrica.
      </div>
      {msg && (
        <div className={msg.startsWith("✓") ? "text-xs text-emerald-600" : "text-xs text-rose-600"}>{msg}</div>
      )}
      {groups.map((g) => (
        <div key={g} className="space-y-2">
          <h3 className="text-sm font-semibold text-ink/85">{g}</h3>
          {params.filter((p) => p.group === g).map((p) => {
            const dirty = (draft[p.key] ?? "") !== p.value;
            return (
              <div key={p.key} className="rounded-lg border border-ink/10 bg-[#fcfcfb]/40 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-ink/90">{p.label}</span>
                  <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] text-accent">{p.affects}</span>
                  {p.is_default ? (
                    <span className="rounded bg-ink/5 px-1.5 py-0.5 text-[10px] text-ink/60">por defecto</span>
                  ) : (
                    <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-700">personalizado</span>
                  )}
                </div>
                <p className="mt-1 text-[11px] text-ink/60">{p.help}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input
                    value={draft[p.key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [p.key]: e.target.value }))}
                    className="min-w-[20rem] flex-1 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-sm text-ink"
                  />
                  <button
                    onClick={() => save(p.key)}
                    disabled={!dirty}
                    className="rounded bg-accent px-3 py-1 text-xs text-white disabled:opacity-40"
                  >
                    Save
                  </button>
                  {!p.is_default && (
                    <button
                      onClick={() => reset(p.key)}
                      className="rounded bg-ink/5 px-3 py-1 text-xs text-ink/75 hover:bg-ink/8"
                    >
                      Restaurar
                    </button>
                  )}
                </div>
                {p.type !== "text" && (
                  <p className="mt-1 text-[10px] text-ink/45">Numérico · default: {p.default}</p>
                )}
              </div>
            );
          })}
        </div>
      ))}
      {loading && <p className="text-xs text-ink/60">Cargando…</p>}
    </div>
  );
}

export default function MasterDataPage() {
  const { subtabs: SUBTABS, tab, setTab } = useSubtabs(ALL_SUBTABS, "6.2");

  return (
    <section id="tab6-export" className="w-[calc(100vw-1.5rem)] -translate-x-1/2 relative left-1/2 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">Tab 6 · Master Data</h1>
          <p className="text-xs text-ink/60">Editable catalogs per property (COWLCR).</p>
        </div>
        <ExcelButton target="tab6-export" filename={`Tab6_Master_Data_${tab}`}
          title={`Tab 6 · Master Data — ${tab}`} subtitle="Corcovado Wilderness Lodge" label="Excel" />
      </div>

      <nav className="flex flex-wrap gap-1 border-b border-ink/10 pb-2">
        {SUBTABS.map((s) => (
          <button key={s.id} onClick={() => setTab(s.id)}
            className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
            {s.label}
          </button>
        ))}
      </nav>

      {tab === "6.1" && <YearBudget />}
      {tab === "6.1.1" && <YearBudget kind="forecast" />}
      {tab === "6.2" && <EditableTable cols={PAYMENT_MAP_COLS} endpoint="/master-data/payment-map" />}
      {tab === "6.3" && <EditableTable cols={DEPARTMENT_COLS} endpoint="/master-data/departments" />}
      {tab === "6.7" && <EditableTable cols={ROOM_CATEGORY_COLS} endpoint="/master-data/room-categories" />}
      {tab === "6.8" && <EditableTable cols={MARKET_CODE_COLS} endpoint="/master-data/market-codes" />}
      {tab === "6.4" && <RevenueActualDaily />}
      {tab === "6.5" && <DailyBudget />}
      {tab === "6.6" && <RoomStatsYtd />}
      {tab === "6.9" && <ParamsPanel />}
      {tab === "6.10" && <WeekCalendarPanel />}
    </section>
  );
}
