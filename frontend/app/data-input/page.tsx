"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import { setBusinessDate, useBusinessDate } from "@/lib/useBusinessDate";

type IngestResult = {
  business_date: string;
  property: string;
  batch_id: string;
  classified: Record<string, string | string[] | null>;
  counts: Record<string, number>;
  uploaded_files: string[];
  audit?: { kpis: { ok: number; discrepancia: number; faltante: number; interno: number } };
};

const CLASSIFY_LABEL: Record<string, string> = {
  revenue: "Opera REVENUE.xml",
  statistics: "Opera STATISTICS.xml",
  history_forecast: "history_forecast (Total + Rooms Only)",
  integrity: "Integrity (sheet named 'Datos')",
  bills: "Opera BILLS.xml",
  customer: "Opera CUSTOMER.xml",
  room_stats: "statroomtype*.xml",
};

type DayStatus = {
  business_date: string;
  systems: Record<string, string>;
  overall: string;
  kpis: { ok: number; discrepancia: number; faltante: number } | null;
};
type StatusGridData = { year: number; property: string; gate_min_set: string[]; days: DayStatus[] };

// The values (keys) come straight from the backend (ingest_day_status.estado)
// -- don't translate the keys, only the label that gets displayed.
const STATUS_STYLE: Record<string, string> = {
  Incompleto: "bg-amber-500/30 text-amber-100 hover:bg-amber-500/50",
  Listo: "bg-sky-500/50 text-sky-50 hover:bg-sky-500/70",
  Auditado: "bg-violet-500/50 text-violet-50 hover:bg-violet-500/70",
  Cerrado: "bg-emerald-500/60 text-emerald-50 hover:bg-emerald-500/80",
};
const STATUS_LABEL: Record<string, string> = {
  Incompleto: "Incomplete", Listo: "Ready", Auditado: "Audited", Cerrado: "Closed",
};
const NO_DATA_STYLE = "bg-white/5 text-white/20 hover:bg-white/10";

const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

const pad2 = (n: number) => String(n).padStart(2, "0");
const isoDate = (y: number, m: number, d: number) => `${y}-${pad2(m + 1)}-${pad2(d)}`;
const daysInMonth = (y: number, m: number) => new Date(y, m + 1, 0).getDate();
const firstWeekdayMon = (y: number, m: number) => (new Date(y, m, 1).getDay() + 6) % 7;

function MonthCalendar({ year, month, statusMap, selectedDay, onSelect }: {
  year: number; month: number; statusMap: Map<string, DayStatus>;
  selectedDay: string; onSelect: (d: string) => void;
}) {
  const lead = firstWeekdayMon(year, month);
  const total = daysInMonth(year, month);
  const cells: (number | null)[] = [...Array(lead).fill(null), ...Array.from({ length: total }, (_, i) => i + 1)];
  return (
    <div className="rounded-lg border border-white/10 bg-[#1E2130] p-2">
      <div className="mb-1 text-center text-[11px] font-medium text-white/70">{MONTHS[month]}</div>
      <div className="grid grid-cols-7 gap-0.5 text-center text-[9px] text-white/40">
        {WEEKDAYS.map((d, i) => <div key={i}>{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((d, i) => {
          if (d === null) return <div key={i} />;
          const iso = isoDate(year, month, d);
          const st = statusMap.get(iso);
          const isSelected = iso === selectedDay;
          const cls = st ? STATUS_STYLE[st.overall] || NO_DATA_STYLE : NO_DATA_STYLE;
          return (
            <button key={i} onClick={() => onSelect(iso)}
              title={st ? `${iso} — ${STATUS_LABEL[st.overall] || st.overall}` : `${iso} — no data`}
              className={`aspect-square rounded text-[9px] transition-colors ${cls} ${isSelected ? "ring-2 ring-white" : ""}`}>
              {d}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StatusGrid({ day, reloadKey }: { day: string; reloadKey: number }) {
  const [year, setYear] = useState(() => parseInt(day.slice(0, 4), 10) || new Date().getFullYear());
  const [data, setData] = useState<StatusGridData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/ingest/status?year=${year}`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      setData(await res.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => { load(); }, [load, reloadKey]);

  const statusMap = new Map((data?.days ?? []).map((d) => [d.business_date, d] as const));
  const selected = statusMap.get(day) || null;

  return (
    <div className="space-y-3 border-t border-white/10 pt-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Day status grid</h2>
          <p className="text-[11px] text-white/40">
            Incomplete → Ready (minimum required: {(data?.gate_min_set ?? []).join(" + ") || "…"}) → Audited → Closed.
            Click a day to select it above.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setYear((y) => y - 1)} className="rounded bg-white/10 px-2 py-1 text-xs text-white/70 hover:text-white">‹</button>
          <span className="w-10 text-center text-xs text-white/60">{year}</span>
          <button onClick={() => setYear((y) => y + 1)} className="rounded bg-white/10 px-2 py-1 text-xs text-white/70 hover:text-white">›</button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-white/60">
        {Object.entries(STATUS_STYLE).map(([k, cls]) => (
          <span key={k} className="flex items-center gap-1">
            <span className={`inline-block h-3 w-3 rounded ${cls.split(" ")[0]}`} /> {STATUS_LABEL[k] || k}
          </span>
        ))}
        <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded bg-white/5" /> No data</span>
      </div>

      {loading && <div className="text-xs text-white/40">Loading…</div>}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {Array.from({ length: 12 }, (_, m) => (
          <MonthCalendar key={m} year={year} month={m} statusMap={statusMap} selectedDay={day} onSelect={setBusinessDate} />
        ))}
      </div>

      {selected && (
        <div className="rounded-lg border border-white/10 bg-[#1E2130] p-3 text-xs">
          <div className="mb-1 font-medium text-white/80">{selected.business_date} — {STATUS_LABEL[selected.overall] || selected.overall}</div>
          <div className="flex flex-wrap gap-3 text-white/60">
            {Object.entries(selected.systems).map(([sys, estado]) => (
              <span key={sys}>{sys}: <span className="text-white/90">{STATUS_LABEL[estado] || estado}</span></span>
            ))}
          </div>
          {selected.kpis && (
            <div className="mt-1 flex gap-3 text-white/60">
              <span>OK: <span className="text-emerald-400">{selected.kpis.ok}</span></span>
              <span>Discrepancies: <span className={selected.kpis.discrepancia ? "text-amber-400" : "text-white"}>{selected.kpis.discrepancia}</span></span>
              <span>Missing: <span className={selected.kpis.faltante ? "text-red-400" : "text-white"}>{selected.kpis.faltante}</span></span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DropZone({ files, onFiles, onRemove }: {
  files: File[]; onFiles: (f: FileList | null) => void; onRemove: (i: number) => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); onFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center text-sm transition-colors ${
          dragOver ? "border-accent bg-accent/10 text-white" : "border-white/15 text-white/50 hover:border-white/30"}`}
      >
        Drag the day&apos;s files here (Opera XML + Integrity/POS Excel), or click to choose them.
        <input ref={inputRef} type="file" multiple className="hidden"
          onChange={(e) => onFiles(e.target.files)} />
      </div>
      {files.length > 0 && (
        <ul className="divide-y divide-white/5 rounded-lg border border-white/10 bg-[#1E2130]">
          {files.map((f, i) => (
            <li key={i} className="flex items-center justify-between px-3 py-1.5 text-xs text-white/80">
              <span className="truncate">{f.name} <span className="text-white/40">({(f.size / 1024).toFixed(0)} KB)</span></span>
              <button onClick={() => onRemove(i)} className="text-white/40 hover:text-red-400">✕</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function DataInputPage() {
  const day = useBusinessDate();
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)]);
    setResult(null); setError("");
  }, []);

  const removeFile = useCallback((i: number) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }, []);

  async function upload() {
    if (files.length === 0) return;
    setUploading(true); setError(""); setResult(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      const res = await fetch(`${API_URL}/ingest/${day}/upload`, { method: "POST", body: form });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setResult(body);
      setFiles([]);
      setReloadKey((k) => k + 1);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-white">Tab 1 · Data Input</h1>
        <p className="text-xs text-white/50">
          Batch upload for a full day (Opera + Integrity + Simphony) · selected day: <b className="text-white/80">{day}</b>
        </p>
        <p className="mt-1 text-[11px] text-white/40">
          business_date is assigned by the batch (the day selector above), never the file name (§2.8).
          Files are classified by content — the real Integrity file can be named anything,
          it&apos;s detected by having a sheet named &quot;Datos&quot;. Re-uploading fully replaces
          what was previously loaded for this day (§2.5) — it doesn&apos;t accumulate.
        </p>
      </div>

      <DropZone files={files} onFiles={addFiles} onRemove={removeFile} />

      <div className="flex items-center gap-3">
        <button onClick={upload} disabled={uploading || files.length === 0}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {uploading ? "Uploading and ingesting…" : `Upload and Ingest (${files.length} file${files.length === 1 ? "" : "s"})`}
        </button>
        {files.length > 0 && !uploading && (
          <button onClick={() => setFiles([])} className="text-xs text-white/50 hover:text-white/80">
            Clear selection
          </button>
        )}
      </div>

      {error && (
        <div className="rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-300">
          Error: {error}
        </div>
      )}

      {result && (
        <div className="space-y-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
          <div className="text-sm font-medium text-emerald-400">
            ✓ Ingestion complete — {result.business_date} ({result.property})
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-white/50">Classification by content</div>
            <table className="w-full text-xs">
              <tbody>
                {Object.entries(CLASSIFY_LABEL).map(([key, label]) => {
                  const v = result.classified[key];
                  const found = Array.isArray(v) ? v.length > 0 : !!v;
                  return (
                    <tr key={key} className="border-t border-white/5">
                      <td className="px-2 py-1 text-white/70">{label}</td>
                      <td className={`px-2 py-1 text-right ${found ? "text-emerald-400" : "text-white/30"}`}>
                        {found ? "✓ detected" : "— not included"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-white/50">Rows loaded per table</div>
            <div className="grid grid-cols-4 gap-2 text-xs">
              {Object.entries(result.counts).map(([k, v]) => (
                <div key={k} className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5">
                  <div className="text-white/50">{k}</div>
                  <div className="font-semibold text-white">{v}</div>
                </div>
              ))}
            </div>
          </div>

          {result.audit && (
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-white/50">Audit (automatic run)</div>
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5">
                  <div className="text-white/50">Reconciled</div>
                  <div className="font-semibold text-emerald-400">{result.audit.kpis.ok}</div>
                </div>
                <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5">
                  <div className="text-white/50">Discrepancies</div>
                  <div className={`font-semibold ${result.audit.kpis.discrepancia ? "text-amber-400" : "text-white"}`}>{result.audit.kpis.discrepancia}</div>
                </div>
                <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5">
                  <div className="text-white/50">Missing</div>
                  <div className={`font-semibold ${result.audit.kpis.faltante ? "text-red-400" : "text-white"}`}>{result.audit.kpis.faltante}</div>
                </div>
                <div className="rounded border border-white/10 bg-[#1E2130] px-2 py-1.5">
                  <div className="text-white/50">Internal</div>
                  <div className="font-semibold text-white/60">{result.audit.kpis.interno}</div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-white/40">
                See the full detail in Tab 2 · Daily Audit, and Revenue/Cash in Tabs 3-5.
              </p>
            </div>
          )}
        </div>
      )}

      <StatusGrid day={day} reloadKey={reloadKey} />
    </section>
  );
}
