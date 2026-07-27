"use client";

import { useState } from "react";
import PeriodTabs from "@/components/PeriodTabs";
import { periodRange, PeriodKey } from "@/lib/periods";
import { useReportQuery } from "@/lib/useReportQuery";
import { useForceRefresh } from "@/lib/forceRefresh";
import { intFmt, pctFmt, usd, valueColor } from "@/lib/fmt";

type Row = {
  date: string; category: string; revenue: number;
  stay_rooms: number; stay_persons: number; physical_rooms: number;
};

const COLUMNS = ["date", "category", "revenue", "stay_rooms", "stay_persons", "physical_rooms"];

const bTh = "px-4 py-3 text-left font-medium text-white/60 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-white/60 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-white/80";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-white/80";

export default function RoomStatsPeriodTable({ anchor }: { anchor: string }) {
  const [period, setPeriod] = useState<PeriodKey>("today");
  const { token, forceRefresh, lastRefreshedAt } = useForceRefresh();
  const { from, to } = periodRange(period, anchor);
  const { rows, loading, error } = useReportQuery<Row>("room_stats", COLUMNS, from, to, token);

  const categories = [...new Set(rows.map((r) => r.category))];
  const byDate = new Map<string, Record<string, number>>();
  const rnByDate = new Map<string, Record<string, number>>();
  const availByDate = new Map<string, Record<string, number>>();
  const paxByDate = new Map<string, Record<string, number>>();
  for (const r of rows) {
    const rev = byDate.get(r.date) ?? {}; rev[r.category] = r.revenue; byDate.set(r.date, rev);
    const rn = rnByDate.get(r.date) ?? {}; rn[r.category] = r.stay_rooms; rnByDate.set(r.date, rn);
    const av = availByDate.get(r.date) ?? {}; av[r.category] = r.physical_rooms; availByDate.set(r.date, av);
    const px = paxByDate.get(r.date) ?? {}; px[r.category] = r.stay_persons; paxByDate.set(r.date, px);
  }
  const dates = [...byDate.keys()].sort();
  const grandTotal = dates.reduce((a, d) => a + Object.values(byDate.get(d)!).reduce((x, y) => x + y, 0), 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PeriodTabs value={period} onChange={setPeriod} />
        <div className="flex items-center gap-2 text-[11px] text-white/40">
          {lastRefreshedAt && <span>Last refreshed: {lastRefreshedAt}</span>}
          <button onClick={forceRefresh}
            className="rounded bg-white/10 px-2.5 py-1 text-[11px] text-white/70 hover:bg-white/20 hover:text-white">
            🔄 Force Recalculate
          </button>
        </div>
      </div>
      <p className="text-[11px] text-white/40">
        {from} → {to} · fact_room_stat + Tab 6.6 YTD anchor as of its own date, reads live -- no cache. RN/Pax netos de comps/in-house (COM/INHOUSE) → ADR correcto.
      </p>
      {loading && <div className="text-xs text-white/40">Loading…</div>}
      {error && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{error}</div>}

      {dates.length > 0 ? (
        <div className="max-h-[600px] overflow-auto rounded-lg border border-white/10">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[#1E2130]">
              <tr>
                <th className={bTh}>Day</th>
                {categories.map((c) => <th key={c} className={bThN}>{c}</th>)}
                <th className={bThN}>Total Revenue</th>
                <th className={bThN}>RN</th>
                <th className={bThN}>Pax</th>
                <th className={bThN}>Available</th>
                <th className={bThN}>Occ %</th>
                <th className={bThN}>ADR</th>
              </tr>
            </thead>
            <tbody>
              {dates.map((d) => {
                const rev = byDate.get(d)!;
                const rn = rnByDate.get(d) ?? {};
                const av = availByDate.get(d) ?? {};
                const px = paxByDate.get(d) ?? {};
                const total = Object.values(rev).reduce((a, b) => a + b, 0);
                const rnTotal = Object.values(rn).reduce((a, b) => a + b, 0);
                const availTotal = Object.values(av).reduce((a, b) => a + b, 0);
                const paxTotal = Object.values(px).reduce((a, b) => a + b, 0);
                const occPct = availTotal ? rnTotal / availTotal : null;
                const adr = rnTotal ? total / rnTotal : null;
                return (
                  <tr key={d} className="border-t border-white/5">
                    <td className={bTd}>{d}</td>
                    {categories.map((c) => <td key={c} className={`${bTdN} ${valueColor(rev[c] ?? 0)}`}>{rev[c] ? usd(rev[c]) : <span className="text-white/25">—</span>}</td>)}
                    <td className={`${bTdN} font-medium ${valueColor(total)}`}>{usd(total)}</td>
                    <td className={bTdN}>{intFmt(rnTotal)}</td>
                    <td className={bTdN}>{intFmt(paxTotal)}</td>
                    <td className={bTdN}>{intFmt(availTotal)}</td>
                    <td className={bTdN}>{occPct !== null ? pctFmt(occPct) : <span className="text-white/25">—</span>}</td>
                    <td className={`${bTdN} ${adr !== null ? valueColor(adr) : ""}`}>{adr !== null ? usd(adr) : <span className="text-white/25">—</span>}</td>
                  </tr>
                );
              })}
              <tr className="sticky bottom-0 border-t-2 border-white/20 bg-[#1E2130] font-bold">
                <td className={bTd}>TOTAL</td>
                {categories.map((c) => {
                  const catTotal = dates.reduce((a, d) => a + (byDate.get(d)?.[c] ?? 0), 0);
                  return <td key={c} className={`${bTdN} ${valueColor(catTotal)}`}>{usd(catTotal)}</td>;
                })}
                <td className={`${bTdN} ${valueColor(grandTotal)}`}>{usd(grandTotal)}</td>
                {(() => {
                  const rnTotal = dates.reduce((a, d) => a + Object.values(rnByDate.get(d) ?? {}).reduce((x, y) => x + y, 0), 0);
                  const paxTotal = dates.reduce((a, d) => a + Object.values(paxByDate.get(d) ?? {}).reduce((x, y) => x + y, 0), 0);
                  const availTotal = dates.reduce((a, d) => a + Object.values(availByDate.get(d) ?? {}).reduce((x, y) => x + y, 0), 0);
                  const occPct = availTotal ? rnTotal / availTotal : null;
                  const adr = rnTotal ? grandTotal / rnTotal : null;
                  return (
                    <>
                      <td className={bTdN}>{intFmt(rnTotal)}</td>
                      <td className={bTdN}>{intFmt(paxTotal)}</td>
                      <td className={bTdN}>{intFmt(availTotal)}</td>
                      <td className={bTdN}>{occPct !== null ? pctFmt(occPct) : "—"}</td>
                      <td className={`${bTdN} ${adr !== null ? valueColor(adr) : ""}`}>{adr !== null ? usd(adr) : "—"}</td>
                    </>
                  );
                })()}
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <div className="rounded-lg border border-dashed border-white/15 bg-[#1E2130]/50 p-4 text-xs text-white/50">
          No room stats for {from} → {to}.
        </div>
      )}
    </div>
  );
}
