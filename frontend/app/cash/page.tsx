"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import ExcelButton from "@/components/ExcelButton";
import { useBusinessDate } from "@/lib/useBusinessDate";
import { useSubtabs } from "@/lib/useSubtabs";
import CashMonthlySummary from "@/components/CashMonthlySummary";
import CashMonthlyPosition from "@/components/CashMonthlyPosition";
import CashFlowForecast from "@/components/CashFlowForecast";

type Split = Record<string, { real: number; non: number }>;
type Pivot = {
  total: number; real_cash: number; non_cash: number;
  cash_relevant_total: number; bank_only_total: number;
  by_bucket: Record<string, number>; by_bank: Record<string, number>;
  by_brand: Record<string, number>; by_channel: Record<string, number>;
  by_bucket_split?: Split; by_bank_split?: Split;
  by_brand_split?: Split; by_channel_split?: Split;
};
type Unmapped = { tcode: string; description: string | null; opera_total: number };
type CashReport = {
  business_date: string; days_loaded_mtd: number;
  today: Pivot; mtd: Pivot;
  unmapped_today: Unmapped[]; unmapped_mtd: Unmapped[];
};
type CashWeeklyReport = {
  business_date: string;
  week: { iso_week: number; week_start: string; week_end: string; label: string };
  days_loaded_week: number; days_loaded_ytd: number;
  weekly: Pivot; ytd: Pivot;
  unmapped_weekly: Unmapped[]; unmapped_ytd: Unmapped[];
};

const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const th = "px-3 py-2 text-left font-medium text-ink/70";
const thN = "px-3 py-2 text-right font-medium text-ink/70";
const td = "px-3 py-1.5 text-ink/85";
const tdN = "px-3 py-1.5 text-right tabular-nums text-ink/85";

const valueColor = (v: number | null | undefined) =>
  v !== null && v !== undefined && v < 0 ? "!text-rose-600" : "";

function Kpi({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-4">
      <div className={`text-2xl font-bold ${tone || "text-ink"}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-ink/60">{label}</div>
    </div>
  );
}

function BreakdownTable({ title, rows }: { title: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((a, [, v]) => a + v, 0);
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">{title}</div>
      {entries.length === 0 ? (
        <div className="rounded-lg border border-ink/10 bg-[#fcfcfb]/50 p-3 text-xs text-ink/60">No activity.</div>
      ) : (
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k} className="border-t border-ink/8 first:border-t-0">
                <td className={td}>{k}</td>
                <td className={`${tdN} ${valueColor(v)}`}>${money(v)}</td>
              </tr>
            ))}
            <tr className="border-t border-ink/15 bg-[#fcfcfb] font-bold">
              <td className={td}>Total</td>
              <td className={`${tdN} ${valueColor(total)}`}>${money(total)}</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

function UnmappedBlock({ rows }: { rows: Unmapped[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-amber-600">⚠ Unmapped payment TCodes (UNMAPPED, §5.5)</div>
      <table className="w-full text-xs">
        <thead><tr>{["TCode", "Description", "Opera Total"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((u) => (
            <tr key={u.tcode} className="border-t border-ink/8">
              <td className="px-3 py-1 font-mono text-ink/85">{u.tcode}</td>
              <td className={td}>{u.description}</td>
              <td className={`${tdN} ${valueColor(u.opera_total) || "text-amber-600"}`}>${money(u.opera_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SplitTable({ title, rows }: { title: string; rows: Split }) {
  const entries = Object.entries(rows)
    .filter(([, v]) => Math.abs(v.real) > 0.005 || Math.abs(v.non) > 0.005)
    .sort((a, b) => (b[1].real - a[1].real) || (b[1].non - a[1].non));
  const totReal = entries.reduce((a, [, v]) => a + v.real, 0);
  const totNon = entries.reduce((a, [, v]) => a + v.non, 0);
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">{title}</div>
      {entries.length === 0 ? (
        <div className="rounded-lg border border-ink/10 bg-[#fcfcfb]/50 p-3 text-xs text-ink/60">No activity.</div>
      ) : (
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead>
            <tr>
              <th className={th}></th>
              <th className={thN}>Real Cash</th>
              <th className={thN}>No-Cash</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([k, v]) => {
              const isReal = Math.abs(v.real) > 0.005;
              return (
                <tr key={k} className="border-t border-ink/8">
                  <td className={td}>
                    {k}
                    {!isReal && <span className="ml-2 rounded bg-ink/5 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-ink/60">excluido</span>}
                  </td>
                  <td className={`${tdN} ${v.real ? "text-emerald-600" : "text-ink/40"}`}>{v.real ? `$${money(v.real)}` : "—"}</td>
                  <td className={`${tdN} ${v.non ? "text-ink/70" : "text-ink/40"}`}>{v.non ? `$${money(v.non)}` : "—"}</td>
                </tr>
              );
            })}
            <tr className="border-t border-ink/15 bg-[#fcfcfb] font-bold">
              <td className={td}>Total</td>
              <td className={`${tdN} text-emerald-600`}>${money(totReal)}</td>
              <td className={`${tdN} text-ink/70`}>${money(totNon)}</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

function RealCashComposition({ p }: { p: Pivot }) {
  const [open, setOpen] = useState(true);
  if (!p.by_bucket_split) return null; // backend viejo sin splits
  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between text-left">
        <div>
          <h3 className="text-sm font-semibold text-emerald-700">🔍 Composición del Real Cash</h3>
          <p className="text-[11px] text-ink/60">
            Qué líneas suman los <b className="text-emerald-600">${money(p.real_cash)}</b> de Real Cash —
            y qué queda <span className="text-ink/70">excluido como No-Cash (${money(p.non_cash)})</span>:
            cuentas por cobrar (AR) y cargos internos. Referencia para el ajuste en 5.2.
          </p>
        </div>
        <span className="text-ink/60">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SplitTable title="Por bucket (report_bucket)" rows={p.by_bucket_split} />
          {p.by_channel_split && <SplitTable title="Por canal" rows={p.by_channel_split} />}
        </div>
      )}
    </div>
  );
}

function PivotSection({ label, p }: { label: string; p: Pivot }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-3">
        <Kpi label={`${label} · Real Cash`} value={`$${money(p.real_cash)}`} tone={valueColor(p.real_cash) || "text-emerald-600"} />
        <Kpi label="Non-Cash" value={`$${money(p.non_cash)}`} tone={valueColor(p.non_cash) || "text-ink/70"} />
        <Kpi label="Cash-relevant (broad)" value={`$${money(p.cash_relevant_total)}`} tone={valueColor(p.cash_relevant_total) || "text-sky-600"} />
        <Kpi label="Bank-only (strict)" value={`$${money(p.bank_only_total)}`} tone={valueColor(p.bank_only_total) || "text-amber-600"} />
      </div>
      <RealCashComposition p={p} />
      <div className="grid grid-cols-2 gap-4">
        <BreakdownTable title="By bucket" rows={p.by_bucket} />
        <BreakdownTable title="By bank" rows={p.by_bank} />
        <BreakdownTable title="By brand/method" rows={p.by_brand} />
        <BreakdownTable title="By channel" rows={p.by_channel} />
      </div>
    </div>
  );
}

type TabId = "today" | "mtd" | "weekly" | "ytd";
const TAB_LABEL: Record<TabId, string> = { today: "Today", mtd: "MTD", weekly: "Weekly", ytd: "YTD" };

function DailyCashFromOperation() {
  const day = useBusinessDate();
  const [data, setData] = useState<CashReport | null>(null);
  const [weekData, setWeekData] = useState<CashWeeklyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [tab, setTab] = useState<TabId>("today");

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const [dailyRes, weeklyRes] = await Promise.all([
        fetch(`${API_URL}/cash/${day}`, { cache: "no-store" }),
        fetch(`${API_URL}/cash/weekly/${day}`, { cache: "no-store" }),
      ]);
      if (!dailyRes.ok) throw new Error(`API ${dailyRes.status}`);
      setData(await dailyRes.json());
      setWeekData(weeklyRes.ok ? await weeklyRes.json() : null);
    } catch {
      setData(null); setWeekData(null);
      setMsg(`No cash data for ${day}. Run ingestion in Tab 1 / Tab 2.`);
    } finally { setLoading(false); }
  }, [day]);

  useEffect(() => { load(); }, [load]);

  const pivotFor = (t: TabId): Pivot | null => {
    if (!data && !weekData) return null;
    if (t === "today") return data?.today ?? null;
    if (t === "mtd") return data?.mtd ?? null;
    if (t === "weekly") return weekData?.weekly ?? null;
    return weekData?.ytd ?? null;
  };
  const unmappedFor = (t: TabId): Unmapped[] => {
    if (t === "today") return data?.unmapped_today ?? [];
    if (t === "mtd") return data?.unmapped_mtd ?? [];
    if (t === "weekly") return weekData?.unmapped_weekly ?? [];
    return weekData?.unmapped_ytd ?? [];
  };
  const activePivot = pivotFor(tab);

  return (
    <div className="space-y-4">
      <p className="text-xs text-ink/60">
        Two-level buckets (§5.5) via dim_payment_map · {day}
        {data && ` · ${data.days_loaded_mtd} day(s) in MTD`}
        {weekData && ` · ${weekData.days_loaded_week} in the week (${weekData.week.label}) · ${weekData.days_loaded_ytd} in YTD`}
      </p>

      {loading && <div className="text-sm text-ink/60">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-3 text-sm text-ink/75">{msg}</div>}

      {data && (
        <>
          <nav className="flex gap-1 border-b border-ink/10 pb-2">
            {(Object.keys(TAB_LABEL) as TabId[]).map((t) => (
              <button key={t} onClick={() => setTab(t)} disabled={t !== "today" && t !== "mtd" && !weekData}
                className={`rounded px-3 py-1 text-xs disabled:opacity-30 ${tab === t ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
                {TAB_LABEL[t]}
              </button>
            ))}
          </nav>

          {activePivot && <PivotSection label={TAB_LABEL[tab]} p={activePivot} />}

          <UnmappedBlock rows={unmappedFor(tab)} />
        </>
      )}
    </div>
  );
}

const ALL_SUBTABS = [
  { id: "5", label: "5 · Daily Cash from Operation" },
  { id: "5.1", label: "5.1 · Monthly Summary (Currency Basis)" },
  { id: "5.2", label: "5.2 · Monthly Cash Position" },
];

export default function CashPage() {
  const { subtabs: SUBTABS, tab, setTab } = useSubtabs(ALL_SUBTABS, "5");
  const anchor = useBusinessDate();
  const fyear = Number(anchor.slice(0, 4)) || 2026;
  return (
    <section id="tab5-export" className="w-[calc(100vw-1.5rem)] -translate-x-1/2 relative left-1/2 space-y-4 px-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">Tab 5 · Cash</h1>
        </div>
        <ExcelButton target="tab5-export" filename={`Tab5_Cash_${tab}_${anchor}`}
          title={`Tab 5 · Cash — ${tab}`} subtitle={`Corcovado Wilderness Lodge · ${anchor}`} label="Excel" />
      </div>
      <nav className="flex flex-wrap gap-1 border-b border-ink/10 pb-2">
        {SUBTABS.map((s) => (
          <button key={s.id} onClick={() => setTab(s.id)}
            className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
            {s.label}
          </button>
        ))}
      </nav>
      {tab === "5" && <DailyCashFromOperation />}
      {tab === "5.1" && <CashMonthlySummary />}
      {tab === "5.2" && (
        <div className="flex flex-col gap-8 xl:flex-row xl:items-start">
          <div className="xl:shrink-0"><CashMonthlyPosition /></div>
          <div className="min-w-0 flex-1"><CashFlowForecast year={fyear} /></div>
        </div>
      )}
    </section>
  );
}
