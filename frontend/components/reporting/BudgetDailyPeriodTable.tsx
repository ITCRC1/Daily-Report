"use client";

import { useState } from "react";
import PeriodTabs from "@/components/PeriodTabs";
import { periodRange, PeriodKey } from "@/lib/periods";
import { useReportQuery } from "@/lib/useReportQuery";
import { useForceRefresh } from "@/lib/forceRefresh";
import { usd, valueColor } from "@/lib/fmt";

type Row = { date: string; dept_code: string | null; dept_name: string | null; amount_usd: number };

const COLUMNS = ["date", "dept_code", "dept_name", "amount_usd"];

const bTh = "px-4 py-3 text-left font-medium text-ink/70 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-ink/70 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-ink/85";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-ink/85";

export default function BudgetDailyPeriodTable({ anchor }: { anchor: string }) {
  const [period, setPeriod] = useState<PeriodKey>("today");
  const { token, forceRefresh, lastRefreshedAt } = useForceRefresh();
  const { from, to } = periodRange(period, anchor);
  const { rows, loading, error } = useReportQuery<Row>("budget_daily", COLUMNS, from, to, token);

  const depts = [...new Set(rows.map((r) => r.dept_code ?? "—"))].sort();
  const deptNames = new Map<string, string>();
  for (const r of rows) if (r.dept_code) deptNames.set(r.dept_code, r.dept_name ?? "");
  const byDate = new Map<string, Record<string, number>>();
  for (const r of rows) {
    const entry = byDate.get(r.date) ?? {};
    entry[r.dept_code ?? "—"] = r.amount_usd;
    byDate.set(r.date, entry);
  }
  const dates = [...byDate.keys()].sort();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PeriodTabs value={period} onChange={setPeriod} />
        <div className="flex items-center gap-2 text-[11px] text-ink/60">
          {lastRefreshedAt && <span>Last refreshed: {lastRefreshedAt}</span>}
          <button onClick={forceRefresh}
            className="rounded bg-ink/5 px-2.5 py-1 text-[11px] text-ink/75 hover:bg-ink/8 hover:text-ink">
            🔄 Force Recalculate
          </button>
        </div>
      </div>
      <p className="text-[11px] text-ink/60">
        {from} → {to} · Daily Budget derived from Tab 6.1 (fact_budget), reads live -- no cache.
      </p>
      {loading && <div className="text-xs text-ink/60">Loading…</div>}
      {error && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">{error}</div>}

      {dates.length > 0 ? (
        <div className="max-h-[600px] overflow-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[#fcfcfb]">
              <tr>
                <th className={bTh}>Day</th>
                {depts.map((d) => <th key={d} className={bThN}>{d}{deptNames.get(d) ? ` · ${deptNames.get(d)}` : ""}</th>)}
                <th className={bThN}>Total</th>
              </tr>
            </thead>
            <tbody>
              {dates.map((d) => {
                const rowData = byDate.get(d)!;
                const total = Object.values(rowData).reduce((a, b) => a + b, 0);
                return (
                  <tr key={d} className="border-t border-ink/8">
                    <td className={bTd}>{d}</td>
                    {depts.map((dept) => <td key={dept} className={`${bTdN} ${valueColor(rowData[dept] ?? 0)}`}>{rowData[dept] ? usd(rowData[dept]) : <span className="text-ink/45">—</span>}</td>)}
                    <td className={`${bTdN} font-medium ${valueColor(total)}`}>{usd(total)}</td>
                  </tr>
                );
              })}
              <tr className="sticky bottom-0 border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={bTd}>TOTAL</td>
                {depts.map((dept) => {
                  const deptTotal = dates.reduce((a, d) => a + (byDate.get(d)![dept] ?? 0), 0);
                  return <td key={dept} className={`${bTdN} ${valueColor(deptTotal)}`}>{usd(deptTotal)}</td>;
                })}
                <td className={`${bTdN} ${valueColor(dates.reduce((a, d) => a + Object.values(byDate.get(d)!).reduce((x, y) => x + y, 0), 0))}`}>
                  {usd(dates.reduce((a, d) => a + Object.values(byDate.get(d)!).reduce((x, y) => x + y, 0), 0))}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <div className="rounded-lg border border-dashed border-ink/12 bg-[#fcfcfb]/50 p-4 text-xs text-ink/60">
          No derived daily budget for {from} → {to}.
        </div>
      )}
    </div>
  );
}
