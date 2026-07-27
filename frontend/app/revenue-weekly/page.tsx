"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";
import RoomStatsTable, { RoomCategory, RoomCategoryOverall, RoomCategoryComps } from "@/components/RoomStatsTable";

type Center = {
  center: string;
  weekly_actual: number; weekly_budget: number; weekly_var: number;
  ytd_actual: number; ytd_budget: number; ytd_var: number;
};
type TableRow = {
  center: string; indent?: boolean; unit?: "count" | "percent" | "currency";
  weekly_actual: number; weekly_budget: number; weekly_var: number; weekly_var_pct: number;
  ytd_actual: number; ytd_budget: number; ytd_var: number; ytd_var_pct: number;
};
type FbSplit = { food: number; beverage: number; misc: number };
type Stats = {
  rn: number; pax: number; available_rooms: number; adr: number; occupancy_pct: number;
  adr_budget: number; occupancy_budget: number;
};
type Report = {
  business_date: string;
  week: { iso_week: number; week_start: string; week_end: string; label: string };
  days_loaded_week: number; days_loaded_ytd: number; budget_status: string;
  centers: Center[];
  table_rows: TableRow[];
  grand_total: { weekly_actual: number; weekly_budget: number; ytd_actual: number; ytd_budget: number };
  fb_detail: { weekly: FbSplit; ytd: FbSplit };
  otros_total: { weekly: number; ytd: number };
  stats: { weekly: Stats; ytd: Stats };
  room_categories: RoomCategory[];
  room_categories_overall: RoomCategoryOverall;
  room_categories_comps: RoomCategoryComps;
  room_categories_reconciled: RoomCategoryOverall;
  room_categories_ytd: RoomCategory[];
  room_categories_ytd_overall: RoomCategoryOverall;
  room_categories_ytd_comps: RoomCategoryComps;
  room_categories_ytd_net: RoomCategoryOverall;
};

const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const moneyAbs = (v: number) => Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 0 });

const th = "px-3 py-2.5 text-left font-bold text-white/70";
const thN = "px-3 py-2.5 text-right font-bold text-white/70";
const td = "px-3 py-1.5 text-white/80";
const tdN = "px-3 py-1.5 text-right tabular-nums text-white/80";
const pct = (v: number) => `${v < 0 ? "(" : ""}${(Math.abs(v) * 100).toFixed(2)}%${v < 0 ? ")" : ""}`;
// Date with the month spelled out (e.g. "July 1, 2026") -- same convention as Tab 3.
const fmtDate = (iso: string) => {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
};
const varColor = (v: number) => (v < 0 ? "!text-rose-400" : v > 0 ? "!text-emerald-400" : "");
const valueColor = (v: number) => (v < 0 ? "!text-rose-400" : "");
const fmtRow = (v: number, unit?: TableRow["unit"]) =>
  unit === "count" ? `${v < 0 ? "(" : ""}${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}${v < 0 ? ")" : ""}`
    : unit === "percent" ? pct(v)
    : `${v < 0 ? "($" : "$"}${moneyAbs(v)}${v < 0 ? ")" : ""}`;

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function Kpi({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-[#1E2130] p-4">
      <div className={`text-2xl font-bold ${tone || "text-white"}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-white/50">{label}</div>
    </div>
  );
}

export default function RevenueWeeklyPage() {
  const globalDay = useBusinessDate();
  const [anchor, setAnchor] = useState(globalDay);
  const [data, setData] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  // The week is picked/edited right here (independent from the day selector
  // up top) -- ‹ Previous week / Next week › + direct date entry.
  useEffect(() => { setAnchor(globalDay); }, [globalDay]);

  const load = useCallback(async () => {
    // Clear `data` here (not just on error) -- same bug as Tab 3: without
    // this, while the new week loads it kept showing the full OLD week
    // underneath the "Loading…".
    setLoading(true); setMsg(""); setData(null);
    try {
      const res = await fetch(`${API_URL}/revenue/weekly/${anchor}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch {
      setData(null); setMsg(`No weekly revenue for ${anchor}. Run ingestion in Tab 1 / Tab 2.`);
    } finally { setLoading(false); }
  }, [anchor]);

  useEffect(() => { load(); }, [load]);

  return (
    <section className="space-y-5">
      {/* Print header -- only visible when printing (Ctrl+P), same convention as Tab 3 */}
      {data && (
        <div className="print-header-block hidden print:flex print:flex-col print:items-center print:border-b print:border-gray-300">
          <div className="print-subtitle uppercase tracking-wide text-gray-500">Corcovado Wilderness Lodge</div>
          <div className="print-title font-bold">Weekly Revenue Report</div>
          <div className="print-date font-extrabold tracking-tight">{fmtDate(data.week.week_start)} – {fmtDate(data.week.week_end)}</div>
        </div>
      )}

      <div className="border-b border-white/10 pb-4 text-center print:hidden">
        <div className="flex items-center justify-center gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-white">Weekly Revenue Report</h1>
          {data && (
            <button onClick={() => window.print()}
              className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/20 hover:text-white">
              🖨️ Print
            </button>
          )}
        </div>
        <p className="mt-1 text-sm text-white/50">
          Corcovado Wilderness Lodge · Mon–Sun Weeks · Actual vs Budget vs Variance
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3 print:hidden">
        <button onClick={() => setAnchor((a) => shiftDate(a, -7))}
          className="rounded-lg border border-white/10 bg-[#1E2130] px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white">
          ‹ Previous week
        </button>
        <input type="date" value={anchor} onChange={(e) => setAnchor(e.target.value)}
          className="rounded-lg border border-white/15 bg-[#0F1118] px-3 py-2 text-sm text-white" />
        <button onClick={() => setAnchor((a) => shiftDate(a, 7))}
          className="rounded-lg border border-white/10 bg-[#1E2130] px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white">
          Next week ›
        </button>
      </div>

      {loading && <div className="text-center text-sm text-white/50">Loading…</div>}
      {msg && <div className="rounded border border-white/10 bg-[#1E2130] p-3 text-center text-sm text-white/70">{msg}</div>}

      {data && (
        <>
          <div className="rounded-xl border border-white/10 bg-gradient-to-br from-[#1E2130] to-[#171926] p-5 shadow-lg">
            <div className="grid grid-cols-4 gap-4 text-center text-sm">
              <div><div className="print-kpi-label text-[11px] font-bold uppercase tracking-wide text-white/40">Week</div><div className="mt-1 text-lg font-bold text-emerald-400">W{data.week.iso_week}</div></div>
              <div><div className="print-kpi-label text-[11px] font-bold uppercase tracking-wide text-white/40">Start</div><div className="mt-1 text-lg font-bold text-white">{data.week.week_start}</div></div>
              <div><div className="print-kpi-label text-[11px] font-bold uppercase tracking-wide text-white/40">End</div><div className="mt-1 text-lg font-bold text-white">{data.week.week_end}</div></div>
              <div><div className="print-kpi-label text-[11px] font-bold uppercase tracking-wide text-white/40">Days loaded</div><div className="mt-1 text-lg font-bold text-white">{data.days_loaded_week} wk / {data.days_loaded_ytd} YTD</div></div>
            </div>
            <div className="mt-3 text-center text-xs text-white/40">{data.week.label}</div>
          </div>

          <div className="print:hidden rounded-lg border border-sky-500/20 bg-sky-500/5 px-4 py-2.5 text-center text-[11px] text-sky-200/80">
            Budget: {data.budget_status} Partial YTD: only sums the days actually
            loaded since Jan 1 -- it never fabricates data.
          </div>

          <div className="overflow-hidden rounded-xl border border-white/10 shadow-lg">
          <table className="w-full text-xs">
            <thead className="bg-gradient-to-r from-[#1a2744] to-[#1E2130]">
              <tr>
                <th className={th}>Metric / Department</th>
                <th className={`${thN} border-l-2 border-white/40`}>Weekly Actual</th>
                <th className={thN}>Weekly Budget</th>
                <th className={thN}>Var $</th>
                <th className={thN}>Var %</th>
                <th className={`${thN} border-l-2 border-white/40`}>YTD Actual</th>
                <th className={thN}>YTD Budget</th>
                <th className={thN}>YTD Var $</th>
                <th className={thN}>YTD Var %</th>
              </tr>
            </thead>
            <tbody>
              {data.table_rows.map((r, i) => {
                const isTotal = r.center === "Total Daily Rev. Weekly";
                const isFirstStat = r.center === "Rooms Sold (RN)";
                return (
                  <tr key={`${r.center}-${i}`}
                    className={`border-t ${isTotal ? "border-t-2 border-emerald-500/40 bg-emerald-500/10 font-bold" : i % 2 === 0 ? "border-white/5 bg-white/[0.015]" : "border-white/5"} ${isFirstStat ? "border-t-2 border-white/20" : ""}`}>
                    <td className={`${td} ${r.indent ? "pl-8 text-white/60" : ""}`}>
                      {isTotal || r.indent || r.unit ? r.center : `Revenue – ${r.center}`}
                    </td>
                    <td className={`${tdN} border-l-2 border-white/40 ${valueColor(r.weekly_actual)}`}>{fmtRow(r.weekly_actual, r.unit)}</td>
                    <td className={`${tdN} ${r.weekly_budget < 0 ? "text-rose-400" : "text-white/40"}`}>{fmtRow(r.weekly_budget, r.unit)}</td>
                    <td className={`${tdN} ${varColor(r.weekly_var)}`}>{fmtRow(r.weekly_var, r.unit === "count" ? "count" : r.unit === "percent" ? "percent" : "currency")}</td>
                    <td className={`${tdN} ${varColor(r.weekly_var_pct)}`}>{pct(r.weekly_var_pct)}</td>
                    <td className={`${tdN} border-l-2 border-white/40 ${valueColor(r.ytd_actual)}`}>{fmtRow(r.ytd_actual, r.unit)}</td>
                    <td className={`${tdN} ${r.ytd_budget < 0 ? "text-rose-400" : "text-white/40"}`}>{fmtRow(r.ytd_budget, r.unit)}</td>
                    <td className={`${tdN} ${varColor(r.ytd_var)}`}>{fmtRow(r.ytd_var, r.unit === "count" ? "count" : r.unit === "percent" ? "percent" : "currency")}</td>
                    <td className={`${tdN} ${varColor(r.ytd_var_pct)}`}>{pct(r.ytd_var_pct)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>

          <div className="print-page-break">
            <div className="print-table-title mb-1 text-[11px] font-bold uppercase tracking-wide text-white/50">Room Statistics by Category (§5.2, ADR/Occ — weekly, revenue rooms only)</div>
            <RoomStatsTable rows={data.room_categories} overall={data.room_categories_overall}
              comps={data.room_categories_comps} reconciled={data.room_categories_reconciled} />
          </div>

          <div>
            <div className="print-table-title mb-1 text-[11px] font-bold uppercase tracking-wide text-white/50">Rooms Statistics YTD by Category (Tab 6.6 — NET + Comps/In-House = TOTAL occupied)</div>
            <RoomStatsTable rows={data.room_categories_ytd} overall={data.room_categories_ytd_overall}
              comps={data.room_categories_ytd_comps} net={data.room_categories_ytd_net} />
          </div>

          {(data.otros_total.weekly !== 0 || data.otros_total.ytd !== 0) && (
            <div className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
              ⚠ There are accounts outside the canonical map (Other): weekly{" "}
              <span className={valueColor(data.otros_total.weekly)}>${money(data.otros_total.weekly)}</span>, YTD{" "}
              <span className={valueColor(data.otros_total.ytd)}>${money(data.otros_total.ytd)}</span>.
            </div>
          )}
        </>
      )}
    </section>
  );
}
