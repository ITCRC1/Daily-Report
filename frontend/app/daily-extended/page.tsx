"use client";

import { Fragment, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";
import { useSubtabs } from "@/lib/useSubtabs";

const ALL_SUBTABS = [
  { id: "9.1", label: "9.1 Summary" },
  { id: "9.2", label: "9.2 Revenue Detail" },
  { id: "9.3", label: "9.3 Rooms by Segment" },
  { id: "9.5", label: "9.5 F&B by Meal Period" },
  { id: "9.6", label: "9.6 F&B Revenue" },
  { id: "9.7", label: "9.7 Spa" },
  { id: "9.8", label: "9.8 Beverage" },
];

type Col = {
  today: number | null; mtd_actual: number | null; mtd_budget: number | null;
  mtd_forecast: number | null; mtd_ly: number | null;
  // Mes completo: budget del mes entero + cuánto falta para cerrarlo.
  month_budget?: number | null; amount_to_budget?: number | null; monthly_var_pct?: number | null;
};
type SData = { business_date: string; days_mtd: number; rooms_stats: Record<string, Col>; revenue: Record<string, Col>; add_stats: Record<string, Col> };
type FT = "int" | "usd" | "pct" | "dec";

const fmt = (v: number | null | undefined, t: FT): string => {
  if (v === null || v === undefined) return "—";
  if (t === "pct") return `${(v * 100).toFixed(1)}%`;
  if (t === "int") return Math.round(v).toLocaleString("en-US");
  if (t === "dec") return v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const a = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return v < 0 ? `($${a})` : `$${a}`;
};
const fmtVar = (v: number | null, t: FT): string => {
  if (v === null || v === undefined) return "—";
  if (t === "pct") return `${v >= 0 ? "" : "("}${(Math.abs(v) * 100).toFixed(1)}%${v < 0 ? ")" : ""}`;
  return fmt(v, t);
};

const th = "px-2 py-1.5 text-right text-[11px] font-medium text-white/50 whitespace-nowrap";
const tdN = "px-2 py-1 text-right tabular-nums whitespace-nowrap";
const negC = (v: number | null) => (v !== null && v < 0 ? "text-rose-400" : "text-white/70");

function Row({ label, col, t, bold }: { label: string; col: Col | null; t: FT; bold?: boolean }) {
  const mtd = col?.mtd_actual ?? null, bud = col?.mtd_budget ?? null, fc = col?.mtd_forecast ?? null, ly = col?.mtd_ly ?? null;
  const mBud = col?.month_budget ?? null, a2b = col?.amount_to_budget ?? null, mPct = col?.monthly_var_pct ?? null;
  const vFc = mtd !== null && fc !== null ? mtd - fc : null;
  const vBud = mtd !== null && bud !== null ? mtd - bud : null;
  const vLy = mtd !== null && ly !== null ? mtd - ly : null;
  const rc = bold ? "bg-[#12151f] font-medium" : "";
  const c = bold ? "text-white/90" : "text-white/70";
  return (
    <tr className={`border-t border-white/5 ${rc}`}>
      <td className={`px-3 py-1 text-left ${bold ? "text-white/90" : "text-white/80"} whitespace-nowrap`}>{label}</td>
      <td className={`${tdN} ${c}`}>{fmt(col?.today, t)}</td>
      <td className={`${tdN} border-l border-white/10 ${negC(mtd)}`}>{fmt(mtd, t)}</td>
      <td className={`${tdN} text-white/40`}>{fmt(fc, t)}</td>
      <td className={`${tdN} ${negC(vFc)}`}>{fmtVar(vFc, t)}</td>
      <td className={`${tdN} border-l border-white/10 text-white/50`}>{fmt(bud, t)}</td>
      <td className={`${tdN} ${negC(vBud)}`}>{fmtVar(vBud, t)}</td>
      <td className={`${tdN} border-l border-white/10 text-white/40`}>{fmt(ly, t)}</td>
      <td className={`${tdN} ${negC(vLy)}`}>{fmtVar(vLy, t)}</td>
      {/* Mes completo: budget del mes entero vs lo acumulado, y cuánto falta. */}
      <td className={`${tdN} border-l border-white/10 text-white/50`}>{fmt(mBud, t)}</td>
      <td className={`${tdN} ${negC(a2b)}`}>{fmtVar(a2b, t)}</td>
      <td className={`${tdN} ${negC(mPct)}`}>{fmtVar(mPct, "pct")}</td>
    </tr>
  );
}

const GH = (label: string) => (
  <tr className="bg-[#161923]"><td className="px-3 py-1.5 text-left text-[11px] font-bold uppercase tracking-wide text-sky-200" colSpan={12}>{label}</td></tr>
);

const REV_ROWS: [string, string, boolean?][] = [
  ["Total Hotel Rooms Rev.", "rooms"], ["Food Revenue", "food"], ["Beverage Revenue", "beverage"],
  ["F&B Misc. Revenue", "fb_misc"], ["Total F&B Revenues", "total_fb", true], ["Total Spa & Fitness", "spa"],
  ["Total Telecommunications", "telecom"], ["Guest Support & Activities", "activities"],
  ["Miscellaneous", "misc"], ["Total Revenues", "total", true],
];
const POR_ROWS: [string, string][] = [
  ["Total Rooms and Residential", "rooms"], ["Food & Beverage", "total_fb"], ["Total Spa & Fitness", "spa"],
  ["Total Telecommunications", "telecom"], ["Guest Support & Activities", "activities"],
  ["Miscellaneous", "misc"], ["Total Revenues POR", "total"],
];
const ADD_MANUAL = ["Rooms Arrivals", "Rooms Departures", "Cancelled", "Walkins", "Relocated", "Avg Length of Stay", "Children, Number of"];

function Summary({ date }: { date: string }) {
  const [d, setD] = useState<SData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true; setErr(""); setD(null);
    fetch(`${API_URL}/daily-extended/summary?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (!live) return; if (j.detail) setErr(j.detail); else setD(j); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [date]);

  const por = (k: string): Col | null => {
    if (!d) return null;
    const occT = d.rooms_stats.occupied.today ?? 0, occM = d.rooms_stats.occupied.mtd_actual ?? 0;
    const v = d.revenue[k];
    return {
      today: occT && v.today !== null ? v.today / occT : null,
      mtd_actual: occM && v.mtd_actual !== null ? v.mtd_actual / occM : null,
      mtd_budget: null, mtd_forecast: null, mtd_ly: null,
    };
  };

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40">
        Portada del Daily Revenue Report (pág. 2) · {date} · MTD = {d?.days_mtd ?? 0} días. Rooms stats y Revenue por
        categoría <b>reales</b> (motor sobre Integrity, como Tab 3/4). <b>Budget</b> = prorrateado a los {d?.days_mtd ?? 0} días
        corridos (comparable 1:1 con M-T-D Actual); <b>Budget Mes</b> = el mes completo (el de 6.1), y <b>Falta</b> = lo
        acumulado menos ese mes completo. Forecast y Año anterior vendrán de la carga.
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="text-xs">
          <thead className="bg-[#1E2130]">
            <tr>
              <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50">Summary</th>
              <th className={th}>Today</th>
              <th className={`${th} border-l border-white/10`}>M-T-D Actual</th>
              <th className={th}>Forecast</th><th className={th}>Var</th>
              <th className={`${th} border-l border-white/10`}>Budget</th><th className={th}>Var</th>
              <th className={`${th} border-l border-white/10`}>Año ant.</th><th className={th}>Var</th>
              <th className={`${th} border-l border-white/10`}>Budget Mes</th>
              <th className={th}>Falta</th><th className={th}>Var %</th>
            </tr>
          </thead>
          <tbody>
            {GH("Rooms Statistics")}
            <Row label="Available Rooms" col={d?.rooms_stats.available ?? null} t="int" />
            <Row label="Occupied Rooms" col={d?.rooms_stats.occupied ?? null} t="int" />
            <Row label="Occupancy" col={d?.rooms_stats.occupancy ?? null} t="pct" />
            <Row label="ADR" col={d?.rooms_stats.adr ?? null} t="usd" />
            <Row label="RevPAR" col={d?.rooms_stats.revpar ?? null} t="usd" />

            {GH("Revenue")}
            {REV_ROWS.map(([label, k, bold]) => <Row key={label} label={label} col={d?.revenue[k] ?? null} t="usd" bold={bold} />)}

            {GH("Additional Rooms Statistics")}
            {ADD_MANUAL.map((label) => <Row key={label} label={label} col={null} t={label.includes("Length") ? "dec" : "int"} />)}
            <Row label="Rooms # of Guests" col={d?.add_stats.guests ?? null} t="int" />
            <Row label="Double Occupancy" col={d?.add_stats.double_occupancy ?? null} t="pct" />

            {GH("Revenue / Occupied Room (POR)")}
            {POR_ROWS.map(([label, k]) => <Row key={label} label={label} col={por(k)} t="usd" bold={k === "total"} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---- 9.3 Rooms by Segment ----------------------------------------------------
type SegMetrics = { rn: number; occ: number; rev: number; adr: number };
type Seg = { market_code: string; description: string | null; group: string; today: SegMetrics; mtd: SegMetrics };
type SegGroup = { group: string; segments: Seg[]; subtotal: { today: SegMetrics; mtd: SegMetrics } };
type RBSData = {
  business_date: string; days_mtd: number;
  available: { today: number; mtd: number };
  groups: SegGroup[]; total: { today: SegMetrics; mtd: SegMetrics };
};

const segTh = "px-2 py-1.5 text-right text-[11px] font-medium text-white/50 whitespace-nowrap";
function SegCells({ m, bold }: { m: SegMetrics; bold?: boolean }) {
  const c = bold ? "text-white/90" : "text-white/70";
  return (
    <>
      <td className={`${tdN} border-l border-white/10 ${c}`}>{fmt(m.rn, "int")}</td>
      <td className={`${tdN} ${c}`}>{fmt(m.occ, "pct")}</td>
      <td className={`${tdN} ${c}`}>{fmt(m.rev, "usd")}</td>
      <td className={`${tdN} ${c}`}>{fmt(m.adr, "usd")}</td>
    </>
  );
}

function RoomsBySegment({ date }: { date: string }) {
  const [d, setD] = useState<RBSData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true; setErr(""); setD(null);
    fetch(`${API_URL}/daily-extended/rooms-by-segment?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (!live) return; if (j.detail) setErr(j.detail); else setD(j); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [date]);

  const empty = d && d.groups.length === 0;
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40">
        Rooms by Market Segment (pág. 5–6) · {date} · MTD = {d?.days_mtd ?? 0} días. RN y Room Revenue <b>reales</b> por
        segmento (XML Statistics + XML Revenue, igual que Tab 7.10). Occ% = RN del segmento / habitaciones disponibles; ADR = Rev / RN.
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      {empty && <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5 text-xs text-white/50">Sin datos de segmento para esta fecha.</div>}
      {d && !empty && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="text-xs">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50" rowSpan={2}>Market Segment</th>
                <th className="px-2 py-1 text-center text-[11px] font-semibold text-sky-200 border-l border-white/10" colSpan={4}>Today</th>
                <th className="px-2 py-1 text-center text-[11px] font-semibold text-sky-200 border-l border-white/10" colSpan={4}>M-T-D</th>
              </tr>
              <tr>
                <th className={`${segTh} border-l border-white/10`}>RN</th><th className={segTh}>Occ%</th><th className={segTh}>Revenue</th><th className={segTh}>ADR</th>
                <th className={`${segTh} border-l border-white/10`}>RN</th><th className={segTh}>Occ%</th><th className={segTh}>Revenue</th><th className={segTh}>ADR</th>
              </tr>
            </thead>
            <tbody>
              {d.groups.map((g) => (
                <Fragment key={g.group}>
                  {GH(g.group)}
                  {g.segments.map((s) => (
                    <tr key={s.market_code} className="border-t border-white/5">
                      <td className="px-3 py-1 text-left text-white/80 whitespace-nowrap">
                        <span className="text-white/50">{s.market_code}</span>{s.description ? ` · ${s.description}` : ""}
                      </td>
                      <SegCells m={s.today} />
                      <SegCells m={s.mtd} />
                    </tr>
                  ))}
                  <tr className="border-t border-white/10 bg-[#12151f] font-medium">
                    <td className="px-3 py-1 text-left text-white/90 whitespace-nowrap">Subtotal {g.group}</td>
                    <SegCells m={g.subtotal.today} bold />
                    <SegCells m={g.subtotal.mtd} bold />
                  </tr>
                </Fragment>
              ))}
              <tr className="border-t-2 border-white/20 bg-[#161923] font-semibold">
                <td className="px-3 py-1.5 text-left text-white whitespace-nowrap">TOTAL</td>
                <SegCells m={d.total.today} bold />
                <SegCells m={d.total.mtd} bold />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---- 9.2 Revenue Detail ------------------------------------------------------
type RDLine = { dept_code: string; label: string; today: number; mtd_actual: number; mtd_budget: number };
type RDSection = { name: string; lines: RDLine[]; subtotal: { today: number; mtd_actual: number; mtd_budget: number } };
type RDData = { business_date: string; days_mtd: number; sections: RDSection[]; total: { today: number; mtd_actual: number; mtd_budget: number } };

function RDRow({ label, today, mtd, bud, bold, indent }: {
  label: string; today: number; mtd: number; bud: number; bold?: boolean; indent?: boolean;
}) {
  const v = mtd - bud;
  const c = bold ? "text-white/90" : "text-white/70";
  return (
    <tr className={`border-t border-white/5 ${bold ? "bg-[#12151f] font-medium" : ""}`}>
      <td className={`px-3 py-1 text-left whitespace-nowrap ${bold ? "text-white/90" : "text-white/80"} ${indent ? "pl-6" : ""}`}>{label}</td>
      <td className={`${tdN} ${c}`}>{fmt(today, "usd")}</td>
      <td className={`${tdN} border-l border-white/10 ${negC(mtd)}`}>{fmt(mtd, "usd")}</td>
      <td className={`${tdN} text-white/50`}>{fmt(bud, "usd")}</td>
      <td className={`${tdN} ${negC(v)}`}>{fmtVar(v, "usd")}</td>
    </tr>
  );
}

function RevenueDetail({ date }: { date: string }) {
  const [d, setD] = useState<RDData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true; setErr(""); setD(null);
    fetch(`${API_URL}/daily-extended/revenue-detail?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (!live) return; if (j.detail) setErr(j.detail); else setD(j); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [date]);

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40">
        Revenue Detail por outlet (pág. 3–4) · {date} · MTD = {d?.days_mtd ?? 0} días. Revenue <b>real</b> por
        departamento (motor sobre Integrity, igual que Tab 3/4/9.1) + Budget MTD por outlet. Detalle de lo que 9.1 muestra colapsado por categoría.
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      {d && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="text-xs">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50">Revenue Detail</th>
                <th className={segTh}>Today</th>
                <th className={`${segTh} border-l border-white/10`}>M-T-D Actual</th>
                <th className={segTh}>Budget</th><th className={segTh}>Var</th>
              </tr>
            </thead>
            <tbody>
              {d.sections.map((sec) => (
                <Fragment key={sec.name}>
                  {GH(sec.name)}
                  {sec.lines.map((ln) => (
                    <RDRow key={ln.dept_code} label={ln.label} today={ln.today} mtd={ln.mtd_actual} bud={ln.mtd_budget} indent />
                  ))}
                  <RDRow label={`Total ${sec.name}`} today={sec.subtotal.today} mtd={sec.subtotal.mtd_actual} bud={sec.subtotal.mtd_budget} bold />
                </Fragment>
              ))}
              <tr className="border-t-2 border-white/20 bg-[#161923] font-semibold">
                <td className="px-3 py-1.5 text-left text-white whitespace-nowrap">TOTAL REVENUE</td>
                <td className={`${tdN} text-white/90`}>{fmt(d.total.today, "usd")}</td>
                <td className={`${tdN} border-l border-white/10 ${negC(d.total.mtd_actual)}`}>{fmt(d.total.mtd_actual, "usd")}</td>
                <td className={`${tdN} text-white/50`}>{fmt(d.total.mtd_budget, "usd")}</td>
                <td className={`${tdN} ${negC(d.total.mtd_actual - d.total.mtd_budget)}`}>{fmtVar(d.total.mtd_actual - d.total.mtd_budget, "usd")}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---- 9.5 F&B by Meal Period (sub-departamento × meal period × Food/Bev) -------
type FBMetrics = { food: number; beverage: number; misc: number; total: number };
type FBPair = { today: number; mtd: number };
type FBMeal = { meal_period: string; today: FBMetrics; mtd: FBMetrics; covers: FBPair; avg_check: FBPair };
type FBOutlet = {
  outlet: string; sub_department: string; meals: FBMeal[];
  subtotal: { today: FBMetrics; mtd: FBMetrics }; covers: FBPair; avg_check: FBPair;
};
type FBData = {
  business_date: string; days_mtd: number; outlets: FBOutlet[];
  total: { today: FBMetrics; mtd: FBMetrics };
  customers: { today: number; mtd: number };
  avg_check: { today: number; mtd: number };
};

function FBCells({ m, bold }: { m: FBMetrics; bold?: boolean }) {
  const c = bold ? "text-white/90" : "text-white/70";
  return (
    <>
      <td className={`${tdN} border-l border-white/10 ${c}`}>{fmt(m.food, "usd")}</td>
      <td className={`${tdN} ${c}`}>{fmt(m.beverage, "usd")}</td>
      <td className={`${tdN} ${c}`}>{fmt(m.misc, "usd")}</td>
      <td className={`${tdN} ${bold ? "text-white/90" : "text-white/80"} font-medium`}>{fmt(m.total, "usd")}</td>
    </>
  );
}

// Covers (cubiertos) + Avg Check. Los cubiertos de Today se capturan a mano por
// celda (outlet × meal period): ni Integrity ni POS los tienen.
function FBCovAvg({ covers, avg, bold, edit }: {
  covers: number; avg: number; bold?: boolean;
  edit?: { value: string; onChange: (v: string) => void; onCommit: () => void; busy: boolean };
}) {
  const c = bold ? "text-white/90" : "text-white/70";
  return (
    <>
      <td className={`${tdN} border-l border-white/10 ${c}`}>
        {edit ? (
          <input
            value={edit.value}
            disabled={edit.busy}
            onChange={(e) => edit.onChange(e.target.value)}
            onBlur={edit.onCommit}
            onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
            className="w-16 rounded border border-white/15 bg-[#0F1118] px-1 py-0.5 text-right text-xs text-white tabular-nums focus:border-accent focus:outline-none disabled:opacity-40"
          />
        ) : (
          fmt(covers, "int")
        )}
      </td>
      <td className={`${tdN} ${bold ? "text-white/90 font-medium" : "text-white/70"}`}>
        {covers ? fmt(avg, "usd") : <span className="text-white/25">—</span>}
      </td>
    </>
  );
}

function FBMealPeriod({ date }: { date: string }) {
  const [d, setD] = useState<FBData | null>(null);
  const [err, setErr] = useState("");
  const [cust, setCust] = useState("");
  const [saving, setSaving] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyCell, setBusyCell] = useState("");
  const [upMsg, setUpMsg] = useState("");

  const cellKey = (outlet: string, meal: string) => `${outlet}|${meal}`;

  const saveCover = async (outlet: string, meal: string) => {
    const key = cellKey(outlet, meal);
    const raw = drafts[key];
    if (raw === undefined) return;
    const n = parseInt(raw, 10);
    if (Number.isNaN(n) || n < 0) { setErr("Cubiertos: ingresa un entero >= 0."); return; }
    setBusyCell(key); setErr("");
    try {
      const r = await fetch(`${API_URL}/daily-extended/fb-covers?business_date=${date}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outlet, meal_period: meal, covers: n }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setD(j); setCust(String(j.customers.today)); setDrafts({});
    } catch (e) { setErr(String(e)); }
    finally { setBusyCell(""); }
  };

  // fetch (no un <a href> pelado) para poder mostrar el error si el backend
  // falla, en vez de que el navegador se vaya a una página en blanco.
  const downloadTemplate = async () => {
    setUpMsg("Generando plantilla…"); setErr("");
    try {
      const year = date.slice(0, 4);
      const month = parseInt(date.slice(5, 7), 10);
      const res = await fetch(`${API_URL}/daily-extended/fb-covers/template?year=${year}&month=${month}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = match ? match[1] : `FB_Covers_${year}-${month}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      setUpMsg("");
    } catch (e) { setUpMsg(""); setErr(String(e)); }
  };

  const uploadCovers = async (file: File) => {
    setUpMsg("Subiendo…"); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${API_URL}/daily-extended/fb-covers/upload`, { method: "POST", body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setUpMsg(`✓ ${j.rows_loaded} celdas · ${j.days} días (${j.date_from} → ${j.date_to}) · ${j.total_covers} cubiertos`);
      const rr = await fetch(`${API_URL}/daily-extended/fb-by-meal-period?business_date=${date}`, { cache: "no-store" });
      const jj = await rr.json();
      if (!jj.detail) { setD(jj); setCust(String(jj.customers.today)); setDrafts({}); }
    } catch (e) { setUpMsg(""); setErr(String(e)); }
  };
  useEffect(() => {
    let live = true; setErr(""); setD(null);
    fetch(`${API_URL}/daily-extended/fb-by-meal-period?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (!live) return; if (j.detail) setErr(j.detail); else { setD(j); setCust(String(j.customers.today)); } })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [date]);

  const saveCustomers = async () => {
    const n = parseInt(cust, 10);
    if (Number.isNaN(n) || n < 0) { setErr("Ingresa un número válido de customers."); return; }
    setSaving(true); setErr("");
    try {
      const r = await fetch(`${API_URL}/daily-extended/fb-customers?business_date=${date}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ customers: n }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setD(j); setCust(String(j.customers.today));
    } catch (e) { setErr(String(e)); }
    finally { setSaving(false); }
  };
  const custDirty = d !== null && cust !== String(d.customers.today);

  const empty = d && d.outlets.length === 0;
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40">
        F&B by Meal Period (pág. 9–11) · {date} · MTD = {d?.days_mtd ?? 0} días. Revenue <b>real</b> de <b>Integrity</b> por
        sub-departamento (outlet, los 8 del catálogo) × meal period (del nombre de cuenta) × Food/Beverage (por naturaleza). Reconcilia 1:1 con el Total F&B de 9.1/9.2.
        Requiere Integrity cargado del día. <b>Covers</b> (cubiertos) se capturan a mano por celda — escribí en la columna
        Covers de <b>Today</b> y se guarda al salir del campo. <b>Avg Check = Revenue ÷ Covers</b>.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={downloadTemplate}
          className="rounded bg-white/10 px-2.5 py-1 text-[11px] text-white/70 hover:bg-white/20"
        >
          ⬇ Plantilla de Covers (mes)
        </button>
        <label className="cursor-pointer rounded bg-accent/80 px-2.5 py-1 text-[11px] text-white hover:bg-accent">
          ⬆ Cargar Covers
          <input
            type="file" accept=".xlsx" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCovers(f); e.target.value = ""; }}
          />
        </label>
        {upMsg && <span className={upMsg.startsWith("✓") ? "text-[11px] text-emerald-400" : "text-[11px] text-white/50"}>{upMsg}</span>}
      </div>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      {empty && <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5 text-xs text-white/50">Sin detalle de F&B en Integrity para esta fecha.</div>}
      {d && !empty && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="text-xs">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50" rowSpan={2}>Sub-departamento / Meal Period</th>
                <th className="px-2 py-1 text-center text-[11px] font-semibold text-sky-200 border-l border-white/10" colSpan={6}>Today</th>
                <th className="px-2 py-1 text-center text-[11px] font-semibold text-sky-200 border-l border-white/10" colSpan={6}>M-T-D</th>
              </tr>
              <tr>
                <th className={`${segTh} border-l border-white/10`}>Food</th><th className={segTh}>Beverage</th><th className={segTh}>Misc</th><th className={segTh}>Total</th>
                <th className={`${segTh} border-l border-white/10`}>Covers</th><th className={segTh}>Avg Check</th>
                <th className={`${segTh} border-l border-white/10`}>Food</th><th className={segTh}>Beverage</th><th className={segTh}>Misc</th><th className={segTh}>Total</th>
                <th className={`${segTh} border-l border-white/10`}>Covers</th><th className={segTh}>Avg Check</th>
              </tr>
            </thead>
            <tbody>
              {d.outlets.map((o) => {
                const inactive = o.subtotal.today.total === 0 && o.subtotal.mtd.total === 0 && o.meals.length === 0;
                return (
                  <Fragment key={o.outlet}>
                    <tr className="border-t border-white/10 bg-[#12151f] font-medium">
                      <td className={`px-3 py-1 text-left whitespace-nowrap ${inactive ? "text-white/35" : "text-white/90"}`}>
                        <span className="text-white/40">{o.outlet}</span> · {o.sub_department}
                        {inactive && <span className="ml-2 text-[10px] text-white/30">(sin movimiento)</span>}
                      </td>
                      <FBCells m={o.subtotal.today} bold />
                      <FBCovAvg covers={o.covers.today} avg={o.avg_check.today} bold />
                      <FBCells m={o.subtotal.mtd} bold />
                      <FBCovAvg covers={o.covers.mtd} avg={o.avg_check.mtd} bold />
                    </tr>
                    {o.meals.map((ml) => {
                      const k = cellKey(o.outlet, ml.meal_period);
                      return (
                        <tr key={k} className="border-t border-white/5">
                          <td className="px-3 py-1 pl-8 text-left text-white/55 whitespace-nowrap">{ml.meal_period}</td>
                          <FBCells m={ml.today} />
                          <FBCovAvg
                            covers={ml.covers.today} avg={ml.avg_check.today}
                            edit={{
                              value: drafts[k] ?? String(ml.covers.today),
                              onChange: (v) => setDrafts((s) => ({ ...s, [k]: v })),
                              onCommit: () => saveCover(o.outlet, ml.meal_period),
                              busy: busyCell === k,
                            }}
                          />
                          <FBCells m={ml.mtd} />
                          <FBCovAvg covers={ml.covers.mtd} avg={ml.avg_check.mtd} />
                        </tr>
                      );
                    })}
                  </Fragment>
                );
              })}
              <tr className="border-t-2 border-white/20 bg-[#161923] font-semibold">
                <td className="px-3 py-1.5 text-left text-white whitespace-nowrap">TOTAL F&B</td>
                <FBCells m={d.total.today} bold />
                <FBCovAvg covers={d.customers.today} avg={d.avg_check.today} bold />
                <FBCells m={d.total.mtd} bold />
                <FBCovAvg covers={d.customers.mtd} avg={d.avg_check.mtd} bold />
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {d && !empty && (
        <div className="flex flex-wrap gap-3 pt-1">
          {/* Total Revenue */}
          <div className="min-w-[220px] flex-1 rounded-lg border border-white/10 bg-[#1E2130] p-3">
            <div className="text-[11px] uppercase tracking-wide text-white/40">Total Revenue</div>
            <div className="mt-2 flex items-end justify-between gap-3">
              <div><div className="text-[10px] text-white/35">Today</div><div className="text-base font-semibold text-white/90 tabular-nums">{fmt(d.total.today.total, "usd")}</div></div>
              <div className="text-right"><div className="text-[10px] text-white/35">M-T-D</div><div className="text-base font-semibold text-white/90 tabular-nums">{fmt(d.total.mtd.total, "usd")}</div></div>
            </div>
          </div>
          {/* Total Customers (editable) */}
          <div className="min-w-[220px] flex-1 rounded-lg border border-white/10 bg-[#1E2130] p-3">
            <div className="flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-wide text-white/40">Total Customers</div>
              <button onClick={saveCustomers} disabled={saving || !custDirty}
                className={`rounded px-2 py-0.5 text-[10px] ${custDirty && !saving ? "bg-accent text-white hover:opacity-90" : "bg-[#12151f] text-white/40"}`}>
                {saving ? "…" : "Guardar"}
              </button>
            </div>
            <div className="mt-2 flex items-end justify-between gap-3">
              <div>
                <div className="text-[10px] text-white/35">Today</div>
                <input type="number" min={0} value={cust} disabled={saving}
                  onChange={(e) => setCust(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") saveCustomers(); }}
                  className="mt-0.5 w-24 rounded border border-white/15 bg-[#0f1219] px-2 py-1 text-right tabular-nums text-white/90 focus:border-accent focus:outline-none" />
              </div>
              <div className="text-right"><div className="text-[10px] text-white/35">M-T-D</div><div className="text-base font-semibold text-white/90 tabular-nums">{fmt(d.customers.mtd, "int")}</div></div>
            </div>
          </div>
          {/* Average Check */}
          <div className="min-w-[220px] flex-1 rounded-lg border border-white/10 bg-[#12151f] p-3">
            <div className="text-[11px] uppercase tracking-wide text-white/50">Average Check</div>
            <div className="mt-2 flex items-end justify-between gap-3">
              <div><div className="text-[10px] text-white/35">Today</div><div className="text-base font-semibold text-white tabular-nums">{fmt(d.avg_check.today, "usd")}</div></div>
              <div className="text-right"><div className="text-[10px] text-white/35">M-T-D</div><div className="text-base font-semibold text-white tabular-nums">{fmt(d.avg_check.mtd, "usd")}</div></div>
            </div>
          </div>
        </div>
      )}
      {d && !empty && (
        <p className="text-[11px] text-white/35">
          Average Check = Total Revenue ÷ Total Customers. El conteo de customers se captura a mano (no existe en el sistema);
          se guarda por día ({date}) y el MTD suma los días cargados.
        </p>
      )}
    </div>
  );
}


// ---- 9.6 F&B Revenue (recap FS: Food/Beverage/Misc × outlet) -----------------
type RecapLine = { label: string; outlet: string; col: Col };
type RecapSection = { key: string; label: string; lines: RecapLine[]; total: Col };
type RecapData = { business_date: string; days_mtd: number; sections: RecapSection[]; total: Col };

function FBRecap({ date }: { date: string }) {
  const [d, setD] = useState<RecapData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true; setErr(""); setD(null);
    fetch(`${API_URL}/daily-extended/fb-revenue-recap?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (!live) return; if (j.detail) setErr(j.detail); else setD(j); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [date]);

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40">
        F&B Revenue recap (formato FS) · {date} · MTD = {d?.days_mtd ?? 0} días. Tres secciones (Food / Beverage / F&B Misc.)
        con los <b>outlets</b> como filas. Actual <b>real</b> de Integrity por outlet; Budget solo en la fila Total (por naturaleza, no por outlet);
        Forecast y Año anterior = "—" (vienen de la carga). Reconcilia con 9.1/9.2.
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      {d && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="text-xs">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50">F&B Revenue</th>
                <th className={th}>Today</th>
                <th className={`${th} border-l border-white/10`}>M-T-D Actual</th>
                <th className={th}>Forecast</th><th className={th}>Var</th>
                <th className={`${th} border-l border-white/10`}>Budget</th><th className={th}>Var</th>
                <th className={`${th} border-l border-white/10`}>Año ant.</th><th className={th}>Var</th>
              </tr>
            </thead>
            <tbody>
              {d.sections.map((s) => (
                <Fragment key={s.key}>
                  {GH(s.label)}
                  {s.lines.map((ln) => <Row key={ln.outlet} label={ln.label} col={ln.col} t="usd" />)}
                  <Row label={`Total ${s.label}`} col={s.total} t="usd" bold />
                </Fragment>
              ))}
              <tr className="border-t-2 border-white/20"><td colSpan={9} className="p-0" /></tr>
              <Row label="Total F&B Revenues" col={d.total} t="usd" bold />
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---- 9.8 Beverage Detail (Beverage Revenue por concepto: Beer/Wine/Liquors) --
type BevSection = { concept: string; lines: RecapLine[]; subtotal: Col };
type BevData = {
  business_date: string; days_mtd: number;
  sections: BevSection[]; total: Col; na_beverage: { today: number; mtd: number };
};

function BeverageDetail({ date }: { date: string }) {
  const [d, setD] = useState<BevData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true; setErr(""); setD(null);
    fetch(`${API_URL}/daily-extended/beverage-detail?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (!live) return; if (j.detail) setErr(j.detail); else setD(j); })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [date]);

  const empty = d && d.sections.length === 0;
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40">
        Beverage Revenue por concepto (pág. 9–11) · {date} · MTD = {d?.days_mtd ?? 0} días. El Beverage (naturalezas 4125/4130/4131)
        se abre en <b>Beer / Wine / Liquors</b> con los outlets como filas. Real de Integrity; reconcilia con el Beverage de 9.6/9.2.
        Budget solo en el Total (por naturaleza). El <b>NA Beverage</b> es memo — el catálogo lo clasifica en Food, no en Beverage.
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      {empty && <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5 text-xs text-white/50">Sin detalle de Beverage en Integrity para esta fecha.</div>}
      {d && !empty && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="text-xs">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50">Beverage · Concepto</th>
                <th className={th}>Today</th>
                <th className={`${th} border-l border-white/10`}>M-T-D Actual</th>
                <th className={th}>Forecast</th><th className={th}>Var</th>
                <th className={`${th} border-l border-white/10`}>Budget</th><th className={th}>Var</th>
                <th className={`${th} border-l border-white/10`}>Año ant.</th><th className={th}>Var</th>
              </tr>
            </thead>
            <tbody>
              {d.sections.map((s) => (
                <Fragment key={s.concept}>
                  {GH(s.concept)}
                  {s.lines.map((ln) => <Row key={ln.outlet + ln.label} label={ln.label} col={ln.col} t="usd" />)}
                  <Row label={`Total ${s.concept}`} col={s.subtotal} t="usd" bold />
                </Fragment>
              ))}
              <tr className="border-t-2 border-white/20"><td colSpan={9} className="p-0" /></tr>
              <Row label="Total Beverage Revenue" col={d.total} t="usd" bold />
              <tr className="border-t border-white/5">
                <td className="px-3 py-1 text-left text-white/40 italic whitespace-nowrap">NA Beverage (memo — va en Food)</td>
                <td className={`${tdN} text-white/40`}>{fmt(d.na_beverage.today, "usd")}</td>
                <td className={`${tdN} border-l border-white/10 text-white/40`}>{fmt(d.na_beverage.mtd, "usd")}</td>
                <td colSpan={6} className="p-0" />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---- 9.7 Spa (Monto · Total Treatments · Average Rate) -----------------------
type SpaData = {
  business_date: string; days_mtd: number;
  revenue: { today: number; mtd: number };
  treatments: { today: number; mtd: number };
  avg_rate: { today: number; mtd: number };
};

function SpaSummary({ date }: { date: string }) {
  const [d, setD] = useState<SpaData | null>(null);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const load = () => {
    setErr("");
    fetch(`${API_URL}/daily-extended/spa?business_date=${date}`, { cache: "no-store" })
      .then((r) => r.json()).then((j) => { if (j.detail) setErr(j.detail); else { setD(j); setInput(String(j.treatments.today)); } })
      .catch((e) => setErr(String(e)));
  };
  useEffect(() => { setD(null); load(); /* eslint-disable-next-line */ }, [date]);

  const save = async () => {
    const n = parseInt(input, 10);
    if (Number.isNaN(n) || n < 0) { setErr("Ingresa un número válido de treatments."); return; }
    setSaving(true); setErr("");
    try {
      const r = await fetch(`${API_URL}/daily-extended/spa/treatments?business_date=${date}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ treatments: n }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setD(j); setInput(String(j.treatments.today));
    } catch (e) { setErr(String(e)); }
    finally { setSaving(false); }
  };

  const dirty = d !== null && input !== String(d.treatments.today);
  return (
    <div className="space-y-3 max-w-2xl">
      <p className="text-[11px] text-white/40">
        Spa · {date} · MTD = {d?.days_mtd ?? 0} días. <b>Monto</b> = revenue de Spa (dept 0140) real de Integrity (reconcilia con 9.1/9.2).
        El <b>conteo de treatments</b> se captura a mano (no existe en el sistema); <b>Average Rate</b> = Monto ÷ Treatments.
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}
      {d && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="text-xs w-full">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className="px-3 py-1.5 text-left text-[11px] font-medium text-white/50">Spa</th>
                <th className={th}>Today</th>
                <th className={`${th} border-l border-white/10`}>M-T-D</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-white/5">
                <td className="px-3 py-1.5 text-left text-white/80 whitespace-nowrap">Monto Spa</td>
                <td className={`${tdN} text-white/70`}>{fmt(d.revenue.today, "usd")}</td>
                <td className={`${tdN} border-l border-white/10 text-white/70`}>{fmt(d.revenue.mtd, "usd")}</td>
              </tr>
              <tr className="border-t border-white/5">
                <td className="px-3 py-1.5 text-left text-white/80 whitespace-nowrap">Total Treatments</td>
                <td className={`${tdN}`}>
                  <input
                    type="number" min={0} value={input} disabled={saving}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") save(); }}
                    className="w-24 rounded border border-white/15 bg-[#0f1219] px-2 py-1 text-right tabular-nums text-white/90 focus:border-accent focus:outline-none"
                  />
                </td>
                <td className={`${tdN} border-l border-white/10 text-white/70`}>{fmt(d.treatments.mtd, "int")}</td>
              </tr>
              <tr className="border-t border-white/10 bg-[#12151f] font-medium">
                <td className="px-3 py-1.5 text-left text-white/90 whitespace-nowrap">Average Rate</td>
                <td className={`${tdN} text-white/90`}>{fmt(d.avg_rate.today, "usd")}</td>
                <td className={`${tdN} border-l border-white/10 text-white/90`}>{fmt(d.avg_rate.mtd, "usd")}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      <div className="flex items-center gap-2">
        <button onClick={save} disabled={saving || !dirty}
          className={`rounded px-3 py-1.5 text-xs ${dirty && !saving ? "bg-accent text-white hover:opacity-90" : "bg-[#1E2130] text-white/40"}`}>
          {saving ? "Guardando…" : "Guardar treatments"}
        </button>
        <span className="text-[11px] text-white/35">Guarda el conteo de treatments del día ({date}); el MTD suma los días cargados.</span>
      </div>
    </div>
  );
}

// Render de UN sub-tab por id -- lo usa tanto la vista normal (uno a la vez)
// como la vista de impresión (todos apilados), para no duplicar el mapeo.
function SubtabBody({ id, date }: { id: string; date: string }) {
  switch (id) {
    case "9.1": return <Summary date={date} />;
    case "9.2": return <RevenueDetail date={date} />;
    case "9.3": return <RoomsBySegment date={date} />;
    case "9.5": return <FBMealPeriod date={date} />;
    case "9.6": return <FBRecap date={date} />;
    case "9.7": return <SpaSummary date={date} />;
    case "9.8": return <BeverageDetail date={date} />;
    default: return null;
  }
}

export default function DailyExtendedPage() {
  const { subtabs: SUBTABS, tab, setTab } = useSubtabs(ALL_SUBTABS, "9.1");
  const anchor = useBusinessDate();
  // Vista de impresión: renderiza TODOS los sub-tabs habilitados apilados, uno
  // por página. No auto-imprime: cada sub-tab trae sus propios datos por fetch,
  // así que el usuario dispara la impresión cuando ya cargaron (evita imprimir
  // secciones a medio cargar por adivinar un timeout).
  const [printing, setPrinting] = useState(false);

  // El navegador usa `document.title` como nombre sugerido del archivo al
  // imprimir / "Guardar como PDF" -- por eso el título lleva la fecha del
  // reporte. Se restaura al salir de la vista de impresión.
  useEffect(() => {
    if (!printing) return;
    const prev = document.title;
    document.title = `Daily Revenue Report - COWLCR - ${anchor}`;
    return () => { document.title = prev; };
  }, [printing, anchor]);

  if (printing) {
    return (
      <section className="print-report w-[calc(100vw-1.5rem)] -translate-x-1/2 relative left-1/2 space-y-4">
        <div className="no-print sticky top-0 z-20 flex flex-wrap items-center gap-2 rounded-lg border border-accent/40 bg-[#1E2130] px-3 py-2">
          <span className="text-xs text-white/80">
            Vista de impresión · {SUBTABS.length} secciones ({SUBTABS[0]?.id}–{SUBTABS[SUBTABS.length - 1]?.id}) · {anchor}
          </span>
          <span className="text-[11px] text-white/40">Esperá a que carguen todas y luego imprimí.</span>
          <span className="ml-auto flex gap-2">
            <button onClick={() => window.print()}
              className="rounded bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/80">
              🖨 Imprimir
            </button>
            <button onClick={() => setPrinting(false)}
              className="rounded bg-white/10 px-3 py-1 text-xs text-white/70 hover:bg-white/20">
              Salir
            </button>
          </span>
        </div>

        <div className="print-head hidden">
          <h1>Daily Revenue Report — Corcovado Wilderness Lodge</h1>
          <p>{anchor}</p>
        </div>

        {SUBTABS.map((s) => (
          <section key={s.id} className="print-section space-y-2">
            <h2 className="print-section-title text-sm font-semibold text-white/90">{s.label}</h2>
            <SubtabBody id={s.id} date={anchor} />
          </section>
        ))}
      </section>
    );
  }

  return (
    <section className="w-[calc(100vw-1.5rem)] -translate-x-1/2 relative left-1/2 space-y-4">
      <div className="flex flex-wrap items-start gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white">Tab 9 · Daily Extendido</h1>
          <p className="text-xs text-white/50">Daily Revenue Report completo (formato profesional), réplica página por página. COWLCR.</p>
        </div>
        <button onClick={() => setPrinting(true)}
          className="ml-auto rounded bg-white/10 px-3 py-1.5 text-[11px] text-white/80 hover:bg-white/20"
          title="Arma el reporte completo (todas las secciones habilitadas) en una sola vista lista para imprimir o guardar como PDF">
          🖨 Imprimir 9.1–9.8
        </button>
      </div>
      <nav className="flex flex-wrap gap-1 border-b border-white/10 pb-2">
        {SUBTABS.map((s) => (
          <button key={s.id} onClick={() => setTab(s.id)}
            className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "bg-[#1E2130] text-white/60 hover:text-white"}`}>
            {s.label}
          </button>
        ))}
      </nav>
      <SubtabBody id={tab} date={anchor} />
    </section>
  );
}
