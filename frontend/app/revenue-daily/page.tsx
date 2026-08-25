"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";
import RoomStatsTable, { RoomCategory, RoomCategoryOverall, RoomCategoryComps } from "@/components/RoomStatsTable";

type Center = {
  center: string;
  today_actual: number; today_budget: number; today_var: number; today_var_pct: number;
  mtd_actual: number; mtd_budget: number; mtd_var: number; mtd_var_pct: number;
  month_budget_total: number; amount_to_budget: number; monthly_var_pct: number;
  month_forecast_total: number; amount_to_forecast: number; monthly_fcst_var_pct: number;
};
type Otros = { cuenta: string; nombre: string | null; amount: number };
type Report = {
  business_date: string; days_loaded_mtd: number; budget_status: string;
  centers: Center[];
  grand_total: {
    today_actual: number; today_budget: number; today_var_pct: number;
    mtd_actual: number; mtd_budget: number; mtd_var_pct: number;
    month_budget_total: number; amount_to_budget: number; monthly_var_pct: number;
    month_forecast_total: number; amount_to_forecast: number; monthly_fcst_var_pct: number;
  };
  fb_detail: { today: FbSplit; mtd: FbSplit };
  otros: Otros[];
  kpis: {
    pax: number; rooms_occupied: number; available_rooms: number; adr: number; occupancy_pct: number;
    mtd_rooms_occupied: number; mtd_pax: number; mtd_adr: number; mtd_occupancy_pct: number;
    adr_budget: number; occupancy_budget: number;
  };
  room_categories: RoomCategory[];
  room_categories_overall: RoomCategoryOverall;
  room_categories_comps: RoomCategoryComps;
  room_categories_reconciled: RoomCategoryOverall;
  room_categories_mtd: RoomCategory[];
  room_categories_mtd_overall: RoomCategoryOverall;
  room_categories_mtd_comps: RoomCategoryComps;
  room_categories_mtd_reconciled: RoomCategoryOverall;
  on_property_production: { rows: Center[]; total: Center };
};
type FbSplit = { food: number; beverage: number; misc: number };

const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Integer for pax / rooms / room-nights (no decimals)
const num = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { maximumFractionDigits: 0 });

const th = "px-3 py-2 text-left font-bold text-ink/70";
const thN = "px-3 py-2 text-right font-bold text-ink/70";
// Group headers (TODAY / MONTH TO DAY / FULL MONTH RESULT, colSpan), centered
const thC = "px-3 py-2 text-center font-bold text-ink/70";
const td = "px-3 py-1.5 text-ink/85";
const tdN = "px-3 py-1.5 text-right tabular-nums text-ink/85";
const pct = (v: number) => `${(v * 100).toFixed(2)}%`;
// Date with the month spelled out (e.g. "July 1, 2026") for the header --
// instead of the raw ISO "2026-07-01", which doesn't look professional in a printed report.
const fmtDate = (iso: string) => {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
};
const varColor = (v: number) => (v < 0 ? "!text-red-600" : v > 0 ? "!text-emerald-600" : "");
// For counts (pax/rooms) that can be negative (e.g. diffs) but have no "positive=green" semantics
const countColor = (v: number) => (v < 0 ? "!text-red-600" : "");

function Kpi({ label, value, tone, small }: { label: string; value: number | string; tone?: string; small?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-ink/10 bg-[#fcfcfb] p-4 text-center">
      <div className={`${small ? "text-lg" : "text-2xl"} whitespace-nowrap font-bold ${tone || "text-ink"}`}>{value}</div>
      <div className="print-kpi-label text-[11px] font-bold uppercase tracking-wide text-ink/60">{label}</div>
    </div>
  );
}

const SUBTABS = [
  { id: "3", label: "3 Summary" },
  { id: "3.1", label: "3.1 Opera Daily vs History" },
  { id: "3.2", label: "3.2 Market Segment / COM" },
];

export default function RevenueDailyPage() {
  const day = useBusinessDate();
  const [tab, setTab] = useState("3");
  const [data, setData] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    // Clear `data` here (not just on error) -- otherwise, while the new day
    // loads it kept showing the full report of the OLD day underneath the
    // "Loading…", with the header already showing the new date: it looked
    // like Today/MTD didn't match (§ reported by the user, in reality it
    // was two different days mixed together on screen).
    // Lee SIEMPRE el día más fresco del selector global (localStorage) -- así el
    // botón "Recalcular" jala el día correcto aunque el estado reactivo se haya
    // quedado atrás por lentitud/carrera (§ reportado por el owner: a veces se
    // veía la foto del día default con el picker en otro día).
    const d = (typeof window !== "undefined" && localStorage.getItem("dailyops.business_date")) || day;
    setLoading(true); setMsg(""); setData(null);
    try {
      const res = await fetch(`${API_URL}/revenue/${d}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch {
      setData(null); setMsg(`No revenue data for ${d}. Run ingestion in Tab 1 / Tab 2.`);
    } finally { setLoading(false); }
  }, [day]);

  useEffect(() => { load(); }, [load]);

  return (
    <section className="space-y-4">
      {/* Print header -- only visible when printing (Ctrl+P), large and centered date */}
      <div className="print-header-block hidden print:flex print:flex-col print:items-center print:border-b print:border-ink/15">
        <div className="print-subtitle uppercase tracking-wide text-ink/60">Corcovado Wilderness Lodge</div>
        <div className="print-title font-bold">Daily Revenue Report</div>
        <div className="print-date font-extrabold tracking-tight">{fmtDate(data?.business_date ?? day)}</div>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-ink">Tab 3 · Daily Revenue Report</h1>
          <p className="text-xs text-ink/60">
            12 canonical centers (§5.1) · Actual vs Budget vs Variance · {fmtDate(data?.business_date ?? day)}
            {data && ` · ${data.days_loaded_mtd} day(s) loaded in MTD`}
          </p>
        </div>
        {tab === "3" && (
          <div className="flex items-center gap-2">
            <button onClick={() => load()} disabled={loading}
              title="Vuelve a jalar los datos del día seleccionado (por si tardó en actualizar)"
              className="rounded-lg bg-ink/5 px-3 py-1.5 text-xs font-medium text-ink/85 hover:bg-ink/8 hover:text-ink disabled:opacity-50">
              {loading ? "Recalculando…" : "🔄 Recalcular"}
            </button>
            {data && (
              <button onClick={() => window.print()}
                className="rounded-lg bg-ink/5 px-3 py-1.5 text-xs font-medium text-ink/85 hover:bg-ink/8 hover:text-ink">
                🖨️ Print
              </button>
            )}
          </div>
        )}
      </div>

      <nav className="flex flex-wrap gap-1 border-b border-ink/10 pb-2 print:hidden">
        {SUBTABS.map((s) => (
          <button key={s.id} onClick={() => setTab(s.id)}
            className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
            {s.label}
          </button>
        ))}
      </nav>

      {tab === "3.1" && <OperaValidation day={day} />}
      {tab === "3.2" && <MarketSegment day={day} />}

      {tab === "3" && (
      <>
      {loading && <div className="text-sm text-ink/60">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-3 text-sm text-ink/75">{msg}</div>}

      {data && (
        <>
          <div className="">
            <div className="mb-2 print-section-title text-center text-lg font-bold uppercase tracking-wide text-ink/85">Today</div>
            <div className="grid grid-cols-4 gap-3">
              <Kpi label="Total Pax" value={num(data.kpis.pax)} tone="text-sky-600" />
              <Kpi label="Rooms Occupied" value={num(data.kpis.rooms_occupied)} tone="text-emerald-600" />
              <Kpi label="ADR (Actual / Budget)" value={`$${money(data.kpis.adr)} / $${money(data.kpis.adr_budget)}`} small />
              <Kpi label="Occupancy % (Actual / Budget)"
                value={`${(data.kpis.occupancy_pct * 100).toFixed(1)}% / ${(data.kpis.occupancy_budget * 100).toFixed(1)}%`} />
            </div>
          </div>
          <div className="">
            <div className="mb-2 print-section-title text-center text-lg font-bold uppercase tracking-wide text-ink/85">Month to Day</div>
            <div className="grid grid-cols-4 gap-3">
              <Kpi label="Total Pax MTD" value={num(data.kpis.mtd_pax)} tone="text-sky-600" />
              <Kpi label="Rooms Occupied MTD" value={num(data.kpis.mtd_rooms_occupied)} tone="text-emerald-600" />
              <Kpi label="ADR MTD (Actual / Budget)" value={`$${money(data.kpis.mtd_adr)} / $${money(data.kpis.adr_budget)}`} small />
              <Kpi label="Occupancy % MTD (Actual / Budget)"
                value={`${(data.kpis.mtd_occupancy_pct * 100).toFixed(1)}% / ${(data.kpis.occupancy_budget * 100).toFixed(1)}%`} />
            </div>
          </div>

          <div className="print:hidden rounded border border-ink/10 bg-[#fcfcfb] px-3 py-2 text-[11px] text-ink/70">
            Budget: {data.budget_status}
          </div>

          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]">
              <tr>
                <th className={th} rowSpan={2}>Revenue Center</th>
                <th className={`${thC} border-l-2 border-ink/25`} colSpan={4}>TODAY</th>
                <th className={`${thC} border-l-2 border-ink/25`} colSpan={4}>MONTH TO DAY</th>
                <th className={`${thC} border-l-2 border-ink/25`} colSpan={6}>FULL MONTH RESULT</th>
              </tr>
              <tr>
                <th className={`${thN} border-l-2 border-ink/25`}>Actual</th>
                <th className={thN}>Budget</th>
                <th className={thN}>Var $</th>
                <th className={thN}>Var %</th>
                <th className={`${thN} border-l-2 border-ink/25`}>Actual</th>
                <th className={thN}>Budget</th>
                <th className={thN}>Var $</th>
                <th className={thN}>Var %</th>
                <th className={`${thN} border-l-2 border-ink/25`}>Monthly Budget</th>
                <th className={thN}>Amount to Budget</th>
                <th className={thN}>Var %</th>
                <th className={`${thN} border-l-2 border-ink/25`}>Monthly Forecast</th>
                <th className={thN}>Amount to Forecast</th>
                <th className={thN}>Var %</th>
              </tr>
            </thead>
            <tbody>
              {data.centers.map((c) => (
                <tr key={c.center} className="border-t border-ink/8">
                  <td className={td}>{c.center}</td>
                  <td className={`${tdN} border-l-2 border-ink/25`}>${money(c.today_actual)}</td>
                  <td className={`${tdN} text-ink/60`}>${money(c.today_budget)}</td>
                  <td className={`${tdN} ${varColor(c.today_var)}`}>${money(c.today_var)}</td>
                  <td className={`${tdN} ${varColor(c.today_var_pct)}`}>{pct(c.today_var_pct)}</td>
                  <td className={`${tdN} border-l-2 border-ink/25`}>${money(c.mtd_actual)}</td>
                  <td className={`${tdN} text-ink/60`}>${money(c.mtd_budget)}</td>
                  <td className={`${tdN} ${varColor(c.mtd_var)}`}>${money(c.mtd_var)}</td>
                  <td className={`${tdN} ${varColor(c.mtd_var_pct)}`}>{pct(c.mtd_var_pct)}</td>
                  <td className={`${tdN} border-l-2 border-ink/25 text-ink/60`}>${money(c.month_budget_total)}</td>
                  <td className={`${tdN} ${varColor(c.amount_to_budget)}`}>${money(c.amount_to_budget)}</td>
                  <td className={`${tdN} ${varColor(c.monthly_var_pct)}`}>{pct(c.monthly_var_pct)}</td>
                  <td className={`${tdN} border-l-2 border-ink/25 text-ink/60`}>${money(c.month_forecast_total)}</td>
                  <td className={`${tdN} ${varColor(c.amount_to_forecast)}`}>${money(c.amount_to_forecast)}</td>
                  <td className={`${tdN} ${varColor(c.monthly_fcst_var_pct)}`}>{pct(c.monthly_fcst_var_pct)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={td}>GRAND TOTAL</td>
                <td className={`${tdN} border-l-2 border-ink/25 text-emerald-600`}>${money(data.grand_total.today_actual)}</td>
                <td className={`${tdN} text-ink/60`}>${money(data.grand_total.today_budget)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.today_actual - data.grand_total.today_budget)}`}>${money(data.grand_total.today_actual - data.grand_total.today_budget)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.today_var_pct)}`}>{pct(data.grand_total.today_var_pct)}</td>
                <td className={`${tdN} border-l-2 border-ink/25 text-emerald-600`}>${money(data.grand_total.mtd_actual)}</td>
                <td className={`${tdN} text-ink/60`}>${money(data.grand_total.mtd_budget)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.mtd_actual - data.grand_total.mtd_budget)}`}>${money(data.grand_total.mtd_actual - data.grand_total.mtd_budget)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.mtd_var_pct)}`}>{pct(data.grand_total.mtd_var_pct)}</td>
                <td className={`${tdN} border-l-2 border-ink/25 text-ink/60`}>${money(data.grand_total.month_budget_total)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.amount_to_budget)}`}>${money(data.grand_total.amount_to_budget)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.monthly_var_pct)}`}>{pct(data.grand_total.monthly_var_pct)}</td>
                <td className={`${tdN} border-l-2 border-ink/25 text-ink/60`}>${money(data.grand_total.month_forecast_total)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.amount_to_forecast)}`}>${money(data.grand_total.amount_to_forecast)}</td>
                <td className={`${tdN} ${varColor(data.grand_total.monthly_fcst_var_pct)}`}>{pct(data.grand_total.monthly_fcst_var_pct)}</td>
              </tr>
            </tbody>
          </table>

          <div className="print-page-break">
            <div className="print-table-title mb-1 text-[11px] font-bold uppercase tracking-wide text-ink/60">On-Property Production (Detail Visibility)</div>
            <table className="w-full rounded-lg border border-ink/10 text-xs">
              <thead className="bg-[#fcfcfb]">
                <tr>
                  <th className={th} rowSpan={2}>Revenue Center</th>
                  <th className={`${thC} border-l-2 border-ink/25`} colSpan={4}>TODAY</th>
                  <th className={`${thC} border-l-2 border-ink/25`} colSpan={4}>MONTH TO DAY</th>
                  <th className={`${thC} border-l-2 border-ink/25`} colSpan={3}>FULL MONTH RESULT</th>
                </tr>
                <tr>
                  <th className={`${thN} border-l-2 border-ink/25`}>Actual</th>
                  <th className={thN}>Budget</th>
                  <th className={thN}>Var $</th>
                  <th className={thN}>Var %</th>
                  <th className={`${thN} border-l-2 border-ink/25`}>Actual</th>
                  <th className={thN}>Budget</th>
                  <th className={thN}>Var $</th>
                  <th className={thN}>Var %</th>
                  <th className={`${thN} border-l-2 border-ink/25`}>Monthly Budget</th>
                  <th className={thN}>Amount to Budget</th>
                  <th className={thN}>Var %</th>
                </tr>
              </thead>
              <tbody>
                {data.on_property_production.rows.map((c) => (
                  <tr key={c.center} className="border-t border-ink/8">
                    <td className={td}>{c.center}</td>
                    <td className={`${tdN} border-l-2 border-ink/25`}>${money(c.today_actual)}</td>
                    <td className={`${tdN} text-ink/60`}>${money(c.today_budget)}</td>
                    <td className={`${tdN} ${varColor(c.today_var)}`}>${money(c.today_var)}</td>
                    <td className={`${tdN} ${varColor(c.today_var_pct)}`}>{pct(c.today_var_pct)}</td>
                    <td className={`${tdN} border-l-2 border-ink/25`}>${money(c.mtd_actual)}</td>
                    <td className={`${tdN} text-ink/60`}>${money(c.mtd_budget)}</td>
                    <td className={`${tdN} ${varColor(c.mtd_var)}`}>${money(c.mtd_var)}</td>
                    <td className={`${tdN} ${varColor(c.mtd_var_pct)}`}>{pct(c.mtd_var_pct)}</td>
                    <td className={`${tdN} border-l-2 border-ink/25 text-ink/60`}>${money(c.month_budget_total)}</td>
                    <td className={`${tdN} ${varColor(c.amount_to_budget)}`}>${money(c.amount_to_budget)}</td>
                    <td className={`${tdN} ${varColor(c.monthly_var_pct)}`}>{pct(c.monthly_var_pct)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                  <td className={td}>{data.on_property_production.total.center}</td>
                  <td className={`${tdN} border-l-2 border-ink/25 text-emerald-600`}>${money(data.on_property_production.total.today_actual)}</td>
                  <td className={`${tdN} text-ink/60`}>${money(data.on_property_production.total.today_budget)}</td>
                  <td className={`${tdN} ${varColor(data.on_property_production.total.today_var)}`}>${money(data.on_property_production.total.today_var)}</td>
                  <td className={`${tdN} ${varColor(data.on_property_production.total.today_var_pct)}`}>{pct(data.on_property_production.total.today_var_pct)}</td>
                  <td className={`${tdN} border-l-2 border-ink/25 text-emerald-600`}>${money(data.on_property_production.total.mtd_actual)}</td>
                  <td className={`${tdN} text-ink/60`}>${money(data.on_property_production.total.mtd_budget)}</td>
                  <td className={`${tdN} ${varColor(data.on_property_production.total.mtd_var)}`}>${money(data.on_property_production.total.mtd_var)}</td>
                  <td className={`${tdN} ${varColor(data.on_property_production.total.mtd_var_pct)}`}>{pct(data.on_property_production.total.mtd_var_pct)}</td>
                  <td className={`${tdN} border-l-2 border-ink/25 text-ink/60`}>${money(data.on_property_production.total.month_budget_total)}</td>
                  <td className={`${tdN} ${varColor(data.on_property_production.total.amount_to_budget)}`}>${money(data.on_property_production.total.amount_to_budget)}</td>
                  <td className={`${tdN} ${varColor(data.on_property_production.total.monthly_var_pct)}`}>{pct(data.on_property_production.total.monthly_var_pct)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="">
            <div className="print-table-title mb-1 text-[11px] font-bold uppercase tracking-wide text-ink/60">Room Statistics by Category (§5.2, ADR/Occ — revenue rooms only)</div>
            <RoomStatsTable rows={data.room_categories} overall={data.room_categories_overall}
              comps={data.room_categories_comps} reconciled={data.room_categories_reconciled} />
          </div>

          <div className="">
            <div className="print-table-title mb-1 text-[11px] font-bold uppercase tracking-wide text-ink/60">
              Months to Day Stats — by Room Type (§5.2, month-to-date accumulation)
            </div>
            <RoomStatsTable rows={data.room_categories_mtd} overall={data.room_categories_mtd_overall}
              comps={data.room_categories_mtd_comps} reconciled={data.room_categories_mtd_reconciled} />
            <p className="mt-1 text-[11px] text-ink/60 print:hidden">
              No budget by room type (not needed — rate is controlled via the general
              ADR above, Integrity Room Revenue ÷ Room Statistics). "Codes" (FVR/OVR)
              are in Tab 3.1. This table comes from the real ingestion of Opera's
              `statroomtype` XML (Tab 1/2) — if a day doesn&apos;t have that XML ingested, it won&apos;t show up here (never fabricated).
            </p>
          </div>

          {data.otros.length > 0 && (
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-amber-600">⚠ Accounts outside the canonical map (Other)</div>
              <table className="w-full rounded-lg border border-amber-500/30 text-xs">
                <thead className="bg-[#fcfcfb]"><tr>
                  <th className={th}>Account</th><th className={th}>Name</th><th className={thN}>Amount</th>
                </tr></thead>
                <tbody>
                  {data.otros.map((o, i) => (
                    <tr key={i} className="border-t border-ink/8">
                      <td className="px-3 py-1.5 font-mono text-ink/85">{o.cuenta}</td>
                      <td className={td}>{o.nombre}</td>
                      <td className={`${tdN} ${o.amount < 0 ? "text-red-600" : "text-amber-600"}`}>${money(o.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      </>
      )}
    </section>
  );
}

type OperaValRow = {
  category: string; rn_daily: number; rn_history: number; rn_diff: number;
  pax_daily: number; pax_history: number; pax_diff: number;
  revenue_daily: number; revenue_history: number; revenue_diff: number;
};
type OperaValReport = {
  business_date: string; rows: OperaValRow[];
  totals: { rn_daily: number; rn_history: number; pax_daily: number; pax_history: number };
  revenue: { daily_total: number; history_total: number; diff: number };
  comps?: { rn_daily: number; rn_history: number; pax_daily: number; pax_history: number };
  reconciled?: { rn_daily: number; rn_history: number; pax_daily: number; pax_history: number };
  room_class_mapping: Record<string, string>;
};

function OperaValidation({ day }: { day: string }) {
  const [data, setData] = useState<OperaValReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/revenue/opera-validation/${day}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch {
      setData(null); setMsg(`No occupancy/room-stats data for ${day}.`);
    } finally { setLoading(false); }
  }, [day]);

  useEffect(() => { load(); }, [load]);

  const diffColor = (v: number) => (v === 0 ? "!text-emerald-600" : "!text-red-600");

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink/60">
        Opera Daily (XML STATISTICS, official) vs Opera History (XML statroomtype, for confirmation) —
        cross-check by room type, {day}. Comps &amp; in-house (COM/INHOUSE) excluded; reconciliation line
        below ties back to the full statistics.
      </p>
      {loading && <div className="text-sm text-ink/60">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-3 text-sm text-ink/75">{msg}</div>}
      {data && (
        <>
          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]"><tr>
              <th className={th}>Category</th>
              <th className={`${thN} border-l border-ink/10`}>RN Daily</th>
              <th className={thN}>RN History</th>
              <th className={thN}>Diff RN</th>
              <th className={`${thN} border-l border-ink/10`}>Pax Daily</th>
              <th className={thN}>Pax History</th>
              <th className={thN}>Diff Pax</th>
              <th className={`${thN} border-l border-ink/10`}>Revenue Daily (Integrity)</th>
              <th className={thN}>Revenue History (statroomtype)</th>
              <th className={thN}>Diff Revenue</th>
            </tr></thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.category} className="border-t border-ink/8">
                  <td className={td}>{r.category}</td>
                  <td className={`${tdN} border-l border-ink/10`}>{num(r.rn_daily)}</td>
                  <td className={tdN}>{num(r.rn_history)}</td>
                  <td className={`${tdN} ${diffColor(r.rn_diff)}`}>{num(r.rn_diff)}</td>
                  <td className={`${tdN} border-l border-ink/10`}>{num(r.pax_daily)}</td>
                  <td className={tdN}>{num(r.pax_history)}</td>
                  <td className={`${tdN} ${diffColor(r.pax_diff)}`}>{num(r.pax_diff)}</td>
                  <td className={`${tdN} border-l border-ink/10`}>${money(r.revenue_daily)}</td>
                  <td className={tdN}>${money(r.revenue_history)}</td>
                  <td className={`${tdN} ${diffColor(r.revenue_diff)}`}>${money(r.revenue_diff)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={td}>{data.comps && data.comps.rn_daily + data.comps.rn_history > 0 ? "TOTAL (revenue rooms)" : "TOTAL"}</td>
                <td className={`${tdN} border-l border-ink/10`}>{num(data.totals.rn_daily)}</td>
                <td className={tdN}>{num(data.totals.rn_history)}</td>
                <td className={`${tdN} ${diffColor(data.totals.rn_daily - data.totals.rn_history)}`}>
                  {num(data.totals.rn_daily - data.totals.rn_history)}
                </td>
                <td className={`${tdN} border-l border-ink/10`}>{num(data.totals.pax_daily)}</td>
                <td className={tdN}>{num(data.totals.pax_history)}</td>
                <td className={`${tdN} ${diffColor(data.totals.pax_daily - data.totals.pax_history)}`}>
                  {num(data.totals.pax_daily - data.totals.pax_history)}
                </td>
                <td className={`${tdN} border-l border-ink/10`}>${money(data.revenue.daily_total)}</td>
                <td className={tdN}>${money(data.revenue.history_total)}</td>
                <td className={`${tdN} ${diffColor(data.revenue.diff)}`}>${money(data.revenue.diff)}</td>
              </tr>
              {data.comps && data.comps.rn_daily + data.comps.rn_history > 0 && (
                <tr className="border-t border-ink/10 bg-[#fbf3e6] italic text-amber-700/80">
                  <td className={td}>Comps &amp; In-House <span className="not-italic text-[10px] text-amber-700/50">(excl. from cross-check)</span></td>
                  <td className={`${tdN} border-l border-ink/10`}>{num(data.comps.rn_daily)}</td>
                  <td className={tdN}>{num(data.comps.rn_history)}</td>
                  <td className={tdN}>—</td>
                  <td className={`${tdN} border-l border-ink/10`}>{num(data.comps.pax_daily)}</td>
                  <td className={tdN}>{num(data.comps.pax_history)}</td>
                  <td className={tdN}>—</td>
                  <td className={`${tdN} border-l border-ink/10`}>$0.00</td>
                  <td className={tdN}>$0.00</td>
                  <td className={tdN}>—</td>
                </tr>
              )}
              {data.reconciled && data.comps && data.comps.rn_daily + data.comps.rn_history > 0 && (
                <tr className="border-t border-ink/15 bg-[#e8f0fb] font-bold text-ink/90">
                  <td className={td}>GRAND TOTAL (incl. comps)</td>
                  <td className={`${tdN} border-l border-ink/10`}>{num(data.reconciled.rn_daily)}</td>
                  <td className={tdN}>{num(data.reconciled.rn_history)}</td>
                  <td className={`${tdN} ${diffColor(data.reconciled.rn_daily - data.reconciled.rn_history)}`}>
                    {num(data.reconciled.rn_daily - data.reconciled.rn_history)}
                  </td>
                  <td className={`${tdN} border-l border-ink/10`}>{num(data.reconciled.pax_daily)}</td>
                  <td className={tdN}>{num(data.reconciled.pax_history)}</td>
                  <td className={`${tdN} ${diffColor(data.reconciled.pax_daily - data.reconciled.pax_history)}`}>
                    {num(data.reconciled.pax_daily - data.reconciled.pax_history)}
                  </td>
                  <td className={`${tdN} border-l border-ink/10`}>${money(data.revenue.daily_total)}</td>
                  <td className={tdN}>${money(data.revenue.history_total)}</td>
                  <td className={`${tdN} ${diffColor(data.revenue.diff)}`}>${money(data.revenue.diff)}</td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="rounded border border-ink/10 bg-[#fcfcfb] p-3 text-[11px] text-ink/60">
            Code mapping (dim_room_category.room_class):{" "}
            {Object.entries(data.room_class_mapping).map(([code, cat]) => `${code}→${cat}`).join(" · ")}
            <br />
            Revenue Daily = Integrity Room Revenue by category (account suffix 01-06, confirmed).
            Revenue History = sum of statroomtype by category. Revenue Daily only exists if the day has
            real Integrity ingestion (the Tab 6.4 backup doesn&apos;t carry this breakdown).
          </div>
        </>
      )}
    </div>
  );
}

type MarketRow = {
  market_code: string; rooms: number; persons: number;
  noshow_rooms: number; cancel_rooms: number; pct_of_total: number;
};
type KpiGroupRow = {
  kpi_group: string; market_codes: string[]; rooms: number; persons: number;
  noshow_rooms: number; cancel_rooms: number; pct_of_total: number;
};
type MarketSegmentSide = {
  rows: MarketRow[]; by_kpi_group: KpiGroupRow[]; total_rooms: number; total_persons: number;
};
type MarketSegmentReport = {
  business_date: string;
  market_names: Record<string, string>;
  today: MarketSegmentSide;
  mtd: MarketSegmentSide;
};

const COM_CODES = new Set(["COM"]);

function KpiGroupTable({ label, data }: { label: string; data: { by_kpi_group: KpiGroupRow[]; total_rooms: number; total_persons: number } }) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">{label} — by Channel (KPI)</div>
      <table className="w-full rounded-lg border border-ink/10 text-xs">
        <thead className="bg-[#fcfcfb]"><tr>
          <th className={th}>Channel</th><th className={th}>Market Codes Included</th>
          <th className={thN}>RN</th><th className={thN}>Pax</th>
          <th className={thN}>No Show</th><th className={thN}>Cancel</th>
          <th className={thN}>% of Total RN</th>
        </tr></thead>
        <tbody>
          {data.by_kpi_group.map((g) => (
            <tr key={g.kpi_group} className={`border-t border-ink/8 ${g.kpi_group === "Unmapped" ? "bg-amber-500/10" : ""}`}>
              <td className={`${td} font-medium ${g.kpi_group === "Unmapped" ? "text-amber-600" : ""}`}>{g.kpi_group}</td>
              <td className="px-3 py-1.5 font-mono text-ink/60">{g.market_codes.join(" + ") || "—"}</td>
              <td className={`${tdN} ${countColor(g.rooms)}`}>{num(g.rooms)}</td>
              <td className={`${tdN} ${countColor(g.persons)}`}>{num(g.persons)}</td>
              <td className={`${tdN} ${countColor(g.noshow_rooms)}`}>{num(g.noshow_rooms)}</td>
              <td className={`${tdN} ${countColor(g.cancel_rooms)}`}>{num(g.cancel_rooms)}</td>
              <td className={tdN}>{pct(g.pct_of_total)}</td>
            </tr>
          ))}
          <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
            <td className={td} colSpan={2}>TOTAL</td>
            <td className={`${tdN} ${countColor(data.total_rooms)}`}>{num(data.total_rooms)}</td>
            <td className={`${tdN} ${countColor(data.total_persons)}`}>{num(data.total_persons)}</td>
            <td className={tdN}>—</td>
            <td className={tdN}>—</td>
            <td className={tdN}>100.00%</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function MarketSegmentTable({ label, data, names }: {
  label: string; data: { rows: MarketRow[]; total_rooms: number; total_persons: number };
  names: Record<string, string>;
}) {
  if (data.rows.length === 0)
    return (
      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">{label}</div>
        <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-4 text-xs text-ink/60">No data.</div>
      </div>
    );
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">{label}</div>
      <table className="w-full rounded-lg border border-ink/10 text-xs">
        <thead className="bg-[#fcfcfb]"><tr>
          <th className={th}>Market Code</th>
          <th className={thN}>RN</th><th className={thN}>Pax</th>
          <th className={thN}>No Show</th><th className={thN}>Cancel</th>
          <th className={thN}>% of Total RN</th>
        </tr></thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.market_code} className={`border-t border-ink/8 ${COM_CODES.has(r.market_code) ? "bg-amber-500/10" : ""}`}>
              <td className={`${td} ${COM_CODES.has(r.market_code) ? "text-amber-600 font-medium" : ""}`}>
                {names[r.market_code] || r.market_code}
                <span className="ml-1 font-mono text-[10px] text-ink/60">({r.market_code})</span>
              </td>
              <td className={`${tdN} ${countColor(r.rooms)}`}>{num(r.rooms)}</td>
              <td className={`${tdN} ${countColor(r.persons)}`}>{num(r.persons)}</td>
              <td className={`${tdN} ${countColor(r.noshow_rooms)}`}>{num(r.noshow_rooms)}</td>
              <td className={`${tdN} ${countColor(r.cancel_rooms)}`}>{num(r.cancel_rooms)}</td>
              <td className={tdN}>{pct(r.pct_of_total)}</td>
            </tr>
          ))}
          <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
            <td className={td}>TOTAL</td>
            <td className={`${tdN} ${countColor(data.total_rooms)}`}>{num(data.total_rooms)}</td>
            <td className={`${tdN} ${countColor(data.total_persons)}`}>{num(data.total_persons)}</td>
            <td className={tdN}>—</td>
            <td className={tdN}>—</td>
            <td className={tdN}>100.00%</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function MarketSegment({ day }: { day: string }) {
  const [data, setData] = useState<MarketSegmentReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/revenue/market-segment/${day}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch {
      setData(null); setMsg(`No occupancy data for ${day}.`);
    } finally { setLoading(false); }
  }, [day]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-ink/60">
        Analysis by Market Code (sales channel / COM / In-house) — how many room-nights come
        from each channel, to see what&apos;s affecting the blended ADR. Source: Opera&apos;s XML STATISTICS
        (Tab 1/2.4) — no data if the day doesn&apos;t have that XML ingested.
      </p>
      {loading && <div className="text-sm text-ink/60">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-3 text-sm text-ink/75">{msg}</div>}
      {data && (
        <>
          <KpiGroupTable label={`Today — ${data.business_date}`} data={data.today} />
          <KpiGroupTable label="Month to Day" data={data.mtd} />
          <MarketSegmentTable label={`Today — ${data.business_date} (by Market Code)`} data={data.today} names={data.market_names} />
          <MarketSegmentTable label="Month to Day (by Market Code)" data={data.mtd} names={data.market_names} />
        </>
      )}
    </div>
  );
}
