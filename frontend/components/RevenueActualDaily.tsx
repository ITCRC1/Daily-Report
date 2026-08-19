"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

type RevenueActualRow = {
  date: string; dept_code: string | null; dept_name: string | null; amount_usd: number;
  rooms_sold: number | null; total_pax: number | null; available_rooms: number | null;
};

const money = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const valueColor = (v: number) => (v < 0 ? "!text-rose-600" : "");
const bTh = "px-4 py-3 text-left font-medium text-ink/70 whitespace-nowrap";
const bThN = "px-4 py-3 text-right font-medium text-ink/70 whitespace-nowrap";
const bTd = "px-4 py-2.5 text-ink/85";
const bTdN = "px-4 py-2.5 text-right tabular-nums text-ink/85";

export default function RevenueActualDaily({ allowUpload = true }: { allowUpload?: boolean }) {
  const [rows, setRows] = useState<RevenueActualRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/master-data/revenue-actual`, { cache: "no-store" });
      setRows(res.ok ? await res.json() : []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function upload(file: File) {
    setUploading(true); setMsg("Uploading…");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/master-data/revenue-actual/upload`, { method: "POST", body: form });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setMsg(`Loaded: ${body.rows_loaded} rows, ${body.days_loaded} days (${body.date_range?.[0]} → ${body.date_range?.[1]}).`);
      await load();
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setUploading(false);
    }
  }

  const depts = [...new Set(rows.map((r) => r.dept_code ?? "—"))];
  const deptNames = new Map<string, string>();
  for (const r of rows) if (r.dept_code) deptNames.set(r.dept_code, r.dept_name ?? "");
  const byDate = new Map<string, Record<string, number>>();
  const paxByDate = new Map<string, { rooms_sold: number | null; total_pax: number | null; available_rooms: number | null }>();
  for (const r of rows) {
    const entry = byDate.get(r.date) ?? {};
    entry[r.dept_code ?? "—"] = r.amount_usd;
    byDate.set(r.date, entry);
    if (r.rooms_sold !== null || r.total_pax !== null || r.available_rooms !== null) {
      paxByDate.set(r.date, { rooms_sold: r.rooms_sold, total_pax: r.total_pax, available_rooms: r.available_rooms });
    }
  }
  const dates = [...byDate.keys()].sort();
  const grandTotal = dates.reduce((a, d) => a + Object.values(byDate.get(d)!).reduce((x, y) => x + y, 0), 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {allowUpload && (
          <label className="cursor-pointer rounded bg-accent px-3 py-1.5 text-xs font-medium text-ink">
            {uploading ? "Uploading…" : "📤 Upload daily grid (Actual)"}
            <input type="file" accept=".xlsx" className="hidden" disabled={uploading}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
          </label>
        )}
        {dates.length > 0 && (
          <span className="text-xs text-ink/60">
            Year to Date: {dates[0]} → {dates[dates.length - 1]} ({dates.length} days) · Total: <span className={valueColor(grandTotal)}>${money(grandTotal)}</span>
          </span>
        )}
      </div>
      {allowUpload && (
        <p className="text-[11px] text-ink/55">
          Bulk upload from an already-aggregated daily grid (the "Actual" sheet of the Weekly workbook, one
          day per row) — doesn&apos;t replace the real day-by-day ingestion (Tabs 1-2), it&apos;s a shortcut to
          backfill history. Only replaces the days present in the uploaded file.
        </p>
      )}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}
      {loading && <div className="text-xs text-ink/55">Loading…</div>}

      {dates.length > 0 ? (
        <div className="max-h-[700px] overflow-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[#fcfcfb]">
              <tr>
                <th className={bTh}>Day</th>
                {depts.map((d) => <th key={d} className={bThN}>{d}{deptNames.get(d) ? ` · ${deptNames.get(d)}` : ""}</th>)}
                <th className={bThN}>Total</th>
                <th className={bThN}>RN</th>
                <th className={bThN}>Pax</th>
                <th className={bThN}>Available</th>
                <th className={bThN}>% Occ.</th>
                <th className={bThN}>ADR</th>
              </tr>
            </thead>
            <tbody>
              {dates.map((d) => {
                const rowData = byDate.get(d)!;
                const total = Object.values(rowData).reduce((a, b) => a + b, 0);
                const pax = paxByDate.get(d);
                const rooms = rowData["0110"] ?? 0;
                const occPct = pax?.available_rooms ? (pax.rooms_sold ?? 0) / pax.available_rooms : null;
                const adr = pax?.rooms_sold ? rooms / pax.rooms_sold : null;
                return (
                  <tr key={d} className="border-t border-ink/8">
                    <td className={bTd}>{d}</td>
                    {depts.map((dept) => <td key={dept} className={`${bTdN} ${valueColor(rowData[dept] ?? 0)}`}>{rowData[dept] ? `$${money(rowData[dept])}` : <span className="text-ink/45">—</span>}</td>)}
                    <td className={`${bTdN} font-medium ${valueColor(total)}`}>${money(total)}</td>
                    <td className={bTdN}>{pax?.rooms_sold !== null && pax?.rooms_sold !== undefined ? intFmt(pax.rooms_sold) : <span className="text-ink/45">—</span>}</td>
                    <td className={bTdN}>{pax?.total_pax !== null && pax?.total_pax !== undefined ? intFmt(pax.total_pax) : <span className="text-ink/45">—</span>}</td>
                    <td className={bTdN}>{pax?.available_rooms !== null && pax?.available_rooms !== undefined ? intFmt(pax.available_rooms) : <span className="text-ink/45">—</span>}</td>
                    <td className={bTdN}>{occPct !== null ? `${(occPct * 100).toFixed(1)}%` : <span className="text-ink/45">—</span>}</td>
                    <td className={`${bTdN} ${adr !== null ? valueColor(adr) : ""}`}>{adr !== null ? `$${money(adr)}` : <span className="text-ink/45">—</span>}</td>
                  </tr>
                );
              })}
              <tr className="sticky bottom-0 border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={bTd}>TOTAL YTD</td>
                {depts.map((dept) => {
                  const deptTotal = dates.reduce((a, d) => a + (byDate.get(d)![dept] ?? 0), 0);
                  return <td key={dept} className={`${bTdN} ${valueColor(deptTotal)}`}>${money(deptTotal)}</td>;
                })}
                <td className={`${bTdN} ${valueColor(grandTotal)}`}>${money(grandTotal)}</td>
                {(() => {
                  const rnTotal = dates.reduce((a, d) => a + (paxByDate.get(d)?.rooms_sold ?? 0), 0);
                  const paxTotal = dates.reduce((a, d) => a + (paxByDate.get(d)?.total_pax ?? 0), 0);
                  const availTotal = dates.reduce((a, d) => a + (paxByDate.get(d)?.available_rooms ?? 0), 0);
                  const roomsTotal = dates.reduce((a, d) => a + (byDate.get(d)!["0110"] ?? 0), 0);
                  const occPct = availTotal ? rnTotal / availTotal : null;
                  const adr = rnTotal ? roomsTotal / rnTotal : null;
                  return (
                    <>
                      <td className={bTdN}>{intFmt(rnTotal)}</td>
                      <td className={bTdN}>{intFmt(paxTotal)}</td>
                      <td className={bTdN}>{intFmt(availTotal)}</td>
                      <td className={bTdN}>{occPct !== null ? `${(occPct * 100).toFixed(1)}%` : "—"}</td>
                      <td className={`${bTdN} ${adr !== null ? valueColor(adr) : ""}`}>{adr !== null ? `$${money(adr)}` : "—"}</td>
                    </>
                  );
                })()}
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        !loading && <div className="rounded-lg border border-dashed border-ink/12 bg-[#fcfcfb]/50 p-4 text-xs text-ink/60">
          No daily actual revenue loaded yet.
        </div>
      )}
    </div>
  );
}
