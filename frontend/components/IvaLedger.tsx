"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { usd } from "@/lib/fmt";

type Row = { date: string; accrued_usd: number; accrued_crc: number; ingested: boolean };
type RangeView = { start: string; end: string; rows: Row[]; total_usd: number; total_crc: number };
type TodayMtd = {
  business_date: string;
  today: { accrued_usd: number; accrued_crc: number };
  mtd: { accrued_usd: number; accrued_crc: number };
};

const EARLIEST = "2026-07-01";

const crc = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `₡${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const th = "px-3 py-2 text-left font-medium text-white/60 whitespace-nowrap";
const thN = "px-3 py-2 text-right font-medium text-white/60 whitespace-nowrap";
const td = "px-3 py-1.5 text-white/80 whitespace-nowrap";

function Kpi({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-[#1E2130] p-4">
      <div className={`text-2xl font-bold ${tone || "text-white"}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-white/50">{label}</div>
    </div>
  );
}

export default function IvaLedger({ anchor: businessDate }: { anchor: string }) {
  const [kpis, setKpis] = useState<TodayMtd | null>(null);
  const [from, setFrom] = useState(EARLIEST);
  const [to, setTo] = useState(businessDate);
  const [data, setData] = useState<RangeView | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const loadKpis = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/iva/today-mtd?business_date=${businessDate}`, { cache: "no-store" });
      if (res.ok) setKpis(await res.json());
    } catch { setKpis(null); }
  }, [businessDate]);

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/iva?date_from=${from}&date_to=${to}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setData(null); setMsg(`Error: ${e.message}`);
    } finally { setLoading(false); }
  }, [from, to]);

  useEffect(() => { loadKpis(); }, [loadKpis]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-white/40">
        VAT accrued per day, real from Integrity (credits to "VAT - CREDITS (IVA DEVENGADO - INGRESOS) - 13%"
        — IVA 13% + IVA 13% POS), since 2026-07-01. Read-only — informational, for tax filing. Shown in both
        USD and CRC (IVA is declared/paid to Hacienda in colones).
      </p>

      {kpis && (
        <div className="grid grid-cols-2 gap-3">
          <Kpi label="Today" value={`${usd(kpis.today.accrued_usd)} · ${crc(kpis.today.accrued_crc)}`} tone="text-amber-400" />
          <Kpi label="MTD" value={`${usd(kpis.mtd.accrued_usd)} · ${crc(kpis.mtd.accrued_crc)}`} tone="text-amber-400" />
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-white/70">
          From
          <input type="date" value={from} min={EARLIEST} onChange={(e) => setFrom(e.target.value)}
            className="rounded border border-white/15 bg-[#0F1118] px-2 py-1 text-white" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-white/70">
          To
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="rounded border border-white/15 bg-[#0F1118] px-2 py-1 text-white" />
        </label>
      </div>

      {loading && <div className="text-xs text-white/40">Loading…</div>}
      {msg && <div className="rounded border border-white/10 bg-[#1E2130] p-2 text-xs text-white/70">{msg}</div>}

      {data && (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-[#1E2130]">
              <tr>
                <th className={th}>Date</th>
                <th className={thN}>IVA 13% (USD)</th>
                <th className={thN}>IVA 13% (CRC)</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.date} className="border-t border-white/5">
                  <td className={td}>{r.date}{!r.ingested && <span className="ml-1 text-white/25">(no audit)</span>}</td>
                  <td className={thN}>{usd(r.accrued_usd)}</td>
                  <td className={thN}>{crc(r.accrued_crc)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-white/20 bg-[#1E2130] font-bold">
                <td className={td}>Total ({from} → {to})</td>
                <td className={thN}>{usd(data.total_usd)}</td>
                <td className={thN}>{crc(data.total_crc)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
