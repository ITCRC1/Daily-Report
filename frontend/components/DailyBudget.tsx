"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

type BudgetDailyRow = {
  date: string; dept_code: string | null; dept_name: string | null; amount_usd: number;
};

const MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const money = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const valueColor = (v: number) => (v < 0 ? "!text-rose-400" : "");
const bTh = "px-4 py-3 text-left font-medium text-white/60 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-white/60 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-white/80";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-white/80";

export default function DailyBudget() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [rows, setRows] = useState<BudgetDailyRow[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/master-data/budget/daily?year=${year}&month=${month}`, { cache: "no-store" });
      setRows(res.ok ? await res.json() : []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => { load(); }, [load]);

  const depts = [...new Set(rows.map((r) => r.dept_code ?? "—"))].sort();
  const deptNames = new Map<string, string>();
  for (const r of rows) if (r.dept_code) deptNames.set(r.dept_code, r.dept_name ?? "");
  const byDate = new Map<string, Record<string, number>>();
  for (const r of rows) {
    const key = r.date;
    const entry = byDate.get(key) ?? {};
    entry[r.dept_code ?? "—"] = r.amount_usd;
    byDate.set(key, entry);
  }
  const dates = [...byDate.keys()].sort();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-white/70">
          Year: <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value, 10) || year)}
            className="w-24 rounded border border-white/15 bg-[#0F1118] px-2 py-1 text-white" />
        </label>
        <label className="flex items-center gap-2 text-xs text-white/70">
          Month:
          <select value={month} onChange={(e) => setMonth(parseInt(e.target.value, 10))}
            className="rounded border border-white/15 bg-[#0F1118] px-2 py-1 text-white">
            {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </label>
      </div>
      <p className="text-[11px] text-white/40">
        Automatically derived from 6.1 (monthly ÷ days in the month, residual on the last day, §3) — not
        edited here directly.
      </p>
      {loading && <div className="text-xs text-white/40">Loading…</div>}
      {dates.length > 0 ? (
        <div className="max-h-[600px] overflow-auto rounded-lg border border-white/10">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[#1E2130]">
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
                  <tr key={d} className="border-t border-white/5">
                    <td className={bTd}>{d}</td>
                    {depts.map((dept) => <td key={dept} className={`${bTdN} ${valueColor(rowData[dept] ?? 0)}`}>{rowData[dept] ? `$${money(rowData[dept])}` : <span className="text-white/25">—</span>}</td>)}
                    <td className={`${bTdN} font-medium ${valueColor(total)}`}>${money(total)}</td>
                  </tr>
                );
              })}
              <tr className="sticky bottom-0 border-t-2 border-white/20 bg-[#1E2130] font-bold">
                <td className={bTd}>TOTAL</td>
                {depts.map((dept) => {
                  const deptTotal = dates.reduce((a, d) => a + (byDate.get(d)![dept] ?? 0), 0);
                  return <td key={dept} className={`${bTdN} ${valueColor(deptTotal)}`}>${money(deptTotal)}</td>;
                })}
                <td className={`${bTdN} ${valueColor(dates.reduce((a, d) => a + Object.values(byDate.get(d)!).reduce((x, y) => x + y, 0), 0))}`}>
                  ${money(dates.reduce((a, d) => a + Object.values(byDate.get(d)!).reduce((x, y) => x + y, 0), 0))}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <div className="rounded-lg border border-dashed border-white/15 bg-[#1E2130]/50 p-4 text-xs text-white/50">
          No derived daily budget for {MESES[month - 1]} {year} — load the monthly one in 6.1 first.
        </div>
      )}
    </div>
  );
}
