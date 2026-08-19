"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { usd, valueColor } from "@/lib/fmt";

type MonthRow = {
  month: string;
  days_loaded: number;
  cards_crc: number; cards_usd: number;
  transfers_crc: number; transfers_usd: number;
  cash_crc: number; cash_usd: number;
  sinpe_crc: number; sinpe_usd: number;
  non_cash_usd: number;
  total_real_cash_usd: number; total_non_cash_usd: number; total_usd: number;
  unmapped_currency: { tcode: string; amount_usd: number }[];
};
type MonthlySummary = { year: number; property: string; months: MonthRow[]; ytd: MonthRow };

// Montos en su moneda NATIVA (no convertidos) -- Cards CRC y Cards USD son
// tcodes distintos (dim_payment_map.moneda), no la misma transacción dos veces.
const crc = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `₡${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const th = "px-3 py-2 text-left font-medium text-ink/70 whitespace-nowrap";
const thN = "px-3 py-2 text-right font-medium text-ink/70 whitespace-nowrap";
const td = "px-3 py-1.5 text-ink/85 whitespace-nowrap";
const tdN = "px-3 py-1.5 text-right tabular-nums text-ink/85 whitespace-nowrap";

export default function CashMonthlySummary() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<MonthlySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/cash/monthly-summary?year=${year}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setData(null); setMsg(`Error: ${e.message}`);
    } finally { setLoading(false); }
  }, [year]);

  useEffect(() => { load(); }, [load]);

  const unmappedCurrency = (data?.months.flatMap((m) => m.unmapped_currency) ?? [])
    .concat(data?.ytd.unmapped_currency ?? []);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-ink/75">
          Year:
          <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value, 10) || year)}
            className="w-24 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
      </div>
      <p className="text-[11px] text-ink/55">
        Cards / Transfers / Cash / SINPE in their native transaction currency (never converted) — built
        day by day from real ingested Integrity data, same source as the rest of Tab 5. A month with no
        ingested days shows $0.00, same as any other view before data is loaded.
      </p>

      {loading && <div className="text-xs text-ink/55">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}

      {unmappedCurrency.length > 0 && (
        <div className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700/80">
          ⚠ {unmappedCurrency.length} payment line(s) with a TCode whose currency (dim_payment_map.moneda)
          is neither CRC nor USD — amount included in the USD column so it isn't lost, but the mapping
          should be reviewed: {unmappedCurrency.map((u) => u.tcode).join(", ")}
        </div>
      )}

      {data && (
        <>
          <div className="overflow-x-auto rounded-lg border border-ink/10">
            <table className="w-full text-sm">
              <thead className="bg-[#fcfcfb]">
                <tr>
                  <th className={th}>Month</th>
                  <th className={thN}>Cards CRC</th>
                  <th className={thN}>Cards USD</th>
                  <th className={thN}>Transfers CRC</th>
                  <th className={thN}>Transfers USD</th>
                  <th className={thN}>Cash CRC</th>
                  <th className={thN}>Cash USD</th>
                  <th className={thN}>SINPE CRC</th>
                  <th className={thN}>SINPE USD</th>
                  <th className={thN}>Non-Cash USD</th>
                  <th className={thN}>Total Real Cash USD</th>
                  <th className={thN}>Total Non-Cash USD</th>
                  <th className={thN}>Total USD</th>
                </tr>
              </thead>
              <tbody>
                {data.months.map((m) => (
                  <tr key={m.month} className="border-t border-ink/8">
                    <td className={td}>
                      {m.month}
                      {m.days_loaded === 0 && <span className="ml-1 text-ink/45">(no data)</span>}
                    </td>
                    <td className={`${tdN} ${valueColor(m.cards_crc)}`}>{crc(m.cards_crc)}</td>
                    <td className={`${tdN} ${valueColor(m.cards_usd)}`}>{usd(m.cards_usd)}</td>
                    <td className={`${tdN} ${valueColor(m.transfers_crc)}`}>{crc(m.transfers_crc)}</td>
                    <td className={`${tdN} ${valueColor(m.transfers_usd)}`}>{usd(m.transfers_usd)}</td>
                    <td className={`${tdN} ${valueColor(m.cash_crc)}`}>{crc(m.cash_crc)}</td>
                    <td className={`${tdN} ${valueColor(m.cash_usd)}`}>{usd(m.cash_usd)}</td>
                    <td className={`${tdN} ${valueColor(m.sinpe_crc)}`}>{crc(m.sinpe_crc)}</td>
                    <td className={`${tdN} ${valueColor(m.sinpe_usd)}`}>{usd(m.sinpe_usd)}</td>
                    <td className={`${tdN} ${valueColor(m.non_cash_usd)}`}>{usd(m.non_cash_usd)}</td>
                    <td className={`${tdN} font-medium ${valueColor(m.total_real_cash_usd)}`}>{usd(m.total_real_cash_usd)}</td>
                    <td className={`${tdN} font-medium ${valueColor(m.total_non_cash_usd)}`}>{usd(m.total_non_cash_usd)}</td>
                    <td className={`${tdN} font-bold ${valueColor(m.total_usd)}`}>{usd(m.total_usd)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                  <td className={td}>YTD TOTAL</td>
                  <td className={`${tdN} ${valueColor(data.ytd.cards_crc)}`}>{crc(data.ytd.cards_crc)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.cards_usd)}`}>{usd(data.ytd.cards_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.transfers_crc)}`}>{crc(data.ytd.transfers_crc)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.transfers_usd)}`}>{usd(data.ytd.transfers_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.cash_crc)}`}>{crc(data.ytd.cash_crc)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.cash_usd)}`}>{usd(data.ytd.cash_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.sinpe_crc)}`}>{crc(data.ytd.sinpe_crc)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.sinpe_usd)}`}>{usd(data.ytd.sinpe_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.non_cash_usd)}`}>{usd(data.ytd.non_cash_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.total_real_cash_usd)}`}>{usd(data.ytd.total_real_cash_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.total_non_cash_usd)}`}>{usd(data.ytd.total_non_cash_usd)}</td>
                  <td className={`${tdN} ${valueColor(data.ytd.total_usd)}`}>{usd(data.ytd.total_usd)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Resumen Mensual USD</div>
            <div className="max-w-md overflow-x-auto rounded-lg border border-ink/10">
              <table className="w-full text-sm">
                <thead className="bg-[#fcfcfb]">
                  <tr>
                    <th className={th}>Mes</th>
                    <th className={thN}>Real Cash USD</th>
                    <th className={thN}>Non-Cash USD</th>
                    <th className={thN}>Total USD</th>
                  </tr>
                </thead>
                <tbody>
                  {data.months.map((m) => (
                    <tr key={m.month} className="border-t border-ink/8">
                      <td className={td}>{m.month}</td>
                      <td className={`${tdN} ${valueColor(m.total_real_cash_usd)}`}>{usd(m.total_real_cash_usd)}</td>
                      <td className={`${tdN} ${valueColor(m.total_non_cash_usd)}`}>{usd(m.total_non_cash_usd)}</td>
                      <td className={`${tdN} font-medium ${valueColor(m.total_usd)}`}>{usd(m.total_usd)}</td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                    <td className={td}>YTD TOTAL</td>
                    <td className={`${tdN} ${valueColor(data.ytd.total_real_cash_usd)}`}>{usd(data.ytd.total_real_cash_usd)}</td>
                    <td className={`${tdN} ${valueColor(data.ytd.total_non_cash_usd)}`}>{usd(data.ytd.total_non_cash_usd)}</td>
                    <td className={`${tdN} ${valueColor(data.ytd.total_usd)}`}>{usd(data.ytd.total_usd)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
