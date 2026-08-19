"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { PERIOD_TABS, periodRange, PeriodKey } from "@/lib/periods";
import { useForceRefresh } from "@/lib/forceRefresh";
import { intFmt, pctFmt, usd, valueColor } from "@/lib/fmt";

type ColType = "currency" | "count" | "percent" | "bool" | "date" | "text";
type ColumnMeta = { key: string; label: string; type: ColType };
type DatasetMeta = { key: string; label: string; columns: ColumnMeta[] };

const th = "px-3 py-2 text-left font-medium text-ink/70 whitespace-nowrap";
const thN = "px-3 py-2 text-right font-medium text-ink/70 whitespace-nowrap";
const td = "px-3 py-1.5 text-ink/85 whitespace-nowrap";
const tdN = "px-3 py-1.5 text-right tabular-nums text-ink/85 whitespace-nowrap";

const isNumericType = (t: ColType) => t === "currency" || t === "count" || t === "percent";

function fmtCell(v: unknown, type: ColType): string {
  if (v === null || v === undefined) return "—";
  if (type === "bool") return v ? "Yes" : "No";
  if (type === "currency") return usd(v as number);
  if (type === "percent") return pctFmt(v as number);
  if (type === "count") return intFmt(v as number);
  return String(v);
}

export default function PowerQuery({ anchor }: { anchor: string }) {
  const [datasets, setDatasets] = useState<DatasetMeta[]>([]);
  const [dataset, setDataset] = useState("");
  const [selectedCols, setSelectedCols] = useState<Set<string>>(new Set());
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [ran, setRan] = useState(false);
  const [msg, setMsg] = useState("");
  const { token, forceRefresh, lastRefreshedAt } = useForceRefresh();

  useEffect(() => {
    fetch(`${API_URL}/reporting/datasets`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d: DatasetMeta[]) => {
        setDatasets(d);
        if (d.length > 0) {
          setDataset(d[0].key);
          setSelectedCols(new Set(d[0].columns.map((c) => c.key)));
        }
      })
      .catch(() => setDatasets([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const current = datasets.find((d) => d.key === dataset) ?? null;

  function chooseDataset(key: string) {
    setDataset(key);
    const d = datasets.find((x) => x.key === key);
    setSelectedCols(new Set(d ? d.columns.map((c) => c.key) : []));
    setRan(false); setRows([]);
  }

  function toggleCol(key: string) {
    setSelectedCols((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function applyPeriod(p: PeriodKey) {
    const { from, to } = periodRange(p, anchor);
    setDateFrom(from); setDateTo(to);
  }

  function queryParams() {
    const p = new URLSearchParams();
    p.set("dataset", dataset);
    p.set("columns", [...selectedCols].join(","));
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    // Cache-bust: a real force-refresh must change the request itself.
    p.set("_r", String(token));
    return p;
  }

  const run = useCallback(async () => {
    if (!dataset || selectedCols.size === 0) { setMsg("Pick a dataset and at least one column."); return; }
    setLoading(true); setMsg(""); setRan(true);
    try {
      const res = await fetch(`${API_URL}/reporting/query?${queryParams().toString()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setRows(await res.json());
    } catch (e: any) {
      setRows([]); setMsg(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, selectedCols, dateFrom, dateTo, token]);

  // Force Recalculate re-runs the query that's already on screen -- if
  // nothing has been run yet, there's nothing to recalculate.
  useEffect(() => {
    if (ran) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function download(fmt: "csv" | "xlsx") {
    setMsg("");
    try {
      // Fetch via JS (not a plain <a href>) so a backend failure surfaces as a
      // message here instead of a blank browser tab.
      const res = await fetch(`${API_URL}/reporting/query/export?${queryParams().toString()}&fmt=${fmt}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${dataset}.${fmt}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    }
  }

  const columns = current ? [...selectedCols].filter((c) => current.columns.some((cc) => cc.key === c))
    .sort((a, b) => current.columns.findIndex((c) => c.key === a) - current.columns.findIndex((c) => c.key === b))
    : [];
  const colType = (c: string): ColType => current?.columns.find((cc) => cc.key === c)?.type ?? "text";

  const totals: Record<string, number> = {};
  for (const c of columns) {
    if (!isNumericType(colType(c)) || colType(c) === "percent") continue;
    totals[c] = rows.reduce((a, r) => a + (Number(r[c]) || 0), 0);
  }
  const hasTotals = Object.keys(totals).length > 0;

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-ink/55">
        Open column-picker report builder over the already-ingested tables — pick a dataset, choose which
        columns to show, optionally narrow by date, and run it. In the spirit of Opera Cloud&apos;s Reporting
        &amp; Analytics, but strictly over our own data (never a live Opera Cloud connection).
      </p>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <nav className="flex gap-1">
          {PERIOD_TABS.map((p) => (
            <button key={p.key} onClick={() => applyPeriod(p.key)}
              className="rounded bg-[#fcfcfb] px-2.5 py-1 text-[11px] text-ink/70 hover:bg-ink/5 hover:text-ink">
              {p.label}
            </button>
          ))}
        </nav>
        <div className="flex items-center gap-2 text-[11px] text-ink/55">
          {lastRefreshedAt && <span>Last refreshed: {lastRefreshedAt}</span>}
          <button onClick={forceRefresh}
            className="rounded bg-ink/5 px-2.5 py-1 text-[11px] text-ink/75 hover:bg-ink/8 hover:text-ink">
            🔄 Force Recalculate
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-ink/10 bg-[#fcfcfb] p-3">
        <label className="flex flex-col gap-1 text-xs text-ink/70">
          Dataset
          <select value={dataset} onChange={(e) => chooseDataset(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1.5 text-ink">
            {datasets.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink/70">
          From
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1.5 text-ink" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink/70">
          To
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1.5 text-ink" />
        </label>
        <button onClick={run} disabled={loading}
          className="rounded bg-accent px-4 py-1.5 text-xs font-medium text-ink disabled:opacity-50">
          {loading ? "Running…" : "▶ Run Query"}
        </button>
        {ran && rows.length > 0 && (
          <div className="flex gap-1.5">
            <button onClick={() => download("csv")} className="rounded bg-ink/5 px-3 py-1.5 text-xs text-ink/85 hover:bg-ink/8">
              📥 CSV
            </button>
            <button onClick={() => download("xlsx")} className="rounded bg-ink/5 px-3 py-1.5 text-xs text-ink/85 hover:bg-ink/8">
              📥 Excel
            </button>
          </div>
        )}
      </div>

      {current && (
        <div className="flex flex-wrap gap-2 rounded-lg border border-ink/10 bg-[#fcfcfb]/50 p-3">
          {current.columns.map((c) => (
            <label key={c.key} className="flex items-center gap-1.5 rounded bg-ink/4 px-2 py-1 text-[11px] text-ink/75">
              <input type="checkbox" checked={selectedCols.has(c.key)} onChange={() => toggleCol(c.key)} />
              {c.label}
            </label>
          ))}
        </div>
      )}

      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}

      {ran && !loading && (
        rows.length > 0 ? (
          <div className="max-h-[600px] overflow-auto rounded-lg border border-ink/10">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[#fcfcfb]">
                <tr>
                  {columns.map((c) => (
                    <th key={c} className={isNumericType(colType(c)) ? thN : th}>
                      {current?.columns.find((cc) => cc.key === c)?.label ?? c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-ink/8">
                    {columns.map((c) => (
                      <td key={c} className={isNumericType(colType(c))
                        ? `${tdN} ${colType(c) === "currency" ? valueColor(Number(r[c])) : ""}` : td}>
                        {fmtCell(r[c], colType(c))}
                      </td>
                    ))}
                  </tr>
                ))}
                {hasTotals && (
                  <tr className="sticky bottom-0 border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                    {columns.map((c, i) => (
                      <td key={c} className={isNumericType(colType(c))
                        ? `${tdN} ${colType(c) === "currency" ? valueColor(totals[c]) : ""}` : td}>
                        {i === 0 ? "TOTAL" : (c in totals ? fmtCell(totals[c], colType(c)) : "")}
                      </td>
                    ))}
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-ink/12 bg-[#fcfcfb]/50 p-4 text-xs text-ink/60">
            No rows for this dataset/date range.
          </div>
        )
      )}
    </div>
  );
}
