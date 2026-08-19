"use client";

import { useEffect, useState } from "react";
import PeriodTabs from "@/components/PeriodTabs";
import { periodRange, PeriodKey } from "@/lib/periods";
import { API_URL } from "@/lib/api";

type Row = {
  market_code: string; description: string | null; market_group: string;
  pax: number; rooms: number; room_revenue: number; revenue_total: number;
};
type Total = { pax: number; rooms: number; room_revenue: number; revenue_total: number };
type Group = { group: string; pax: number; rooms: number; room_revenue: number; revenue_total: number };
type Data = { date_from: string; date_to: string; rows: Row[]; total: Total; groups: Group[] };

const usd = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 });

const bTh = "px-4 py-3 text-left font-medium text-ink/70 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-ink/70 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-ink/85";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-ink/85";

export default function MarketCodesPeriodTable({ anchor }: { anchor: string }) {
  const [period, setPeriod] = useState<PeriodKey>("today");
  const { from, to } = periodRange(period, anchor);
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let live = true; setLoading(true); setErr("");
    fetch(`${API_URL}/market-codes?date_from=${from}&date_to=${to}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { if (!live) return; if (d.detail) setErr(d.detail); else setData(d); })
      .catch((e) => live && setErr(String(e)))
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [from, to]);

  return (
    <div className="space-y-3">
      <PeriodTabs value={period} onChange={setPeriod} />
      <p className="text-[11px] text-ink/55">
        {from} → {to} · <span className="text-ink/70">Rooms</span> y <span className="text-ink/70">Pax</span> del XML STATISTICS;
        {" "}<span className="text-ink/70">Room Revenue</span> (Accommodation) y <span className="text-ink/70">Revenue Total</span> (todo lo REVENUE)
        {" "}del XML de Revenue, por market code. Total abajo.
      </p>
      {loading && <div className="text-xs text-ink/55">Loading…</div>}
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">{err}</div>}

      {data && (
        <div className="max-h-[600px] overflow-auto rounded-xl border border-ink/10 shadow-lg">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gradient-to-r from-[#dfeafc] to-[#fcfcfb]">
              <tr>
                <th className={bTh}>Market Code</th>
                <th className={bTh}>Description</th>
                <th className={bTh}>Market Group</th>
                <th className={bThN}>Pax</th>
                <th className={bThN}>Rooms</th>
                <th className={bThN}>Room Revenue</th>
                <th className={bThN}>Revenue Total</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.market_code} className="border-t border-ink/8">
                  <td className={`${bTd} font-medium`}>{r.market_code}</td>
                  <td className={bTd}>{r.description ?? <span className="text-ink/45">—</span>}</td>
                  <td className={bTd}>
                    <span className={r.market_group === "Unmapped" ? "text-amber-700/80" : "text-ink/75"}>{r.market_group}</span>
                  </td>
                  <td className={bTdN}>{intFmt(r.pax)}</td>
                  <td className={bTdN}>{intFmt(r.rooms)}</td>
                  <td className={bTdN}>${usd(r.room_revenue)}</td>
                  <td className={`${bTdN} font-medium`}>${usd(r.revenue_total)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-ink/20 bg-[#fcfcfb] font-bold">
                <td className={bTd} colSpan={3}>TOTAL</td>
                <td className={bTdN}>{intFmt(data.total.pax)}</td>
                <td className={bTdN}>{intFmt(data.total.rooms)}</td>
                <td className={bTdN}>${usd(data.total.room_revenue)}</td>
                <td className={bTdN}>${usd(data.total.revenue_total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <>
          <div className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-ink/60">By Market Group</div>
          <p className="text-[11px] text-ink/55">
            Direct = DIR/WEB/BAR · OTA = OTA · Travel Agency = TAFIT/TAGP/TA · Groups = FNF/RET/SOC/WED · Other = el resto (el total cierra con la tabla de arriba).
          </p>
          <div className="overflow-auto rounded-xl border border-ink/10 shadow-lg">
            <table className="w-full text-sm">
              <thead className="bg-gradient-to-r from-[#dfeafc] to-[#fcfcfb]">
                <tr>
                  <th className={bTh}>Market Group</th>
                  <th className={bThN}>Pax</th>
                  <th className={bThN}>Rooms</th>
                  <th className={bThN}>Room Revenue</th>
                  <th className={bThN}>Revenue Total</th>
                </tr>
              </thead>
              <tbody>
                {data.groups.map((g) => (
                  <tr key={g.group} className="border-t border-ink/8">
                    <td className={`${bTd} font-medium`}>{g.group}</td>
                    <td className={bTdN}>{intFmt(g.pax)}</td>
                    <td className={bTdN}>{intFmt(g.rooms)}</td>
                    <td className={bTdN}>${usd(g.room_revenue)}</td>
                    <td className={`${bTdN} font-medium`}>${usd(g.revenue_total)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-ink/20 bg-[#fcfcfb] font-bold">
                  <td className={bTd}>TOTAL</td>
                  <td className={bTdN}>{intFmt(data.total.pax)}</td>
                  <td className={bTdN}>{intFmt(data.total.rooms)}</td>
                  <td className={bTdN}>${usd(data.total.room_revenue)}</td>
                  <td className={bTdN}>${usd(data.total.revenue_total)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
