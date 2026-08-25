"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import ExcelButton from "@/components/ExcelButton";
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
// Lavado al 40 % con el número en el tono 800: sobre fondo claro los textos
// casi blancos de antes (amber-100, sky-50…) quedaban ilegibles. Medido, los
// cuatro estados dan ~5:1.
const STATUS_STYLE: Record<string, string> = {
  Incompleto: "bg-amber-500/40 text-amber-800 hover:bg-amber-500/55",
  Listo: "bg-sky-500/40 text-sky-800 hover:bg-sky-500/55",
  Auditado: "bg-violet-500/40 text-violet-800 hover:bg-violet-500/55",
  Cerrado: "bg-emerald-500/40 text-emerald-800 hover:bg-emerald-500/55",
};
const STATUS_LABEL: Record<string, string> = {
  Incompleto: "Incomplete", Listo: "Ready", Auditado: "Audited", Cerrado: "Closed",
};
const NO_DATA_STYLE = "bg-ink/4 text-ink/40 hover:bg-ink/5";

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
    <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-2">
      <div className="mb-1 text-center text-[11px] font-medium text-ink/75">{MONTHS[month]}</div>
      <div className="grid grid-cols-7 gap-0.5 text-center text-[9px] text-ink/60">
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
              className={`aspect-square rounded text-[9px] transition-colors ${cls} ${
                // El anillo va en TINTA, no en blanco: un anillo blanco sobre un
                // día sin datos (casi blanco) es invisible -- justo el caso en
                // que más se necesita ver qué está seleccionado. El offset lo
                // despega de la celda para que se lea también sobre los colores.
                isSelected ? "font-bold ring-2 ring-ink ring-offset-1 ring-offset-panel" : ""
              }`}>
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
    <div className="space-y-3 border-t border-ink/10 pt-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink">Day status grid</h2>
          <p className="text-[11px] text-ink/60">
            Incomplete → Ready (minimum required: {(data?.gate_min_set ?? []).join(" + ") || "…"}) → Audited → Closed.
            Click a day to select it above.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setYear((y) => y - 1)} className="rounded bg-ink/5 px-2 py-1 text-xs text-ink/75 hover:text-ink">‹</button>
          <span className="w-10 text-center text-xs text-ink/70">{year}</span>
          <button onClick={() => setYear((y) => y + 1)} className="rounded bg-ink/5 px-2 py-1 text-xs text-ink/75 hover:text-ink">›</button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-ink/70">
        {Object.entries(STATUS_STYLE).map(([k, cls]) => (
          <span key={k} className="flex items-center gap-1">
            <span className={`inline-block h-3 w-3 rounded ${cls.split(" ")[0]}`} /> {STATUS_LABEL[k] || k}
          </span>
        ))}
        <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded bg-ink/4" /> No data</span>
      </div>

      {loading && <div className="text-xs text-ink/60">Loading…</div>}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {Array.from({ length: 12 }, (_, m) => (
          <MonthCalendar key={m} year={year} month={m} statusMap={statusMap} selectedDay={day} onSelect={setBusinessDate} />
        ))}
      </div>

      {selected && (
        <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-3 text-xs">
          <div className="mb-1 font-medium text-ink/85">{selected.business_date} — {STATUS_LABEL[selected.overall] || selected.overall}</div>
          <div className="flex flex-wrap gap-3 text-ink/70">
            {Object.entries(selected.systems).map(([sys, estado]) => (
              <span key={sys}>{sys}: <span className="text-ink/90">{STATUS_LABEL[estado] || estado}</span></span>
            ))}
          </div>
          {selected.kpis && (
            <div className="mt-1 flex gap-3 text-ink/70">
              <span>OK: <span className="text-emerald-600">{selected.kpis.ok}</span></span>
              <span>Discrepancies: <span className={selected.kpis.discrepancia ? "text-amber-600" : "text-ink"}>{selected.kpis.discrepancia}</span></span>
              <span>Missing: <span className={selected.kpis.faltante ? "text-red-600" : "text-ink"}>{selected.kpis.faltante}</span></span>
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
          dragOver ? "border-accent bg-accent/10 text-white" : "border-ink/12 text-ink/60 hover:border-ink/20"}`}
      >
        Drag the day&apos;s files here (Opera XML + Integrity/POS Excel), or click to choose them.
        <input ref={inputRef} type="file" multiple className="hidden"
          onChange={(e) => onFiles(e.target.files)} />
      </div>
      {files.length > 0 && (
        <ul className="divide-y divide-ink/8 rounded-lg border border-ink/10 bg-[#fcfcfb]">
          {files.map((f, i) => (
            <li key={i} className="flex items-center justify-between px-3 py-1.5 text-xs text-ink/85">
              <span className="truncate">{f.name} <span className="text-ink/60">({(f.size / 1024).toFixed(0)} KB)</span></span>
              <button onClick={() => onRemove(i)} className="text-ink/60 hover:text-red-600">✕</button>
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
    <section id="tab1-export" className="space-y-4">
      <div className="float-right">
        <ExcelButton target="tab1-export" filename={`Tab1_Data_Input_${day}`}
          title="Tab 1 · Data Input" subtitle={`Corcovado Wilderness Lodge · ${day}`} label="Excel" />
      </div>
      <div>
        <h1 className="text-xl font-semibold text-ink">Tab 1 · Data Input</h1>
        <p className="text-xs text-ink/60">
          Batch upload for a full day (Opera + Integrity + Simphony) · selected day: <b className="text-ink/85">{day}</b>
        </p>
        <p className="mt-1 text-[11px] text-ink/60">
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
          <button onClick={() => setFiles([])} className="text-xs text-ink/60 hover:text-ink/85">
            Clear selection
          </button>
        )}
      </div>

      {error && (
        <div className="rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-600">
          Error: {error}
        </div>
      )}

      {result && (
        <div className="space-y-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
          <div className="text-sm font-medium text-emerald-600">
            ✓ Ingestion complete — {result.business_date} ({result.property})
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Classification by content</div>
            <table className="w-full text-xs">
              <tbody>
                {Object.entries(CLASSIFY_LABEL).map(([key, label]) => {
                  const v = result.classified[key];
                  const found = Array.isArray(v) ? v.length > 0 : !!v;
                  return (
                    <tr key={key} className="border-t border-ink/8">
                      <td className="px-2 py-1 text-ink/75">{label}</td>
                      <td className={`px-2 py-1 text-right ${found ? "text-emerald-600" : "text-ink/45"}`}>
                        {found ? "✓ detected" : "— not included"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Rows loaded per table</div>
            <div className="grid grid-cols-4 gap-2 text-xs">
              {Object.entries(result.counts).map(([k, v]) => (
                <div key={k} className="rounded border border-ink/10 bg-[#fcfcfb] px-2 py-1.5">
                  <div className="text-ink/60">{k}</div>
                  <div className="font-semibold text-ink">{v}</div>
                </div>
              ))}
            </div>
          </div>

          {result.audit && (
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Audit (automatic run)</div>
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div className="rounded border border-ink/10 bg-[#fcfcfb] px-2 py-1.5">
                  <div className="text-ink/60">Reconciled</div>
                  <div className="font-semibold text-emerald-600">{result.audit.kpis.ok}</div>
                </div>
                <div className="rounded border border-ink/10 bg-[#fcfcfb] px-2 py-1.5">
                  <div className="text-ink/60">Discrepancies</div>
                  <div className={`font-semibold ${result.audit.kpis.discrepancia ? "text-amber-600" : "text-ink"}`}>{result.audit.kpis.discrepancia}</div>
                </div>
                <div className="rounded border border-ink/10 bg-[#fcfcfb] px-2 py-1.5">
                  <div className="text-ink/60">Missing</div>
                  <div className={`font-semibold ${result.audit.kpis.faltante ? "text-red-600" : "text-ink"}`}>{result.audit.kpis.faltante}</div>
                </div>
                <div className="rounded border border-ink/10 bg-[#fcfcfb] px-2 py-1.5">
                  <div className="text-ink/60">Internal</div>
                  <div className="font-semibold text-ink/70">{result.audit.kpis.interno}</div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-ink/60">
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
