"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { usd, valueColor } from "@/lib/fmt";

type Row = {
  date: string; collected_usd: number; paid_usd: number; balance_usd: number;
  note: string | null; ingested: boolean;
};
type LedgerRange = { start: string; end: string; opening_balance: number; closing_balance: number; rows: Row[] };
type TodayMtd = {
  business_date: string;
  today: { collected_usd: number; paid_usd: number };
  mtd: { collected_usd: number; paid_usd: number };
  balance_usd: number;
};

const EARLIEST = "2026-07-01";

const th = "px-3 py-2 text-left font-medium text-ink/70 whitespace-nowrap";
const thN = "px-3 py-2 text-right font-medium text-ink/70 whitespace-nowrap";
const td = "px-3 py-1.5 text-ink/85 whitespace-nowrap";
const tdEmpty = "px-3 py-1.5";
const numInput = "w-28 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-right text-ink disabled:border-ink/8 disabled:bg-transparent disabled:text-ink/70";

function Kpi({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-4">
      <div className={`text-2xl font-bold ${tone || "text-ink"}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-ink/60">{label}</div>
    </div>
  );
}

export default function TipsLedger({ anchor: businessDate, kind, description }: {
  anchor: string; kind: string; description: string;
}) {
  const readOnly = kind === "all";
  const [kpis, setKpis] = useState<TodayMtd | null>(null);
  const [from, setFrom] = useState(EARLIEST);
  const [to, setTo] = useState(businessDate);
  const [data, setData] = useState<LedgerRange | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [paidDrafts, setPaidDrafts] = useState<Record<string, string>>({});
  const [savingDate, setSavingDate] = useState<string | null>(null);

  const loadKpis = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/tips/${kind}/today-mtd?business_date=${businessDate}`, { cache: "no-store" });
      if (res.ok) setKpis(await res.json());
    } catch { setKpis(null); }
  }, [kind, businessDate]);

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/tips/${kind}?date_from=${from}&date_to=${to}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const json: LedgerRange = await res.json();
      setData(json);
      const notes: Record<string, string> = {};
      const paid: Record<string, string> = {};
      for (const r of json.rows) { notes[r.date] = r.note ?? ""; paid[r.date] = String(r.paid_usd); }
      setNoteDrafts(notes); setPaidDrafts(paid);
    } catch (e: any) {
      setData(null); setMsg(`Error: ${e.message}`);
    } finally { setLoading(false); }
  }, [kind, from, to]);

  useEffect(() => { loadKpis(); }, [loadKpis]);
  useEffect(() => { load(); }, [load]);

  async function savePayout(date: string) {
    setSavingDate(date); setMsg("");
    try {
      const res = await fetch(`${API_URL}/tips/${kind}/payout/${date}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paid_usd: parseFloat(paidDrafts[date]) || 0,
          note: (noteDrafts[date] ?? "").trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      await Promise.all([load(), loadKpis()]);
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
    finally { setSavingDate(null); }
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-ink/60">{description}</p>

      {kpis && (
        <div className="grid grid-cols-3 gap-3">
          <Kpi label="Today · Collected" value={usd(kpis.today.collected_usd)} tone="text-emerald-600" />
          <Kpi label="Today · Paid" value={usd(kpis.today.paid_usd)} />
          <Kpi label={readOnly ? "MTD Balance (both combined)" : "MTD Balance (pending payout)"}
            value={usd(kpis.balance_usd)} tone={valueColor(kpis.balance_usd) || "text-sky-600"} />
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-ink/75">
          From
          <input type="date" value={from} min={EARLIEST} onChange={(e) => setFrom(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink/75">
          To
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
      </div>

      {loading && <div className="text-xs text-ink/60">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}

      {data && (
        <div className="overflow-x-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="bg-[#fcfcfb]">
              <tr>
                <th className={th}>Date</th>
                <th className={thN}>Collected</th>
                <th className={thN}>Paid</th>
                <th className={thN}>Balance</th>
                <th className={th}>Note</th>
                {!readOnly && <th className={th}></th>}
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-ink/8 bg-[#fcfcfb]/40 text-ink/60">
                <td className={td}>Opening ({from})</td>
                <td className={tdEmpty}></td>
                <td className={tdEmpty}></td>
                <td className={`${thN} ${valueColor(data.opening_balance)}`}>{usd(data.opening_balance)}</td>
                <td className={td} colSpan={readOnly ? 1 : 2}></td>
              </tr>
              {data.rows.map((r) => (
                <tr key={r.date} className="border-t border-ink/8">
                  <td className={td}>{r.date}{!r.ingested && <span className="ml-1 text-ink/45">(no audit)</span>}</td>
                  <td className={thN}>{usd(r.collected_usd)}</td>
                  <td className={thN}>
                    {readOnly ? usd(r.paid_usd) : (
                      <input type="number" step="0.01" value={paidDrafts[r.date] ?? ""}
                        placeholder="0.00"
                        onChange={(e) => setPaidDrafts((p) => ({ ...p, [r.date]: e.target.value }))}
                        className={numInput} />
                    )}
                  </td>
                  <td className={`${thN} font-medium ${valueColor(r.balance_usd)}`}>{usd(r.balance_usd)}</td>
                  <td className={td}>
                    {readOnly ? (noteDrafts[r.date] || "") : (
                      <input type="text" value={noteDrafts[r.date] ?? ""}
                        onChange={(e) => setNoteDrafts((p) => ({ ...p, [r.date]: e.target.value }))}
                        placeholder="optional note"
                        className="w-48 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
                    )}
                  </td>
                  {!readOnly && (
                    <td className={td}>
                      <button onClick={() => savePayout(r.date)} disabled={savingDate === r.date}
                        className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:bg-ink/8 disabled:opacity-40">
                        {savingDate === r.date ? "…" : "💾 Save"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={td}>Closing ({to})</td>
                <td className={tdEmpty}></td>
                <td className={tdEmpty}></td>
                <td className={`${thN} ${valueColor(data.closing_balance)}`}>{usd(data.closing_balance)}</td>
                <td className={td} colSpan={readOnly ? 1 : 2}></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
