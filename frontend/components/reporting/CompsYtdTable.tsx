"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";

type Cat = { category: string; rn: Record<string, number>; pax: Record<string, number>; rn_ytd: number; pax_ytd: number };
type Total = { rn: Record<string, number>; pax: Record<string, number>; rn_ytd: number; pax_ytd: number };
type Data = { year: number; months: number[]; categories: Cat[]; total: Total };

const MONTH_ES: Record<number, string> = { 1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic" };
const n = (v: number | undefined) => (v === undefined ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 0 }));

const bTh = "px-4 py-3 text-left font-medium text-ink/70 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-ink/70 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-ink/85";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-ink/85";

export default function CompsYtdTable() {
  const anchor = useBusinessDate();
  const year = Number(anchor.slice(0, 4)) || 2026;
  const [data, setData] = useState<Data | null>(null);
  const [metric, setMetric] = useState<"rn" | "pax">("rn");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const res = await fetch(`${API_URL}/comps/monthly?year=${year}`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      setData(await res.json());
    } catch (e: any) { setErr(`No se pudo cargar (${e.message}).`); } finally { setLoading(false); }
  }, [year]);
  useEffect(() => { load(); }, [load]);

  const ytdKey = metric === "rn" ? "rn_ytd" : "pax_ytd";

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-ink/60">
        Comps / In-House por tipo de habitación, mes a mes. Ene–Jun = histórico del Excel (arranque, reconcilia con
        la línea <span className="text-amber-700">Comps</span> del ancla de Tab 6.6 = 243 RN / 346 Pax); Jul en
        adelante se <span className="text-emerald-700">actualiza solo con la ingesta diaria</span> (cada comp cae en
        su mes y su tipo, del XML STATISTICS). Es el saldo de arranque del daily de Tab 7.9.
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
                <th className={bTh}>Room Type</th>
                {data.months.map((m) => <th key={m} className={bThN}>{MONTH_ES[m]}</th>)}
                <th className={bThN}>Total YTD</th>
              </tr>
            </thead>
            <tbody>
              {data.categories.map((c) => (
                <tr key={c.category} className="border-t border-ink/8">
                  <td className={bTd}>{c.category}</td>
                  {data.months.map((m) => <td key={m} className={bTdN}>{n((metric === "rn" ? c.rn : c.pax)[m])}</td>)}
                  <td className={`${bTdN} font-medium`}>{n((c as any)[ytdKey])}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-ink/20 bg-[#fcfcfb] font-bold">
                <td className={bTd}>TOTAL COMPS</td>
                {data.months.map((m) => <td key={m} className={bTdN}>{n((metric === "rn" ? data.total.rn : data.total.pax)[m])}</td>)}
                <td className={bTdN}>{n((data.total as any)[ytdKey])}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
