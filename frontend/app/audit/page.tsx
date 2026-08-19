"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";

type Row = {
  tcode: string; description: string; type: string | null; categoria: string;
  opera: number | null; integrity: number | null; diferencia: number | null;
  estado: string; cuenta: string; nombre: string;
};
type TrialRow = {
  tcode: string; description: string; type: string; total: number;
  guest_ledger: number; package_ledger: number; ar_ledger: number; deposit_ledger: number;
};
type Cat = { categoria: string; opera: number; integrity: number; diferencia: number };
type MarketRow = { tcode: string; description: string; values: Record<string, number>; total: number };
type Finding = {
  id?: string; business_date?: string;
  tcode: string | null; area: string | null; tipo_desviacion: string | null;
  monto: number; estado: string; comentario: string | null; source_view?: string | null;
  resolved_note?: string | null; resolved_at?: string | null;
};
type Ledger = {
  ledger: string; label: string; opening: number; movement: number; closing: number;
  anchored: boolean; anchor_date: string | null; note: string | null; source?: string;
};
type OccRecord = {
  market_code: string | null; market_name: string | null;
  room_class: string | null; room_class_name: string | null; room_type: string | null;
  rooms: number; persons: number; noshow_rooms: number; cancel_rooms: number;
};
type OccPivot = { rooms: number; persons: number; noshow_rooms: number; cancel_rooms: number };
type Occupancy = {
  records: OccRecord[];
  by_market: (OccPivot & { market_code: string; name: string | null })[];
  by_room_class: (OccPivot & { room_class: string; name: string | null })[];
  totals: OccPivot;
};
type OtbScope = {
  revenue: number; no_rooms: number; no_persons: number; inventory_rooms: number;
  adr: number; occupancy: number; source_file: string | null;
};
type OtbRecon = { otb: number; actual_integrity: number; diferencia: number; estado: string };
type OtbActualStats = {
  rn: number; pax: number; available: number; adr: number; occupancy_pct: number;
  available_real_opera: number;
};
type OtbData = {
  total: OtbScope | null; rooms: OtbScope | null; non_room_revenue: number | null;
  full_revenue_recon: OtbRecon | null; rooms_only_recon: OtbRecon | null;
  actual_stats: OtbActualStats | null;
};
type PosCheckCheck = { concepto: string; a: number; b: number; diferencia: number; estado: string };
type PosPmsCheck = {
  pos_total_ventas: number; opera_recon: PosCheckCheck; integrity_recon: PosCheckCheck;
} | null;
type PosSummaryData = {
  ventas_netas: number; cargos_servicio: number; total_ventas: number;
  voids: number; room_charge_confirmado: number; source_file: string | null;
};
type PosRoomCharge = { restaurant: string | null; employee: string | null; check_num: string | null; hora: string | null; monto: number };
type PosData = {
  summary: PosSummaryData; internal_checks: PosCheckCheck[]; pms_check: PosPmsCheck;
  by_payment: { forma: string; count: number; total: number }[];
  by_employee: { empleado: string; count: number; total: number }[];
  room_charges: PosRoomCharge[]; total_checks: number;
} | null;
type Gate = { gate_hard: boolean; allowed: boolean; reason: string; open_issues: number };
type Audit = {
  business_date: string; status: string | null; generated_at: string | null;
  released_at: string | null; refreshed_at: string | null;
  override_flag: boolean; override_note: string | null; gate: Gate;
  kpis: { ok: number; discrepancia: number; faltante: number; interno: number };
  rows: Row[]; category_summary: Cat[];
  revenue_total: number; nonrev_total: number; payment_total: number;
  trial_balance: TrialRow[]; trial_balance_source?: string; ledgers: Ledger[];
  occupancy: Occupancy; otb: OtbData; pos: PosData;
  market_code: { codes: string[]; rows: MarketRow[]; totals: Record<string, number> };
  findings: Finding[];
};

const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const int = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { maximumFractionDigits: 0 });

const negColor = (v: number | null | undefined) =>
  v !== null && v !== undefined && v < 0 ? "!text-rose-600" : "";

// The keys come straight from the backend (engine/reconcile.py `estado`) --
// don't translate the keys, only the label that gets displayed (ESTADO_LABEL).
const ESTADO_STYLE: Record<string, string> = {
  OK: "text-emerald-600", DISCREPANCIA: "text-amber-600",
  "FALTA EN INTEGRITY": "text-red-600", "FALTA EN OPERA": "text-red-600",
  INTERNO: "text-ink/60", DIF_OPERATIVA: "text-amber-600",
};
const ESTADO_LABEL: Record<string, string> = {
  OK: "OK", DISCREPANCIA: "DISCREPANCY",
  "FALTA EN INTEGRITY": "MISSING IN INTEGRITY", "FALTA EN OPERA": "MISSING IN OPERA",
  INTERNO: "INTERNAL", DIF_OPERATIVA: "OPERATIONAL DIFF",
};

const SUBTABS = [
  { id: "2.1", label: "2.1 Summary" },
  { id: "2.2", label: "2.2 Trial Balance" },
  { id: "2.3", label: "2.3 Ledgers" },
  { id: "2.4", label: "2.4 Statistics" },
  { id: "2.5", label: "2.5 OTB vs Revenue" },
  { id: "2.6", label: "2.6 Market Code" },
  { id: "2.7", label: "2.7 ReCon Detail" },
  { id: "2.8", label: "2.8 Discrepancies" },
  { id: "2.9", label: "2.9 Simphony POS" },
  { id: "2.10", label: "2.10 Findings" },
];

function Kpi({ label, value, tone }: { label: string; value: number | string; tone: string }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-4">
      <div className={`text-2xl font-bold ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-ink/60">{label}</div>
    </div>
  );
}

const th = "px-3 py-2 text-left font-medium text-ink/70";
const td = "px-3 py-1.5 text-ink/85";
const tdN = "px-3 py-1.5 text-right tabular-nums text-ink/85";

function Pending({ what, needs }: { what: string; needs: string }) {
  return (
    <div className="rounded-lg border border-dashed border-ink/12 bg-[#fcfcfb]/50 p-6 text-sm text-ink/70">
      <b className="text-ink/85">{what}</b> — pending. {needs}
    </div>
  );
}

export default function AuditPage() {
  const day = useBusinessDate();
  const [data, setData] = useState<Audit | null>(null);
  const [tab, setTab] = useState("2.1");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [showOverride, setShowOverride] = useState(false);
  const [overrideNote, setOverrideNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/audit/${day}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch {
      setData(null); setMsg(`No audit for ${day}. Run the ingestion.`);
    } finally { setLoading(false); }
  }, [day]);

  useEffect(() => { load(); }, [load]);

  // "Apply Audit" -- forces a full re-ingest + re-audit of every table for
  // this day, then VERIFIES the response actually contains updated data
  // (rows ingested > 0 and reconciliation rows present) before declaring
  // success. If no such confirmation comes back, it retries on its own
  // instead of leaving the user staring at stale zeros.
  async function applyAudit() {
    setLoading(true);
    const MAX_ATTEMPTS = 3;
    try {
      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        setMsg(`Applying audit — forcing recalculation of all tables (attempt ${attempt}/${MAX_ATTEMPTS})…`);
        try {
          const res = await fetch(`${API_URL}/ingest/${day}?run_audit=true`, { method: "POST" });
          const body = await res.json();
          // A 400 means the day's files are bad (a required source came in
          // empty) — retrying won't fix it. Stop immediately and show exactly
          // what to correct, instead of burning 3 attempts on a deterministic
          // failure.
          if (res.status === 400) {
            setMsg(`⛔ Ingest blocked — ${body.detail || "a required source is empty"}`);
            await load();
            return;
          }
          if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
          const counts: Record<string, number> = body.counts || {};
          const totalRows = Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0);
          const auditRan = body.audit && Array.isArray(body.audit.rows);
          if (totalRows > 0 && auditRan) {
            setMsg(`✓ Confirmed updated: ${totalRows} rows ingested across all tables, ${body.audit.rows.length} reconciliation rows generated.`);
            await load();
            return;
          }
          setMsg(`No confirmation of update yet (${totalRows} rows ingested) — retrying (${attempt}/${MAX_ATTEMPTS})…`);
        } catch (e: any) {
          setMsg(`Error on attempt ${attempt}/${MAX_ATTEMPTS}: ${e.message} — retrying…`);
        }
        if (attempt < MAX_ATTEMPTS) await new Promise((r) => setTimeout(r, 1500));
      }
      setMsg(`Could not confirm the audit updated after ${MAX_ATTEMPTS} attempts. Check that the day's files were actually uploaded in Tab 1, then try again.`);
      await load();
    } finally { setLoading(false); }
  }

  async function release(override: boolean) {
    setLoading(true); setMsg(override ? "Releasing with override…" : "Releasing…");
    try {
      const res = await fetch(`${API_URL}/audit/${day}/release`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(override
          ? { override_flag: true, override_note: overrideNote }
          : {}),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setShowOverride(false); setOverrideNote("");
      setMsg(`Released: ${body.gate.reason}`);
      await load();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  }

  async function reopen() {
    if (!confirm(`Reopen ${day}? It's already released to owners — this undoes the release (goes back to "Open"), it doesn't delete the data already audited.`)) return;
    setLoading(true); setMsg("Reopening…");
    try {
      const res = await fetch(`${API_URL}/audit/${day}/reopen`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reopen_note: "Reopened from Tab 2." }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setMsg("Reopened.");
      await load();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  }

  async function downloadExport(fmt: "excel" | "pdf") {
    setMsg(`Preparing ${fmt.toUpperCase()}…`);
    try {
      // fetch (not a plain <a href>) so a backend failure surfaces as a
      // message here instead of a blank browser tab.
      const res = await fetch(`${API_URL}/export/${day}/${fmt}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `DAILY-OPS_${day}.${fmt === "excel" ? "xlsx" : "pdf"}`;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      setMsg("");
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
  }

  async function refresh() {
    setLoading(true); setMsg("Refreshing (re-ingest + re-audit)…");
    try {
      const res = await fetch(`${API_URL}/audit/${day}/refresh`, { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setMsg("Refreshed.");
      await load();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
    finally { setLoading(false); }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Tab 2 · Daily Audit</h1>
          <p className="text-xs text-ink/60">
            Opera ↔ Integrity Reconciliation · {day}
            {data?.generated_at && ` · generated ${new Date(data.generated_at).toLocaleString()}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <span className={`rounded px-2 py-1 text-[11px] font-medium ${
              data.status === "cerrado" ? "bg-emerald-500/15 text-emerald-600" : "bg-ink/5 text-ink/70"}`}>
              {data.status === "cerrado" ? "🔒 Closed (released)" : "🔓 Open"}
            </span>
          )}
          {data?.status === "cerrado" ? (
            <>
              <button onClick={refresh} disabled={loading}
                className="rounded bg-ink/5 px-3 py-2 text-xs font-medium text-white hover:bg-ink/8 disabled:opacity-50">
                {loading ? "…" : "🔄 REFRESH"}
              </button>
              <button onClick={reopen} disabled={loading}
                className="rounded bg-amber-600 px-3 py-2 text-xs font-medium text-white hover:bg-amber-500 disabled:opacity-50">
                {loading ? "…" : "🔓 Reopen"}
              </button>
            </>
          ) : (
            <button onClick={() => release(false)} disabled={loading || !data}
              className="rounded bg-emerald-600 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
              {loading ? "…" : "Release to Owners"}
            </button>
          )}
          <button onClick={applyAudit} disabled={loading}
            title="Force-recalculates every table for this day from the uploaded files, verifies the update actually took effect, and retries automatically if it doesn't."
            className="rounded bg-indigo-600 px-3 py-2 text-xs font-medium text-ink hover:bg-indigo-500 disabled:opacity-50">
            {loading ? "…" : "🛡 Apply Audit"}
          </button>
          <div className="flex gap-1 border-l border-ink/10 pl-2">
            <button onClick={() => downloadExport("excel")}
              className="rounded bg-ink/5 px-3 py-2 text-xs font-medium text-white hover:bg-ink/8">
              📊 Excel
            </button>
            <button onClick={() => downloadExport("pdf")}
              className="rounded bg-ink/5 px-3 py-2 text-xs font-medium text-white hover:bg-ink/8">
              📄 PDF
            </button>
          </div>
        </div>
      </div>

      {data && !data.gate.allowed && data.status !== "cerrado" && (
        <div className="rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-600">
          <div className="mb-1">⛔ {data.gate.reason}</div>
          {!showOverride ? (
            <button onClick={() => setShowOverride(true)} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/85 hover:bg-ink/8">
              Release anyway with override…
            </button>
          ) : (
            <div className="flex gap-2">
              <input value={overrideNote} onChange={(e) => setOverrideNote(e.target.value)}
                placeholder="Override reason (required)"
                className="w-80 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
              <button onClick={() => release(true)} disabled={loading || !overrideNote.trim()}
                className="rounded bg-amber-600 px-2 py-1 text-[11px] text-white disabled:opacity-50">
                Confirm override
              </button>
              <button onClick={() => setShowOverride(false)} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75">✕</button>
            </div>
          )}
        </div>
      )}

      {data?.status === "cerrado" && data.override_flag && (
        <div className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700">
          ⚠ Released with override: {data.override_note}
        </div>
      )}

      {msg && (
        <div className={`rounded border p-3 text-sm ${
          msg.startsWith("✓") ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-700"
            : msg.startsWith("Error") || msg.startsWith("Could not confirm") ? "border-red-500/30 bg-red-500/5 text-red-600"
            : "border-ink/10 bg-[#fcfcfb] text-ink/75"
        }`}>
          {msg}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-4 gap-3">
            <Kpi label="Reconciled" value={data.kpis.ok} tone="text-emerald-600" />
            <Kpi label="Discrepancies" value={data.kpis.discrepancia} tone={data.kpis.discrepancia ? "text-amber-600" : "text-ink"} />
            <Kpi label="Missing" value={data.kpis.faltante} tone={data.kpis.faltante ? "text-red-600" : "text-ink"} />
            <Kpi label="Internal" value={data.kpis.interno} tone="text-ink/70" />
          </div>

          <nav className="flex flex-wrap gap-1 border-b border-ink/10 pb-2">
            {SUBTABS.map((s) => (
              <button key={s.id} onClick={() => setTab(s.id)}
                className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "border border-ink/10 bg-panel text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
                {s.label}
              </button>
            ))}
          </nav>

          <div className="overflow-x-auto">
            {tab === "2.1" && <Resumen d={data} />}
            {tab === "2.2" && <TrialBalance rows={data.trial_balance} source={data.trial_balance_source} />}
            {tab === "2.3" && <Ledgers ledgers={data.ledgers} day={day} onSaved={load} />}
            {tab === "2.4" && <Estadisticas o={data.occupancy} />}
            {tab === "2.5" && <OtbVsRevenue otb={data.otb} />}
            {tab === "2.6" && <MarketCode m={data.market_code} />}
            {tab === "2.7" && <Recon rows={data.rows} />}
            {tab === "2.8" && <Recon rows={[
              ...data.rows.filter((r) => r.estado !== "OK" && r.estado !== "INTERNO"),
              ...operationalFindingsAsRows(data.findings),
            ]} empty="No discrepancies — everything reconciles." />}
            {tab === "2.9" && <SimphonyPos pos={data.pos} />}
            {tab === "2.10" && (
              <div className="space-y-6">
                <HallazgosYTD />
                <div>
                  <h3 className="mb-2 text-sm font-medium text-ink/75">Findings for the day ({day})</h3>
                  <Hallazgos findings={data.findings} />
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function Resumen({ d }: { d: Audit }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Kpi label="Revenue (Opera)" value={`$${money(d.revenue_total)}`} tone="text-emerald-600" />
        <Kpi label="Non-Revenue" value={`$${money(d.nonrev_total)}`} tone="text-ink/85" />
        <Kpi label="Payments" value={`$${money(d.payment_total)}`} tone="text-sky-600" />
      </div>
      <table className="w-full rounded-lg border border-ink/10 text-xs">
        <thead className="bg-[#fcfcfb]"><tr>
          {["Category", "Opera", "Integrity", "Difference", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
        </tr></thead>
        <tbody>
          {d.category_summary.map((c) => {
            const ok = Math.abs(c.diferencia) < 0.01;
            return (
              <tr key={c.categoria} className="border-t border-ink/8">
                <td className={td}>{c.categoria}</td>
                <td className={`${tdN} ${negColor(c.opera)}`}>${money(c.opera)}</td>
                <td className={`${tdN} ${negColor(c.integrity)}`}>${money(c.integrity)}</td>
                <td className={`${tdN} ${ok ? negColor(c.diferencia) : "text-amber-600"}`}>${money(c.diferencia)}</td>
                <td className={`px-3 py-1.5 font-medium ${ok ? "text-emerald-600" : "text-amber-600"}`}>{ok ? "✓ Reconciled" : "⚠ Review"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Operational findings (2.5, no tcode -- Inventory/Occupancy/etc.) mapped to
// the reconciliation row format, to consolidate them in 2.8 alongside tcode ones.
function operationalFindingsAsRows(findings: Finding[]): Row[] {
  return findings.filter((f) => f.tcode === null).map((f) => ({
    tcode: "—", description: f.comentario ?? "", type: f.source_view ?? "Operational",
    categoria: "Operational", opera: null, integrity: null, diferencia: f.monto,
    estado: f.tipo_desviacion ?? "DIF_OPERATIVA", cuenta: "", nombre: f.area ?? "",
  }));
}

function Recon({ rows, empty }: { rows: Row[]; empty?: string }) {
  if (empty && rows.length === 0)
    return <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-6 text-sm text-emerald-600">{empty}</div>;
  return (
    <table className="w-full rounded-lg border border-ink/10 text-xs">
      <thead className="bg-[#fcfcfb]"><tr>
        {["TCode", "Description", "Type", "Opera", "Integrity", "Difference", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
      </tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={`${r.tcode}-${r.nombre}-${i}`} className="border-t border-ink/8">
            <td className="px-3 py-1.5 font-mono text-ink/85">{r.tcode}</td>
            <td className={td}>{r.description}</td>
            <td className="px-3 py-1.5 text-ink/60">{r.type}</td>
            <td className={`${tdN} ${negColor(r.opera)}`}>${money(r.opera)}</td>
            <td className={`${tdN} ${negColor(r.integrity)}`}>${money(r.integrity)}</td>
            <td className={`${tdN} ${r.diferencia && Math.abs(r.diferencia) >= 0.01 ? "text-amber-600" : negColor(r.diferencia) || "text-ink/60"}`}>${money(r.diferencia)}</td>
            <td className={`px-3 py-1.5 font-medium ${ESTADO_STYLE[r.estado] || "text-ink"}`}>{ESTADO_LABEL[r.estado] || r.estado}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function sumTrialCols(rows: TrialRow[]) {
  return rows.reduce(
    (acc, r) => ({
      total: acc.total + r.total,
      guest_ledger: acc.guest_ledger + r.guest_ledger,
      package_ledger: acc.package_ledger + r.package_ledger,
      ar_ledger: acc.ar_ledger + r.ar_ledger,
      deposit_ledger: acc.deposit_ledger + r.deposit_ledger,
    }),
    { total: 0, guest_ledger: 0, package_ledger: 0, ar_ledger: 0, deposit_ledger: 0 },
  );
}

function TrialBalance({ rows, source }: { rows: TrialRow[]; source?: string }) {
  // rows already come grouped by Type from the backend (TYPE_ORDER) -- a
  // subtotal is built when each consecutive group closes, plus a Grand Total at the end.
  const groups: { type: string; rows: TrialRow[] }[] = [];
  for (const r of rows) {
    const last = groups[groups.length - 1];
    if (last && last.type === r.type) last.rows.push(r);
    else groups.push({ type: r.type, rows: [r] });
  }
  const grandTotal = sumTrialCols(rows);
  const official = (source || "").toLowerCase().includes("official");

  return (
    <div className="space-y-2">
    {source && (
      <div className="text-xs text-ink/70">
        Source:{" "}
        <span className={`rounded px-2 py-0.5 font-medium ${official ? "bg-emerald-500/15 text-emerald-700" : "bg-amber-500/15 text-amber-700"}`}>
          {source}
        </span>
      </div>
    )}
    <table className="w-full rounded-lg border border-ink/10 text-xs">
      <thead className="bg-[#fcfcfb]"><tr>
        {["TCode", "Description", "Type", "Total", "Guest", "Package", "AR", "Deposit"].map((h) => <th key={h} className={th}>{h}</th>)}
      </tr></thead>
      <tbody>
        {groups.map((g) => {
          const sub = sumTrialCols(g.rows);
          return (
            <Fragment key={g.type}>
              {g.rows.map((r) => (
                <tr key={r.tcode} className="border-t border-ink/8">
                  <td className="px-3 py-1.5 font-mono text-ink/85">{r.tcode}</td>
                  <td className={td}>{r.description}</td>
                  <td className="px-3 py-1.5 text-ink/60">{r.type}</td>
                  <td className={`${tdN} ${negColor(r.total)}`}>${money(r.total)}</td>
                  <td className={`${tdN} ${negColor(r.guest_ledger)}`}>${money(r.guest_ledger)}</td>
                  <td className={`${tdN} ${negColor(r.package_ledger)}`}>${money(r.package_ledger)}</td>
                  <td className={`${tdN} ${negColor(r.ar_ledger)}`}>${money(r.ar_ledger)}</td>
                  <td className={`${tdN} ${negColor(r.deposit_ledger)}`}>${money(r.deposit_ledger)}</td>
                </tr>
              ))}
              <tr className="border-t border-ink/10 bg-[#fcfcfb]/60">
                <td className={`${td} font-medium text-ink/70`} colSpan={3}>Subtotal {g.type}</td>
                <td className={`${tdN} font-medium ${negColor(sub.total)}`}>${money(sub.total)}</td>
                <td className={`${tdN} font-medium ${negColor(sub.guest_ledger)}`}>${money(sub.guest_ledger)}</td>
                <td className={`${tdN} font-medium ${negColor(sub.package_ledger)}`}>${money(sub.package_ledger)}</td>
                <td className={`${tdN} font-medium ${negColor(sub.ar_ledger)}`}>${money(sub.ar_ledger)}</td>
                <td className={`${tdN} font-medium ${negColor(sub.deposit_ledger)}`}>${money(sub.deposit_ledger)}</td>
              </tr>
            </Fragment>
          );
        })}
        <tr className="border-t-2 border-ink/15 bg-[#fcfcfb]">
          <td className={`${td} font-bold`} colSpan={3}>GRAND TOTAL</td>
          <td className={`${tdN} font-bold ${negColor(grandTotal.total) || "text-emerald-600"}`}>${money(grandTotal.total)}</td>
          <td className={`${tdN} font-bold ${negColor(grandTotal.guest_ledger)}`}>${money(grandTotal.guest_ledger)}</td>
          <td className={`${tdN} font-bold ${negColor(grandTotal.package_ledger)}`}>${money(grandTotal.package_ledger)}</td>
          <td className={`${tdN} font-bold ${negColor(grandTotal.ar_ledger)}`}>${money(grandTotal.ar_ledger)}</td>
          <td className={`${tdN} font-bold ${negColor(grandTotal.deposit_ledger)}`}>${money(grandTotal.deposit_ledger)}</td>
        </tr>
      </tbody>
    </table>
    </div>
  );
}

type Folio = {
  bill_no: string; guest_name: string; status: string; total_amount: number;
  lines: { trx_code: string; trx_date: string; net_amount: number; debit_amount: number; credit_amount: number }[];
};
// AR ledger detail = City Ledger invoices (empresas/agencias)
type ArInvoice = {
  invoice_no: string; bill_no: string | null; account_name: string | null;
  account_number: string | null; amount: number; guest_name: string | null;
  arrival_date: string | null; departure_date: string | null; confirmation_no: string | null;
};
type MovementRow = { tcode: string; description: string; type: string; amount: number };
type Detail = {
  ledger: string; movement_detail: MovementRow[]; movement_total: number;
  folios: (Folio | ArInvoice)[]; folio_total: number; note: string; ties_to_movement?: boolean;
};

function Ledgers({ ledgers, day, onSaved }: { ledgers: Ledger[]; day: string; onSaved: () => void }) {
  const [edit, setEdit] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [openDetail, setOpenDetail] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [openFolio, setOpenFolio] = useState<string | null>(null);

  async function toggleDetail(ledger: string) {
    if (openDetail === ledger) { setOpenDetail(null); return; }
    setOpenDetail(ledger); setDetail(null); setOpenFolio(null);
    try {
      const res = await fetch(`${API_URL}/ledgers/${day}/detail?ledger=${ledger}`, { cache: "no-store" });
      setDetail(await res.json());
    } catch { setDetail(null); }
  }

  function startEdit(l: Ledger) {
    setEdit(l.ledger); setAmount(String(l.opening)); setNote(l.note || "");
  }

  async function save(ledger: string) {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/ledgers/${day}/opening`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ledger, amount: parseFloat(amount) || 0, note: note || null }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setEdit(null); onSaved();
    } catch { /* noop */ } finally { setSaving(false); }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-ink/60">
        Running balance: <b className="text-ink/75">Closing = Opening + Day&apos;s Movement</b>. The
        opening carries over the previous day&apos;s closing; edit it to re-anchor and start fresh.
      </p>
      <table className="w-full rounded-lg border border-ink/10 text-xs">
        <thead className="bg-[#fcfcfb]"><tr>
          {["Ledger", "Opening", "Day's Movement", "Closing", "Opening Source", ""].map((h) => <th key={h} className={th}>{h}</th>)}
        </tr></thead>
        <tbody>
          {ledgers.map((l) => (
            <tr key={l.ledger} className="border-t border-ink/8">
              <td className={`${td} font-medium`}>{l.label}</td>
              <td className={`${tdN} ${negColor(l.opening)}`}>
                {edit === l.ledger ? (
                  <span className="flex items-center justify-end gap-1">
                    <span className="text-ink/60">$</span>
                    <input value={amount} onChange={(e) => setAmount(e.target.value)} type="number"
                      autoFocus
                      className="w-28 rounded border border-accent bg-[#f9f9f7] px-2 py-1 text-right text-ink" />
                  </span>
                ) : `$${money(l.opening)}`}
              </td>
              <td className={`${tdN} ${negColor(l.movement)}`}>${money(l.movement)}</td>
              <td className={`${tdN} font-medium ${negColor(l.closing) || "text-ink"}`}>${money(l.closing)}</td>
              <td className="px-3 py-1.5 text-ink/60">
                {l.source === "Trial Balance"
                  ? <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[11px] text-emerald-700">Trial Balance</span>
                  : l.anchored ? <span className="text-sky-600">anchor {l.anchor_date}</span> : "carried over"}
                {l.note && <span className="text-ink/60"> · {l.note}</span>}
              </td>
              <td className="px-3 py-1.5">
                {edit === l.ledger ? (
                  <span className="flex items-center gap-1">
                    <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="note — optional, NOT the balance"
                      title="Optional reference text only. The dollar amount goes in the 'Opening' box on the left, not here."
                      className="w-40 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink/75 placeholder:text-ink/45 placeholder:italic" />
                    <button onClick={() => save(l.ledger)} disabled={saving}
                      className="rounded bg-accent px-2 py-1 text-[11px] text-white disabled:opacity-50">Save</button>
                    <button onClick={() => setEdit(null)} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75">✕</button>
                  </span>
                ) : (
                  <span className="flex gap-1">
                    <button onClick={() => toggleDetail(l.ledger)}
                      className={`rounded px-2 py-1 text-[11px] ${openDetail === l.ledger ? "bg-accent text-white" : "bg-ink/5 text-ink/75 hover:text-ink"}`}>
                      {openDetail === l.ledger ? "▲ folios" : "▼ folios"}
                    </button>
                    <button onClick={() => startEdit(l)} className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:text-ink">Edit opening</button>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {openDetail && (
        <div className="rounded-lg border border-ink/10 bg-[#fcfcfb]/40 p-3 text-xs">
          <div className="mb-2 font-medium text-ink/85">
            Supporting detail · {ledgers.find((l) => l.ledger === openDetail)?.label}
          </div>
          {!detail ? (
            <div className="text-ink/60">Loading…</div>
          ) : (
            <div className="space-y-3">
              <div>
                <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Day&apos;s movement by TCode (ties to the movement)</div>
                {detail.movement_detail.length === 0 ? (
                  <div className="text-ink/60">No movement this day.</div>
                ) : (
                  <table className="w-full">
                    <thead><tr>{["TCode", "Description", "Type", "Amount"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
                    <tbody>
                      {detail.movement_detail.map((m) => (
                        <tr key={m.tcode} className="border-t border-ink/8">
                          <td className="px-3 py-1 font-mono text-ink/85">{m.tcode}</td>
                          <td className={td}>{m.description}</td>
                          <td className="px-3 py-1 text-ink/60">{m.type}</td>
                          <td className={`${tdN} ${negColor(m.amount)}`}>${money(m.amount)}</td>
                        </tr>
                      ))}
                      <tr className="border-t border-ink/15 bg-[#fcfcfb]">
                        <td className={`${td} font-bold`} colSpan={3}>TOTAL MOVEMENT</td>
                        <td className={`${tdN} font-bold ${negColor(detail.movement_total)}`}>${money(detail.movement_total)}</td>
                      </tr>
                    </tbody>
                  </table>
                )}
              </div>
              {detail.ledger === "ar" && detail.folios.length > 0 && (
                <div>
                  <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink/60">
                    City Ledger invoices (companies / agencies)
                    {detail.ties_to_movement
                      ? <span className="rounded bg-emerald-500/15 px-1.5 text-[10px] text-emerald-700 normal-case">✓ ties to movement</span>
                      : <span className="rounded bg-red-500/15 px-1.5 text-[10px] text-red-600 normal-case">⚠ does not tie</span>}
                  </div>
                  <table className="w-full">
                    <thead><tr>{["Invoice", "Company / Agency", "Guest", "Stay", "Amount"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
                    <tbody>
                      {(detail.folios as ArInvoice[]).map((f) => (
                        <tr key={f.invoice_no} className="border-t border-ink/8">
                          <td className="px-3 py-1.5 font-mono text-ink/85">{f.invoice_no}</td>
                          <td className={td}>{f.account_name}{f.account_number ? <span className="text-ink/60"> · {f.account_number}</span> : null}</td>
                          <td className={td}>{f.guest_name}</td>
                          <td className="px-3 py-1.5 text-ink/60">{f.arrival_date} → {f.departure_date}</td>
                          <td className={`${tdN} font-medium ${negColor(f.amount)}`}>${money(f.amount)}</td>
                        </tr>
                      ))}
                      <tr className="border-t border-ink/15 bg-[#fcfcfb]">
                        <td className={`${td} font-bold`} colSpan={4}>TOTAL INVOICES</td>
                        <td className={`${tdN} font-bold ${negColor(detail.folio_total)}`}>${money(detail.folio_total)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
              {detail.ledger === "guest" && detail.folios.length > 0 && (
                <div>
                  <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Folios (day&apos;s settled documents)</div>
              <table className="w-full">
                <thead><tr>{["Folio", "Guest", "Status", "Total", ""].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
                <tbody>
                  {(detail.folios as Folio[]).map((f) => (
                    <Fragment key={f.bill_no}>
                      <tr className="border-t border-ink/8 cursor-pointer hover:bg-ink/4"
                        onClick={() => setOpenFolio(openFolio === f.bill_no ? null : f.bill_no)}>
                        <td className="px-3 py-1.5 font-mono text-ink/85">{openFolio === f.bill_no ? "▾ " : "▸ "}{f.bill_no}</td>
                        <td className={td}>{f.guest_name}</td>
                        <td className="px-3 py-1.5 text-emerald-600">{f.status}</td>
                        <td className={`${tdN} font-medium ${negColor(f.total_amount)}`}>${money(f.total_amount)}</td>
                        <td className="px-3 py-1.5 text-ink/60">{f.lines.length} lines</td>
                      </tr>
                      {openFolio === f.bill_no && f.lines.map((ln, i) => (
                        <tr key={`${f.bill_no}-${i}`} className="bg-[#f9f9f7]/60 text-ink/70">
                          <td className="px-3 py-1 pl-8 font-mono">{ln.trx_code}</td>
                          <td className="px-3 py-1">{ln.trx_date}</td>
                          <td className={`px-3 py-1 text-right ${negColor(ln.net_amount)}`} colSpan={1}>net ${money(ln.net_amount)}</td>
                          <td className={`px-3 py-1 text-right ${ln.debit_amount ? negColor(ln.debit_amount) : negColor(ln.credit_amount)}`}>{ln.debit_amount ? `debit $${money(ln.debit_amount)}` : ln.credit_amount ? `credit $${money(ln.credit_amount)}` : ""}</td>
                          <td />
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                  <tr className="border-t border-ink/15 bg-[#fcfcfb]">
                    <td className={`${td} font-bold`} colSpan={3}>TOTAL FOLIOS</td>
                    <td className={`${tdN} font-bold ${negColor(detail.folio_total)}`}>${money(detail.folio_total)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
                </div>
              )}
              <p className="text-[11px] text-ink/60">{detail.note}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MarketCode({ m }: { m: Audit["market_code"] }) {
  return (
    <table className="w-full rounded-lg border border-ink/10 text-xs">
      <thead className="bg-[#fcfcfb]"><tr>
        <th className={th}>TCode</th><th className={th}>Description</th>
        {m.codes.map((c) => <th key={c} className={`${th} text-right`}>{c}</th>)}
        <th className={`${th} text-right`}>Total</th>
      </tr></thead>
      <tbody>
        {m.rows.map((r) => (
          <tr key={r.tcode} className="border-t border-ink/8">
            <td className="px-3 py-1.5 font-mono text-ink/85">{r.tcode}</td>
            <td className={td}>{r.description}</td>
            {m.codes.map((c) => <td key={c} className={`${tdN} ${negColor(r.values[c])}`}>{r.values[c] ? `$${money(r.values[c])}` : "—"}</td>)}
            <td className={`${tdN} font-medium ${negColor(r.total)}`}>${money(r.total)}</td>
          </tr>
        ))}
        <tr className="border-t border-ink/15 bg-[#fcfcfb]">
          <td className={`${td} font-bold`} colSpan={2}>TOTAL REVENUE</td>
          {m.codes.map((c) => <td key={c} className={`${tdN} font-bold ${negColor(m.totals[c])}`}>${money(m.totals[c])}</td>)}
          <td className={`${tdN} font-bold ${negColor(Object.values(m.totals).reduce((a, b) => a + b, 0))}`}>${money(Object.values(m.totals).reduce((a, b) => a + b, 0))}</td>
        </tr>
      </tbody>
    </table>
  );
}

function OccTable<K extends string>({ title, keyName, keyLabel, rows, totals }: {
  title: string; keyName: K; keyLabel: string;
  rows: (OccPivot & Record<K, string> & { name: string | null })[]; totals: OccPivot;
}) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">{title}</div>
      <table className="w-full rounded-lg border border-ink/10 text-xs">
        <thead className="bg-[#fcfcfb]"><tr>
          <th className={th}>{keyLabel}</th>
          {["Rooms", "Persons", "No-show", "Canceled"].map((h) => <th key={h} className={`${th} text-right`}>{h}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[keyName]} className="border-t border-ink/8">
              <td className="px-3 py-1.5 text-ink/85">
                {r.name || r[keyName]}
                {r.name && <span className="ml-1 font-mono text-[10px] text-ink/60">({r[keyName]})</span>}
              </td>
              <td className={`${tdN} ${negColor(r.rooms)}`}>{int(r.rooms)}</td>
              <td className={`${tdN} ${negColor(r.persons)}`}>{int(r.persons)}</td>
              <td className={`${tdN} ${r.noshow_rooms ? "text-amber-600" : negColor(r.noshow_rooms)}`}>{int(r.noshow_rooms)}</td>
              <td className={`${tdN} ${r.cancel_rooms ? "text-amber-600" : negColor(r.cancel_rooms)}`}>{int(r.cancel_rooms)}</td>
            </tr>
          ))}
          <tr className="border-t border-ink/15 bg-[#fcfcfb]">
            <td className={`${td} font-bold`}>TOTAL</td>
            <td className={`${tdN} font-bold ${negColor(totals.rooms)}`}>{int(totals.rooms)}</td>
            <td className={`${tdN} font-bold ${negColor(totals.persons)}`}>{int(totals.persons)}</td>
            <td className={`${tdN} font-bold ${negColor(totals.noshow_rooms)}`}>{int(totals.noshow_rooms)}</td>
            <td className={`${tdN} font-bold ${negColor(totals.cancel_rooms)}`}>{int(totals.cancel_rooms)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function Estadisticas({ o }: { o: Occupancy }) {
  if (!o || o.records.length === 0)
    return <Pending what="Occupancy Statistics" needs="No STATISTICS records for this day — run the ingestion." />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <Kpi label="Occupied Rooms" value={int(o.totals.rooms)} tone="text-emerald-600" />
        <Kpi label="Persons (PAX)" value={int(o.totals.persons)} tone="text-sky-600" />
        <Kpi label="No-show" value={int(o.totals.noshow_rooms)} tone={o.totals.noshow_rooms ? "text-amber-600" : "text-ink/70"} />
        <Kpi label="Canceled" value={int(o.totals.cancel_rooms)} tone={o.totals.cancel_rooms ? "text-amber-600" : "text-ink/70"} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <OccTable title="By Market Code" keyName="market_code" keyLabel="Market" rows={o.by_market} totals={o.totals} />
        <OccTable title="By Room Class" keyName="room_class" keyLabel="Class" rows={o.by_room_class} totals={o.totals} />
      </div>
      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Detail (market / class / type)</div>
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead className="bg-[#fcfcfb]"><tr>
            <th className={th}>Market</th><th className={th}>Room Class</th><th className={th}>Room Type</th>
            {["Rooms", "Persons", "No-show", "Canceled"].map((h) => <th key={h} className={`${th} text-right`}>{h}</th>)}
          </tr></thead>
          <tbody>
            {o.records.map((r, i) => (
              <tr key={i} className="border-t border-ink/8">
                <td className="px-3 py-1.5 text-ink/85">
                  {r.market_name || r.market_code}
                  {r.market_name && <span className="ml-1 font-mono text-[10px] text-ink/60">({r.market_code})</span>}
                </td>
                <td className="px-3 py-1.5 text-ink/75">
                  {r.room_class_name || r.room_class}
                  {r.room_class_name && <span className="ml-1 font-mono text-[10px] text-ink/60">({r.room_class})</span>}
                </td>
                <td className="px-3 py-1.5 font-mono text-ink/75">{r.room_type}</td>
                <td className={`${tdN} ${negColor(r.rooms)}`}>{int(r.rooms)}</td>
                <td className={`${tdN} ${negColor(r.persons)}`}>{int(r.persons)}</td>
                <td className={`${tdN} ${negColor(r.noshow_rooms)}`}>{int(r.noshow_rooms)}</td>
                <td className={`${tdN} ${negColor(r.cancel_rooms)}`}>{int(r.cancel_rooms)}</td>
              </tr>
            ))}
            <tr className="border-t border-ink/15 bg-[#fcfcfb] font-bold">
              <td className={td} colSpan={3}>TOTAL</td>
              <td className={`${tdN} ${negColor(o.totals.rooms)}`}>{int(o.totals.rooms)}</td>
              <td className={`${tdN} ${negColor(o.totals.persons)}`}>{int(o.totals.persons)}</td>
              <td className={`${tdN} ${negColor(o.totals.noshow_rooms)}`}>{int(o.totals.noshow_rooms)}</td>
              <td className={`${tdN} ${negColor(o.totals.cancel_rooms)}`}>{int(o.totals.cancel_rooms)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <InhouseComp o={o} />
    </div>
  );
}

// Solo habitaciones In-House (INHOUSE) y Complimentary/Courtesy (COM), agrupadas por room type.
const INHOUSE_COMP_CODES = ["COM", "INHOUSE"];
function InhouseComp({ o }: { o: Occupancy }) {
  const map = new Map<string, { market_code: string; market_name: string | null; room_class_name: string | null; room_type: string | null; rooms: number; persons: number }>();
  for (const r of o.records) {
    if (!r.market_code || !INHOUSE_COMP_CODES.includes(r.market_code)) continue;
    const key = `${r.market_code}|${r.room_type ?? ""}`;
    const cur = map.get(key);
    if (cur) { cur.rooms += r.rooms; cur.persons += r.persons; }
    else map.set(key, { market_code: r.market_code, market_name: r.market_name, room_class_name: r.room_class_name, room_type: r.room_type, rooms: r.rooms, persons: r.persons });
  }
  const rows = [...map.values()].sort(
    (a, b) => a.market_code.localeCompare(b.market_code) || (a.room_type ?? "").localeCompare(b.room_type ?? "")
  );
  const totRooms = rows.reduce((s, r) => s + r.rooms, 0);
  const totPax = rows.reduce((s, r) => s + r.persons, 0);
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">In-House &amp; Complimentary Rooms (COM / INHOUSE)</div>
      {rows.length === 0 ? (
        <div className="rounded-lg border border-ink/10 bg-[#171A28] px-3 py-2 text-xs text-ink/60">
          No hay habitaciones In-House ni Complimentary este día.
        </div>
      ) : (
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead className="bg-[#fcfcfb]"><tr>
            <th className={th}>Market</th><th className={th}>Room Type</th>
            <th className={`${th} text-right`}>Total Rooms</th><th className={`${th} text-right`}>Pax</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-ink/8">
                <td className="px-3 py-1.5 text-ink/85">
                  {r.market_name || r.market_code}
                  <span className="ml-1 font-mono text-[10px] text-ink/60">({r.market_code})</span>
                </td>
                <td className="px-3 py-1.5 font-mono text-ink/75">
                  {r.room_type || "—"}
                  {r.room_class_name && <span className="ml-1 font-sans text-[10px] text-ink/60">{r.room_class_name}</span>}
                </td>
                <td className={tdN}>{int(r.rooms)}</td>
                <td className={tdN}>{int(r.persons)}</td>
              </tr>
            ))}
            <tr className="border-t border-ink/15 bg-[#fcfcfb] font-bold">
              <td className={td} colSpan={2}>TOTAL</td>
              <td className={tdN}>{int(totRooms)}</td>
              <td className={tdN}>{int(totPax)}</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

function PosCheckRow({ r }: { r: PosCheckCheck }) {
  const ok = r.estado === "OK";
  return (
    <tr className="border-t border-ink/8">
      <td className={`${td} font-medium`}>{r.concepto}</td>
      <td className={`${tdN} ${negColor(r.a)}`}>${money(r.a)}</td>
      <td className={`${tdN} ${negColor(r.b)}`}>${money(r.b)}</td>
      <td className={`${tdN} ${ok ? negColor(r.diferencia) || "text-ink/60" : "text-amber-600 font-medium"}`}>${money(r.diferencia)}</td>
      <td className={`px-3 py-1.5 font-medium ${ESTADO_STYLE[r.estado] || "text-ink"}`}>{ok ? "✓ Reconciled" : "⚠ " + (ESTADO_LABEL[r.estado] || r.estado)}</td>
    </tr>
  );
}

function SimphonyPos({ pos }: { pos: PosData }) {
  if (!pos)
    return <Pending what="Simphony POS" needs="No Sales Excel loaded for this day — run the ingestion with the day's file (Tab 1)." />;
  const s = pos.summary;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-5 gap-3">
        <Kpi label="Net Sales" value={`$${money(s.ventas_netas)}`} tone="text-emerald-600" />
        <Kpi label="Service Charges" value={`$${money(s.cargos_servicio)}`} tone="text-sky-600" />
        <Kpi label="Total Sales" value={`$${money(s.total_ventas)}`} tone="text-ink" />
        <Kpi label="Voids" value={`$${money(s.voids)}`} tone={s.voids ? "text-amber-600" : "text-ink/70"} />
        <Kpi label="Room Charges → Opera" value={`$${money(s.room_charge_confirmado)}`} tone="text-emerald-600" />
      </div>

      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">
          Internal Consistency of the Sales Excel
        </div>
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead className="bg-[#fcfcfb]"><tr>
            {["Concept", "A", "B", "Difference", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {pos.internal_checks.map((c) => <PosCheckRow key={c.concepto} r={c} />)}
          </tbody>
        </table>
      </div>

      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">
          Cashier Control — POS (Simphony) vs Opera / Integrity (F&amp;B, §5.6)
        </div>
        {pos.pms_check ? (
          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]"><tr>
              {["Concept", "POS", "PMS/Accounting", "Difference", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
            </tr></thead>
            <tbody>
              <PosCheckRow r={pos.pms_check.opera_recon} />
              <PosCheckRow r={pos.pms_check.integrity_recon} />
            </tbody>
          </table>
        ) : (
          <div className="rounded-lg border border-dashed border-ink/12 bg-[#fcfcfb]/50 p-4 text-xs text-ink/60">
            No Opera/Integrity data loaded for this day — cashier control doesn&apos;t apply
            (not an error, there&apos;s just nothing to reconcile against yet).
          </div>
        )}
      </div>

      {pos.room_charges.length > 0 && (
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">
            Room Charges confirmed by Opera ({pos.room_charges.length} checks)
          </div>
          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]"><tr>
              {["Restaurant", "Employee", "# Check", "Time", "Amount", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
            </tr></thead>
            <tbody>
              {pos.room_charges.map((c, i) => (
                <tr key={i} className="border-t border-ink/8">
                  <td className={td}>{c.restaurant}</td>
                  <td className={td}>{c.employee}</td>
                  <td className="px-3 py-1.5 font-mono text-ink/85">{c.check_num}</td>
                  <td className="px-3 py-1.5 text-ink/60">{c.hora}</td>
                  <td className={`${tdN} ${negColor(c.monto)}`}>${money(c.monto)}</td>
                  <td className="px-3 py-1.5 font-medium text-emerald-600">✓ AnswerStat=OK</td>
                </tr>
              ))}
              <tr className="border-t border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={td} colSpan={4}>TOTAL sent to Opera</td>
                <td className={`${tdN} ${negColor(pos.room_charges.reduce((a, c) => a + c.monto, 0))}`}>${money(pos.room_charges.reduce((a, c) => a + c.monto, 0))}</td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">By Payment Method</div>
          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]"><tr>
              {["Method", "# Checks", "Amount"].map((h) => <th key={h} className={th}>{h}</th>)}
            </tr></thead>
            <tbody>
              {pos.by_payment.map((p) => (
                <tr key={p.forma} className="border-t border-ink/8">
                  <td className={`${td} ${p.forma.toUpperCase().includes("ROOM CHARGE") ? "text-emerald-600 font-medium" : ""}`}>{p.forma}</td>
                  <td className={`${tdN} ${negColor(p.count)}`}>{int(p.count)}</td>
                  <td className={`${tdN} ${negColor(p.total)}`}>${money(p.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">By Employee (cashier control)</div>
          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]"><tr>
              {["Employee", "# Checks", "Amount"].map((h) => <th key={h} className={th}>{h}</th>)}
            </tr></thead>
            <tbody>
              {pos.by_employee.map((e) => (
                <tr key={e.empleado} className="border-t border-ink/8">
                  <td className={td}>{e.empleado}</td>
                  <td className={`${tdN} ${negColor(e.count)}`}>{int(e.count)}</td>
                  <td className={`${tdN} ${negColor(e.total)}`}>${money(e.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-[11px] text-ink/60">
        {pos.total_checks} closed checks · source: {pos.summary.source_file}
      </p>
    </div>
  );
}

function OtbReconRow({ label, r }: { label: string; r: OtbRecon | null }) {
  if (!r) return null;
  const ok = r.estado === "OK";
  return (
    <tr className="border-t border-ink/8">
      <td className={`${td} font-medium`}>{label}</td>
      <td className={`${tdN} ${negColor(r.otb)}`}>${money(r.otb)}</td>
      <td className={`${tdN} ${negColor(r.actual_integrity)}`}>${money(r.actual_integrity)}</td>
      <td className={`${tdN} ${ok ? negColor(r.diferencia) || "text-ink/60" : "text-amber-600 font-medium"}`}>${money(r.diferencia)}</td>
      <td className={`px-3 py-1.5 font-medium ${ESTADO_STYLE[r.estado] || "text-ink"}`}>{ok ? "✓ Reconciled" : "⚠ " + (ESTADO_LABEL[r.estado] || r.estado)}</td>
    </tr>
  );
}

function OtbVsRevenue({ otb }: { otb: OtbData }) {
  if (!otb || (!otb.total && !otb.rooms))
    return <Pending what="OTB vs Revenue" needs="No history_forecast loaded for this day — run the ingestion." />;
  const scopes: { key: string; label: string; d: OtbScope | null }[] = [
    { key: "total", label: "Total (HF full)", d: otb.total },
    { key: "rooms", label: "Rooms Only", d: otb.rooms },
  ];
  return (
    <div className="space-y-5">
      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">
          Reconciliation — each report is reconciled SEPARATELY against Integrity (Opera vs Integrity, §5.4)
        </div>
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead className="bg-[#fcfcfb]"><tr>
            {["OTB Report (Opera)", "OTB", "Actual (Integrity)", "Difference", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
          </tr></thead>
          <tbody>
            <OtbReconRow label="Full Revenue (HF full)" r={otb.full_revenue_recon} />
            <OtbReconRow label="Rooms Only" r={otb.rooms_only_recon} />
          </tbody>
        </table>
        <p className="mt-1 text-[11px] text-ink/60">
          Full Revenue and Rooms Only are different in nature (one is the whole hotel&apos;s total, the
          other is rooms only) — that&apos;s why each is reconciled on its own against Integrity&apos;s
          real revenue, not against each other.
        </p>
      </div>

      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">Detail of each OTB report</div>
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead className="bg-[#fcfcfb]"><tr>
            {["Scope", "Revenue", "Rooms", "Persons", "Inventory", "ADR", "Occupancy %", "Source"].map((h) => <th key={h} className={th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {scopes.filter((s) => s.d).map(({ key, label, d }) => (
              <tr key={key} className="border-t border-ink/8">
                <td className={`${td} font-medium`}>{label}</td>
                <td className={`${tdN} ${negColor(d!.revenue)}`}>${money(d!.revenue)}</td>
                <td className={`${tdN} ${negColor(d!.no_rooms)}`}>{int(d!.no_rooms)}</td>
                <td className={`${tdN} ${negColor(d!.no_persons)}`}>{int(d!.no_persons)}</td>
                <td className={`${tdN} ${negColor(d!.inventory_rooms)}`}>{int(d!.inventory_rooms)}</td>
                <td className={`${tdN} ${negColor(d!.adr)}`}>${money(d!.adr)}</td>
                <td className={`${tdN} ${negColor(d!.occupancy)}`}>{d!.occupancy.toFixed(1)}%</td>
                <td className="px-3 py-1.5 text-ink/60">{d!.source_file}</td>
              </tr>
            ))}
            {otb.actual_stats && (
              <tr className="border-t border-ink/15 bg-[#fcfcfb]">
                <td className={`${td} font-bold text-sky-600`}>Actual</td>
                <td className={`${tdN} font-bold ${negColor(otb.rooms_only_recon?.actual_integrity) || "text-sky-600"}`}>${money(otb.rooms_only_recon?.actual_integrity ?? null)}</td>
                <td className={`${tdN} font-bold ${negColor(otb.actual_stats.rn) || "text-sky-600"}`}>{int(otb.actual_stats.rn)}</td>
                <td className={`${tdN} font-bold ${negColor(otb.actual_stats.pax) || "text-sky-600"}`}>{int(otb.actual_stats.pax)}</td>
                <td className={`${tdN} font-bold ${negColor(otb.actual_stats.available) || "text-sky-600"}`}>
                  {int(otb.actual_stats.available)}
                  {otb.actual_stats.available_real_opera !== otb.actual_stats.available && (
                    <span className="ml-1 font-normal text-amber-600">
                      (Opera: {int(otb.actual_stats.available_real_opera)})
                    </span>
                  )}
                </td>
                <td className={`${tdN} font-bold ${negColor(otb.actual_stats.adr) || "text-sky-600"}`}>${money(otb.actual_stats.adr)}</td>
                <td className={`${tdN} font-bold text-sky-600`}>{(otb.actual_stats.occupancy_pct * 100).toFixed(1)}%</td>
                <td className="px-3 py-1.5 text-ink/60">Revenue/ADR: Integrity · RN/Pax/Inv: fact_room_stat · Available: fixed at 30</td>
              </tr>
            )}
          </tbody>
        </table>
        {otb.non_room_revenue !== null && (
          <p className="mt-1 text-[11px] text-ink/60">
            For reference: Full Revenue − Rooms Only = <span className={`text-ink/75 ${negColor(otb.non_room_revenue)}`}>${money(otb.non_room_revenue)}</span> of
            non-lodging revenue (F&amp;B, tours, etc.) per the OTB report itself — this is NOT a
            reconciliation, it&apos;s contextual data within the same Opera report.
          </p>
        )}
      </div>

      {otb.rooms && otb.actual_stats && (
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wide text-ink/60">
            Comparison by concept — OTB Rooms Only vs Actual (Revenue/ADR from Integrity · RN/Pax/Inventory from Opera)
          </div>
          <table className="w-full rounded-lg border border-ink/10 text-xs">
            <thead className="bg-[#fcfcfb]"><tr>
              {["Concept", "OTB (Rooms Only)", "Actual", "Difference", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}
            </tr></thead>
            <tbody>
              {([
                ["Rooms (RN)", otb.rooms.no_rooms, otb.actual_stats.rn, (v: number) => int(v)],
                ["Persons (Pax)", otb.rooms.no_persons, otb.actual_stats.pax, (v: number) => int(v)],
                ["Available Inventory", otb.rooms.inventory_rooms, otb.actual_stats.available, (v: number) => int(v)],
                ["ADR", otb.rooms.adr, otb.actual_stats.adr, (v: number) => `$${money(v)}`],
                ["Occupancy %", otb.rooms.occupancy, otb.actual_stats.occupancy_pct * 100, (v: number) => `${v.toFixed(1)}%`],
              ] as [string, number, number, (v: number) => string][]).map(([label, otbVal, realVal, fmt]) => {
                const dif = Math.round((realVal - otbVal) * 100) / 100;
                const ok = Math.abs(dif) < 0.05;
                return (
                  <tr key={label} className="border-t border-ink/8">
                    <td className={`${td} font-medium`}>{label}</td>
                    <td className={`${tdN} ${negColor(otbVal)}`}>{fmt(otbVal)}</td>
                    <td className={`${tdN} ${negColor(realVal)}`}>{fmt(realVal)}</td>
                    <td className={`${tdN} ${ok ? negColor(dif) || "text-ink/60" : "text-amber-600 font-medium"}`}>{ok ? "0" : (dif > 0 ? "+" : "") + fmt(dif)}</td>
                    <td className={`px-3 py-1.5 font-medium ${ok ? "text-emerald-600" : "text-amber-600"}`}>{ok ? "✓ Reconciled" : "⚠ Review"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-1 text-[11px] text-ink/60">
            Compared against Rooms Only because it&apos;s the OTB report directly equivalent to the
            physical rooms operation (Full Revenue blends in other revenue). If Inventory or
            Occupancy don&apos;t match, the OTB is using an availability assumption different from the
            day&apos;s actual (e.g. out-of-service rooms not reflected in the forecast).
          </p>
        </div>
      )}
    </div>
  );
}

function HallazgosYTD() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftEstado, setDraftEstado] = useState("cerrado");
  const [draftNote, setDraftNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/audit/findings?estado=abierto`, { cache: "no-store" });
      setFindings(res.ok ? await res.json() : []);
    } catch {
      setFindings([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // The default value ("cerrado") matches the real DB enum -- don't
  // translate it, only the label shown in the <select> (see below).
  function startEdit(f: Finding) {
    setEditingId(f.id ?? null);
    setDraftEstado("cerrado");
    setDraftNote("");
    setError("");
  }

  async function save(id: string) {
    setSaving(true); setError("");
    try {
      const res = await fetch(`${API_URL}/audit/findings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estado: draftEstado, resolved_note: draftNote || null }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `API ${res.status}`);
      setEditingId(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const year = new Date().getFullYear();

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-ink/75">
          Open Findings — Year to Date {year} ({findings.length})
        </h3>
        {loading && <span className="text-xs text-ink/60">Loading…</span>}
      </div>
      {findings.length === 0 && !loading ? (
        <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-6 text-sm text-emerald-600">
          No open findings so far this year.
        </div>
      ) : (
        <table className="w-full rounded-lg border border-ink/10 text-xs">
          <thead className="bg-[#fcfcfb]"><tr>
            {["Day", "TCode", "Area", "Type", "Amount", "Comment", "Status", ""].map((h) => <th key={h} className={th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {findings.map((f) => (
              <Fragment key={f.id}>
                <tr className="border-t border-ink/8">
                  <td className="px-3 py-1.5 font-mono text-ink/70">{f.business_date}</td>
                  <td className="px-3 py-1.5 font-mono text-ink/85">{f.tcode ?? "—"}</td>
                  <td className={td}>{f.area}</td>
                  <td className="px-3 py-1.5 text-amber-600">{(f.tipo_desviacion && ESTADO_LABEL[f.tipo_desviacion]) || f.tipo_desviacion}</td>
                  <td className={`${tdN} ${negColor(f.monto)}`}>${money(f.monto)}</td>
                  <td className="px-3 py-1.5 text-ink/60">{f.comentario}</td>
                  <td className="px-3 py-1.5 text-amber-600">{f.estado === "abierto" ? "open" : f.estado === "cerrado" ? "closed" : f.estado}</td>
                  <td className="px-3 py-1.5">
                    {editingId !== f.id && (
                      <button onClick={() => startEdit(f)}
                        className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:text-ink">
                        Change status
                      </button>
                    )}
                  </td>
                </tr>
                {editingId === f.id && (
                  <tr className="border-t border-ink/8 bg-[#fcfcfb]/50">
                    <td colSpan={8} className="px-3 py-3">
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-2">
                          <label className="text-[11px] text-ink/70">New status:</label>
                          <select value={draftEstado} onChange={(e) => setDraftEstado(e.target.value)}
                            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-xs text-ink">
                            <option value="cerrado">closed</option>
                            <option value="abierto">open</option>
                          </select>
                        </div>
                        <textarea value={draftNote} onChange={(e) => setDraftNote(e.target.value)}
                          placeholder="Detailed comment: what was investigated, with whom, how it was resolved…"
                          rows={4}
                          className="w-full rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1.5 text-xs text-ink placeholder:text-ink/45" />
                        {error && <div className="text-[11px] text-red-600">{error}</div>}
                        <div className="flex gap-2">
                          <button onClick={() => save(f.id!)} disabled={saving}
                            className="rounded bg-accent px-3 py-1 text-[11px] text-white disabled:opacity-50">
                            {saving ? "Saving…" : "Save"}
                          </button>
                          <button onClick={() => setEditingId(null)}
                            className="rounded bg-ink/5 px-3 py-1 text-[11px] text-ink/75">
                            Cancel
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Hallazgos({ findings }: { findings: Finding[] }) {
  if (findings.length === 0)
    return <div className="rounded-lg border border-ink/10 bg-[#fcfcfb] p-6 text-sm text-emerald-600">No open findings.</div>;
  return (
    <table className="w-full rounded-lg border border-ink/10 text-xs">
      <thead className="bg-[#fcfcfb]"><tr>
        {["Day", "TCode", "Area", "Type", "Amount", "Status", "Comment"].map((h) => <th key={h} className={th}>{h}</th>)}
      </tr></thead>
      <tbody>
        {findings.map((f, i) => (
          <tr key={`${f.tcode ?? "sin-tcode"}-${f.area ?? ""}-${i}`} className="border-t border-ink/8">
            <td className="px-3 py-1.5 font-mono text-ink/70">{f.business_date ?? "—"}</td>
            <td className="px-3 py-1.5 font-mono text-ink/85">{f.tcode ?? "—"}</td>
            <td className={td}>{f.area}</td>
            <td className="px-3 py-1.5 text-amber-600">{(f.tipo_desviacion && ESTADO_LABEL[f.tipo_desviacion]) || f.tipo_desviacion}</td>
            <td className={`${tdN} ${negColor(f.monto)}`}>${money(f.monto)}</td>
            <td className="px-3 py-1.5 text-ink/70">{f.estado === "abierto" ? "open" : f.estado === "cerrado" ? "closed" : f.estado}</td>
            <td className="px-3 py-1.5 text-ink/60">{f.comentario}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
