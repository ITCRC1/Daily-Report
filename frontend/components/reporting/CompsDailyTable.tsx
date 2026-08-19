"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";

type CatVal = { category: string; rn: number; pax: number };
type Day = { date: string; by_cat: Record<string, { rn: number; pax: number }>; rn: number; pax: number };
type Data = {
  categories: string[];
  opening_label: string; opening: CatVal[]; opening_total: { rn: number; pax: number };
  daily: Day[];
  running: CatVal[]; running_total: { rn: number; pax: number };
};

const n = (v: number | undefined) => (v === undefined || v === null ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 0 }));
const bTh = "px-3 py-2.5 text-left font-medium text-ink/70 whitespace-nowrap";
const bThN = "px-3 py-2.5 text-right font-medium text-ink/70 whitespace-nowrap";
const bTd = "px-3 py-2 text-ink/85 whitespace-nowrap";
const bTdN = "px-3 py-2 text-right tabular-nums text-ink/85";

export default function CompsDailyTable() {
  const anchor = useBusinessDate();
  const year = Number(anchor.slice(0, 4)) || 2026;
  const [data, setData] = useState<Data | null>(null);
  const [metric, setMetric] = useState<"rn" | "pax">("rn");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const res = await fetch(`${API_URL}/comps/daily?year=${year}`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      setData(await res.json());
    } catch (e: any) { setErr(`No se pudo cargar (${e.message}).`); } finally { setLoading(false); }
  }, [year]);
  useEffect(() => { load(); }, [load]);

  const openByCat: Record<string, CatVal> = {};
  data?.opening.forEach((o) => (openByCat[o.category] = o));
  const runByCat: Record<string, CatVal> = {};
  data?.running.forEach((o) => (runByCat[o.category] = o));

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-ink/60">
        Control diario de comps / in-house por tipo de habitación. El <span className="text-amber-700">saldo de arranque</span> es
        el YTD a 30-Jun (Tab 7.8 = línea Comps de Tab 6.6, 243/346); cada día suma los comps reales del XML STATISTICS
        (COM/INHOUSE), y el acumulado corrido debe cuadrar con la línea Comps de 6.6.
      </p>
      <div className="flex items-center gap-1">
        {(["rn", "pax"] as const).map((m) => (
          <button key={m} onClick={() => setMetric(m)}
            className={`rounded px-2.5 py-1 text-[11px] ${metric === m ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
            {m === "rn" ? "Room Nights" : "Pax"}
          </button>
        ))}
      </div>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">{err}</div>}
      {loading && <div className="text-xs text-ink/60">Cargando…</div>}
      {data && (
        <div className="overflow-x-auto rounded-xl border border-ink/10 shadow-lg">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-[#dfeafc] to-[#fcfcfb]">
              <tr>
                <th className={bTh}>Día</th>
                {data.categories.map((c) => <th key={c} className={bThN}>{c}</th>)}
                <th className={bThN}>Total día</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-ink/10 bg-[#e8f0fb] font-bold text-emerald-700/90">
                <td className={bTd}>{data.opening_label} (arranque)</td>
                {data.categories.map((c) => <td key={c} className={bTdN}>{n(metric === "rn" ? openByCat[c]?.rn : openByCat[c]?.pax)}</td>)}
                <td className={bTdN}>{n(metric === "rn" ? data.opening_total.rn : data.opening_total.pax)}</td>
              </tr>
              {data.daily.map((d) => (
                <tr key={d.date} className="border-t border-ink/8">
                  <td className={bTd}>{d.date}</td>
                  {data.categories.map((c) => {
                    const v = d.by_cat[c]; const val = v ? (metric === "rn" ? v.rn : v.pax) : 0;
                    return <td key={c} className={bTdN}>{val ? n(val) : <span className="text-ink/40">—</span>}</td>;
                  })}
                  <td className={`${bTdN} font-medium`}>{n(metric === "rn" ? d.rn : d.pax)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-ink/20 bg-[#fcfcfb] font-bold">
                <td className={bTd}>ACUMULADO (arranque + días)</td>
                {data.categories.map((c) => <td key={c} className={bTdN}>{n(metric === "rn" ? runByCat[c]?.rn : runByCat[c]?.pax)}</td>)}
                <td className={bTdN}>{n(metric === "rn" ? data.running_total.rn : data.running_total.pax)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
