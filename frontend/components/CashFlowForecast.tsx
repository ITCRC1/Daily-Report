"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

type Scn = { scenario: string; label: string; opening: number; net: number[]; begin_override: (number | null)[]; beginning: number[]; ending: number[]; net_total: number; ending_total: number };
type FData = { year: number; opening_label: string; months: string[]; scenarios: Scn[] };
type Form = Record<string, { opening: string; net: string[]; begin: string[] }>;

const money = (v: number) =>
  v < 0 ? `($${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`
    : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const numOf = (s: string) => parseFloat(s) || 0;

export default function CashFlowForecast({ year }: { year: number }) {
  const [meta, setMeta] = useState<{ months: string[]; opening_label: string; order: { key: string; label: string }[] } | null>(null);
  const [form, setForm] = useState<Form>({});
  const [focused, setFocused] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr(""); setMsg("");
    try {
      const r = await fetch(`${API_URL}/cash/flow-forecast?year=${year}`, { cache: "no-store" });
      const j: FData = await r.json();
      if ((j as any).detail) { setErr((j as any).detail); return; }
      const f: Form = {};
      for (const s of j.scenarios) f[s.scenario] = {
        opening: s.opening ? String(s.opening) : "",
        net: s.net.map((v) => (v ? String(v) : "")),
        begin: (s.begin_override ?? []).map((v) => (v === null || v === undefined ? "" : String(v))),
      };
      setForm(f);
      setMeta({ months: j.months, opening_label: j.opening_label, order: j.scenarios.map((s) => ({ key: s.scenario, label: s.label })) });
      setDirty(false);
    } catch (e: any) { setErr(String(e)); } finally { setLoading(false); }
  }, [year]);
  useEffect(() => { load(); }, [load]);

  const calc = (scn: string) => {
    const f = form[scn] ?? { opening: "", net: [], begin: [] };
    const opening = numOf(f.opening);
    const nets = Array.from({ length: 12 }, (_, i) => numOf(f.net[i] ?? ""));
    const beginning: number[] = [], ending: number[] = [];
    for (let i = 0; i < 12; i++) {
      const ov = f.begin?.[i] ?? "";
      const beg = ov !== "" ? numOf(ov) : (i === 0 ? opening : ending[i - 1]);
      beginning.push(beg); ending.push(beg + nets[i]);
    }
    return { opening, nets, beginning, ending, netTotal: nets.reduce((a, x) => a + x, 0), endTotal: ending[11] };
  };

  const setOpening = (scn: string, v: string) => { if (v !== "" && !/^-?\d*\.?\d*$/.test(v)) return; setForm((p) => ({ ...p, [scn]: { ...p[scn], opening: v } })); setDirty(true); setMsg(""); };
  const setNet = (scn: string, i: number, v: string) => { if (v !== "" && !/^-?\d*\.?\d*$/.test(v)) return; setForm((p) => { const net = [...(p[scn]?.net ?? [])]; net[i] = v; return { ...p, [scn]: { ...p[scn], net } }; }); setDirty(true); setMsg(""); };
  const setBegin = (scn: string, i: number, v: string) => { if (v !== "" && !/^-?\d*\.?\d*$/.test(v)) return; setForm((p) => { const begin = [...(p[scn]?.begin ?? [])]; begin[i] = v; return { ...p, [scn]: { ...p[scn], begin } }; }); setDirty(true); setMsg(""); };

  const save = async () => {
    if (!meta) return;
    setSaving(true); setErr(""); setMsg("");
    try {
      for (const { key } of meta.order) {
        const f = form[key] ?? { opening: "", net: [], begin: [] };
        await fetch(`${API_URL}/cash/flow-forecast?year=${year}&scenario=${key}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            opening: numOf(f.opening),
            net: Array.from({ length: 12 }, (_, i) => numOf(f.net[i] ?? "")),
            begin: Array.from({ length: 12 }, (_, i) => { const s = f.begin?.[i] ?? ""; return s === "" ? null : numOf(s); }),
          }),
        });
      }
      setDirty(false); setMsg(`✓ Saved ${new Date().toLocaleTimeString()}`);
    } catch (e: any) { setErr(String(e)); } finally { setSaving(false); }
  };

  if (!meta) return <div className="text-xs text-white/40">{err ? `(${err})` : "Loading…"}</div>;

  const cols = [meta.opening_label, ...meta.months, "Total"];
  const inp = "w-[92px] rounded border border-white/10 bg-[#0f1118] px-1.5 py-1 text-right tabular-nums text-white/90 focus:border-accent focus:outline-none";
  const cellN = "px-1.5 py-1 text-right tabular-nums whitespace-nowrap";
  const neg = (v: number) => (v < 0 ? "text-rose-400" : "");
  const editCell = (key: string, val: string, onCh: (v: string) => void) => (
    <input type="text" inputMode="decimal" className={`${inp} ${numOf(val) < 0 ? "!text-rose-400" : ""}`}
      value={focused === key ? val : val === "" ? "" : money(numOf(val))} placeholder="0.00"
      onFocus={() => setFocused(key)} onBlur={() => setFocused(null)} onChange={(e) => onCh(e.target.value)} />
  );
  // Beginning Cash editable: vacío = usa el roll-forward (Ending del mes anterior),
  // que se muestra como placeholder gris; si se escribe, sobreescribe.
  const beginCell = (scn: string, i: number, eff: number) => {
    const key = `${scn}:b${i}`;
    const ov = form[scn]?.begin?.[i] ?? "";
    const shown = ov !== "" ? numOf(ov) : eff;
    return (
      <input type="text" inputMode="decimal" className={`${inp} ${shown < 0 ? "!text-rose-400" : ""} ${ov === "" ? "text-white/50" : ""}`}
        value={focused === key ? ov : ov === "" ? "" : money(numOf(ov))} placeholder={money(eff)}
        onFocus={() => setFocused(key)} onBlur={() => setFocused(null)} onChange={(e) => setBegin(scn, i, e.target.value)} />
    );
  };

  // variancias en vivo: Current − otros (Ending Cash)
  const cur = calc("current");
  const variances = meta.order.filter((o) => o.key !== "current").map((o) => {
    const s = calc(o.key);
    return { label: `Variance: Current − ${o.label}`, values: cur.ending.map((e, i) => e - s.ending[i]), total: cur.endTotal - s.endTotal };
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-white/90">Full Year Cash Flow Forecast {year} vs Budget {year}</h2>
        <div className="flex items-center gap-2 text-[11px]">
          {dirty && <span className="text-amber-300/80">unsaved changes</span>}
          {msg && <span className="text-emerald-400">{msg}</span>}
          <button onClick={save} disabled={saving || !dirty}
            className={`rounded px-3 py-1 ${dirty ? "bg-accent text-white hover:brightness-110" : "bg-white/10 text-white/40"}`}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
      <p className="text-[11px] text-white/40">
        Editable: <b>Net Change in Cash</b> de cada mes y el saldo de arranque (Ending Cash de {meta.opening_label}).
        Beginning/Ending Cash y los totales se calculan solos (roll-forward). {loading && "· cargando…"}
      </p>
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}

      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="text-[11px]">
          <thead className="bg-[#1E2130]">
            <tr>
              <th className="sticky left-0 z-10 bg-[#1E2130] px-2 py-1.5 text-left font-medium text-white/60">&nbsp;</th>
              {cols.map((c) => <th key={c} className="px-1.5 py-1.5 text-right font-medium text-white/60 whitespace-nowrap">{c}</th>)}
            </tr>
          </thead>
          {meta.order.map(({ key, label }) => {
              const c = calc(key);
              return (
                <tbody key={key} className="border-t-2 border-white/20">
                  <tr className="bg-[#16233a]"><td className="sticky left-0 z-10 bg-[#16233a] px-2 py-1 font-bold text-sky-200" colSpan={cols.length + 1}>{label}</td></tr>
                  {/* Net Change in Cash — editable */}
                  <tr className="border-t border-white/5">
                    <td className="sticky left-0 z-10 bg-[#0f1118] px-2 py-1 text-left text-white/80 whitespace-nowrap">Net Change in Cash</td>
                    <td className={cellN} />
                    {Array.from({ length: 12 }, (_, i) => <td key={i} className="px-1 py-0.5 text-right">{editCell(`${key}:n${i}`, form[key]?.net[i] ?? "", (v) => setNet(key, i, v))}</td>)}
                    <td className={`${cellN} font-medium ${neg(c.netTotal)}`}>{money(c.netTotal)}</td>
                  </tr>
                  {/* Beginning Cash — editable (vacío = roll-forward) */}
                  <tr className="border-t border-white/5">
                    <td className="sticky left-0 z-10 bg-[#0f1118] px-2 py-1 text-left text-white/70 whitespace-nowrap">Beginning Cash</td>
                    <td className={cellN} />
                    {c.beginning.map((v, i) => <td key={i} className="px-1 py-0.5 text-right">{beginCell(key, i, v)}</td>)}
                    <td className={cellN} />
                  </tr>
                  {/* Ending Cash — Dec-prev editable (opening), resto computado */}
                  <tr className="border-t border-white/5 bg-[#12151f]">
                    <td className="sticky left-0 z-10 bg-[#12151f] px-2 py-1 text-left font-medium text-white/80 whitespace-nowrap">Ending Cash</td>
                    <td className="px-1 py-0.5 text-right">{editCell(`${key}:op`, form[key]?.opening ?? "", (v) => setOpening(key, v))}</td>
                    {c.ending.map((v, i) => <td key={i} className={`${cellN} font-medium ${neg(v)}`}>{money(v)}</td>)}
                    <td className={`${cellN} font-bold ${neg(c.endTotal)}`}>{money(c.endTotal)}</td>
                  </tr>
                </tbody>
              );
            })}
            {/* Variancias */}
            {variances.map((vr) => (
              <tbody key={vr.label} className="border-t-2 border-white/20">
                <tr className="bg-[#231c17]">
                  <td className="sticky left-0 z-10 bg-[#231c17] px-2 py-1 font-medium text-amber-200/80 whitespace-nowrap">{vr.label}</td>
                  <td className={cellN} />
                  {vr.values.map((v, i) => <td key={i} className={`${cellN} ${neg(v)}`}>{money(v)}</td>)}
                  <td className={`${cellN} font-medium ${neg(vr.total)}`}>{money(vr.total)}</td>
                </tr>
              </tbody>
            ))}
        </table>
      </div>
    </div>
  );
}
