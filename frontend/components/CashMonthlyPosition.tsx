"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";
import { useBusinessDate } from "@/lib/useBusinessDate";

// Campos editables (deben coincidir con el backend MonthlyCashPositionIn)
type Vals = {
  opening: number; other_collections: number;
  pay_vendors: number; pay_capital: number; pay_payroll: number;
  pay_social_security: number; pay_ins: number; pay_hacienda: number;
  other_pay_1: number; other_pay_2: number; other_pay_3: number; other_pay_4: number;
};
type CardFees = {
  pos_base: number; ecom_base: number; pos_fee: number; ecom_fee: number; total_fees: number;
  pos_commission_pct: number; pos_retention_pct: number;
  ecom_commission_pct: number; ecom_retention_pct: number;
  rates_inherited_from?: string | null;
};
type Resp = Vals & {
  year: number; month: number; as_of: string; mtd_operation: number;
  mtd_operation_gross?: number; mtd_operation_net?: number; card_fees?: CardFees;
  total_payments: number; month_balance: number;
};

const RATE_KEYS = ["pos_commission_pct", "pos_retention_pct", "ecom_commission_pct", "ecom_retention_pct"] as const;
type RateKey = typeof RATE_KEYS[number];
const RATES_ZERO: Record<RateKey, string> = {
  pos_commission_pct: "", pos_retention_pct: "", ecom_commission_pct: "", ecom_retention_pct: "",
};

const ZERO: Vals = {
  opening: 0, other_collections: 0, pay_vendors: 0, pay_capital: 0, pay_payroll: 0,
  pay_social_security: 0, pay_ins: 0, pay_hacienda: 0,
  other_pay_1: 0, other_pay_2: 0, other_pay_3: 0, other_pay_4: 0,
};
const PAY_KEYS: (keyof Vals)[] = ["pay_vendors", "pay_capital", "pay_payroll", "pay_social_security",
  "pay_ins", "pay_hacienda", "other_pay_1", "other_pay_2", "other_pay_3", "other_pay_4"];

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];
const money = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function CashMonthlyPosition() {
  const anchor = useBusinessDate();
  const ad = new Date(anchor + "T00:00:00");
  // Selector de mes/año PROPIO (independiente del Día global). Arranca en el
  // mes del Día; después el owner lo cambia sin mover el Día.
  const [year, setYear] = useState(ad.getFullYear());
  const [month, setMonth] = useState(ad.getMonth() + 1);
  const yearOpts = [ad.getFullYear() - 1, ad.getFullYear(), ad.getFullYear() + 1];

  const KEYS = Object.keys(ZERO) as (keyof Vals)[];
  const emptyForm = () => Object.fromEntries(KEYS.map((k) => [k, ""])) as Record<keyof Vals, string>;
  const [form, setForm] = useState<Record<keyof Vals, string>>(emptyForm);
  const [mtd, setMtd] = useState(0);           // neto (viene del backend con las tasas guardadas)
  const [gross, setGross] = useState(0);       // bruto = Real Cash MTD
  const [posBase, setPosBase] = useState(0);   // Real Cash cobrado por POS
  const [ecomBase, setEcomBase] = useState(0); // Real Cash cobrado por Ecommerce
  const [rates, setRates] = useState<Record<RateKey, string>>(RATES_ZERO);
  const [inheritedFrom, setInheritedFrom] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  // Labels editables de las 4 líneas "Other Payment" (globales por propiedad).
  const [labels, setLabels] = useState<Record<string, string>>({
    other_pay_1: "Other Payment #1", other_pay_2: "Other Payment #2",
    other_pay_3: "Other Payment #3", other_pay_4: "Other Payment #4",
  });

  const num = (k: keyof Vals) => parseFloat(form[k]) || 0;
  // Campo enfocado: mientras se edita se muestra el número crudo; al salir se
  // muestra formateado con separadores (ej. 385,030.83), como la línea MTD.
  const [focused, setFocused] = useState<keyof Vals | null>(null);
  const display = (k: keyof Vals) => (focused === k ? form[k] : form[k] === "" ? "" : money(num(k)));

  const load = useCallback(async () => {
    setLoading(true); setErr(""); setMsg("");
    try {
      const r = await fetch(`${API_URL}/cash/monthly-position?year=${year}&month=${month}&as_of=${anchor}`, { cache: "no-store" });
      const j: Resp = await r.json();
      if ((j as any).detail) { setErr((j as any).detail); return; }
      setForm(Object.fromEntries(KEYS.map((k) => [k, j[k] ? String(j[k]) : ""])) as Record<keyof Vals, string>);
      if ((j as any).labels) setLabels((j as any).labels);
      setMtd(j.mtd_operation);
      setGross(j.mtd_operation_gross ?? j.mtd_operation);
      const cf = j.card_fees;
      if (cf) {
        setPosBase(cf.pos_base); setEcomBase(cf.ecom_base);
        setInheritedFrom(cf.rates_inherited_from ?? null);
        setRates({
          pos_commission_pct: cf.pos_commission_pct ? String(cf.pos_commission_pct) : "",
          pos_retention_pct: cf.pos_retention_pct ? String(cf.pos_retention_pct) : "",
          ecom_commission_pct: cf.ecom_commission_pct ? String(cf.ecom_commission_pct) : "",
          ecom_retention_pct: cf.ecom_retention_pct ? String(cf.ecom_retention_pct) : "",
        });
      }
      setDirty(false);
    } catch (e: any) { setErr(String(e)); } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month, anchor]);
  useEffect(() => { load(); }, [load]);

  // Neto = bruto − comisiones/retención de tarjeta (POS + Ecommerce). Se computa
  // en vivo con las tasas del formulario para que el balance reaccione al editar.
  const rnum = (k: RateKey) => parseFloat(rates[k]) || 0;
  const posFee = posBase * (rnum("pos_commission_pct") + rnum("pos_retention_pct")) / 100;
  const ecomFee = ecomBase * (rnum("ecom_commission_pct") + rnum("ecom_retention_pct")) / 100;
  const totalFees = posFee + ecomFee;
  const netOp = gross - totalFees;

  const totalPayments = useMemo(() => PAY_KEYS.reduce((a, k) => a + (parseFloat(form[k]) || 0), 0), [form]);
  const totalCollections = netOp + num("opening") + num("other_collections");
  const balance = totalCollections - totalPayments;

  // Guarda el TEXTO crudo mientras se edita (permite decimales / borrar); se
  // parsea a número solo para el cálculo y el guardado.
  const set = (k: keyof Vals, v: string) => {
    if (v !== "" && !/^-?\d*\.?\d*$/.test(v)) return;
    setForm((p) => ({ ...p, [k]: v })); setDirty(true); setMsg("");
  };
  const setRate = (k: RateKey, v: string) => {
    if (v !== "" && !/^\d*\.?\d*$/.test(v)) return;
    setRates((p) => ({ ...p, [k]: v })); setDirty(true); setMsg("");
  };

  const save = async () => {
    setSaving(true); setErr(""); setMsg("");
    try {
      const payload: Record<string, unknown> = Object.fromEntries(KEYS.map((k) => [k, num(k)]));
      RATE_KEYS.forEach((k) => { payload[k] = rnum(k); });
      payload.labels = labels;
      const r = await fetch(`${API_URL}/cash/monthly-position?year=${year}&month=${month}&as_of=${anchor}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const j: Resp = await r.json();
      if ((j as any).detail) { setErr((j as any).detail); return; }
      setMtd(j.mtd_operation); setDirty(false); setMsg(`✓ Saved ${new Date().toLocaleTimeString()}`);
    } catch (e: any) { setErr(String(e)); } finally { setSaving(false); }
  };

  const inputCls = "w-40 rounded border border-white/15 bg-[#0f1118] px-2 py-1 text-right tabular-nums text-white/90 focus:border-accent focus:outline-none";
  const rowL = "px-3 py-1.5 text-left text-white/80";
  // Función (NO componente) para no remontar el input en cada tecla (perdía el foco).
  const editRow = (label: string, k: keyof Vals, indent?: boolean) => (
    <tr className="border-t border-white/5">
      <td className={`${rowL} ${indent ? "pl-6 text-white/60" : ""}`}>{label}</td>
      <td className="px-3 py-1.5 text-right">
        <span className="mr-2 text-white/30">$</span>
        <input type="text" inputMode="decimal" value={display(k)} placeholder="0.00"
          onFocus={() => setFocused(k)} onBlur={() => setFocused(null)}
          onChange={(e) => set(k, e.target.value)} className={inputCls} />
      </td>
    </tr>
  );
  // Fila con el CONCEPTO (label) editable + el monto (para las 4 "Other Payment").
  const setLabel = (k: string, v: string) => { setLabels((p) => ({ ...p, [k]: v })); setDirty(true); setMsg(""); };
  const editRowNamed = (k: keyof Vals) => (
    <tr className="border-t border-white/5">
      <td className="px-3 py-1.5">
        <input type="text" value={labels[k] ?? ""} placeholder="Description…"
          onChange={(e) => setLabel(k, e.target.value)}
          className="w-64 rounded border border-dashed border-white/20 bg-[#0f1118] px-2 py-1 text-left text-white/90 focus:border-accent focus:outline-none" />
      </td>
      <td className="px-3 py-1.5 text-right">
        <span className="mr-2 text-white/30">$</span>
        <input type="text" inputMode="decimal" value={display(k)} placeholder="0.00"
          onFocus={() => setFocused(k)} onBlur={() => setFocused(null)}
          onChange={(e) => set(k, e.target.value)} className={inputCls} />
      </td>
    </tr>
  );

  const rateInput = "w-20 rounded border border-white/15 bg-[#0f1118] px-2 py-1 text-right tabular-nums text-white/90 focus:border-accent focus:outline-none";
  const rateRow = (label: string, base: number, commK: RateKey, retK: RateKey, fee: number) => (
    <tr className="border-t border-white/5">
      <td className="px-2 py-1.5 text-white/80">{label}</td>
      <td className="px-2 py-1.5 text-right tabular-nums text-white/70">${money(base)}</td>
      <td className="px-2 py-1.5 text-right">
        <input type="text" inputMode="decimal" value={rates[commK]} placeholder="0"
          onChange={(e) => setRate(commK, e.target.value)} className={rateInput} />
      </td>
      <td className="px-2 py-1.5 text-right">
        <input type="text" inputMode="decimal" value={rates[retK]} placeholder="0"
          onChange={(e) => setRate(retK, e.target.value)} className={rateInput} />
      </td>
      <td className="px-2 py-1.5 text-right tabular-nums text-rose-300/80">${money(fee)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums text-emerald-300">${money(base - fee)}</td>
    </tr>
  );

  return (
    <div className="max-w-2xl space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-white/90">Monthly Cash Position</h2>
          <select value={month} onChange={(e) => setMonth(parseInt(e.target.value, 10))}
            className="rounded border border-white/15 bg-[#0f1118] px-2 py-1 text-[12px] text-white/90 focus:border-accent focus:outline-none">
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select value={year} onChange={(e) => setYear(parseInt(e.target.value, 10))}
            className="rounded border border-white/15 bg-[#0f1118] px-2 py-1 text-[12px] text-white/90 focus:border-accent focus:outline-none">
            {yearOpts.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
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
        All lines are editable (manual input) except <b>MTD Cash collected from the Operation</b>, which is calculated from Tab 5 =
        {" "}<b>Real Cash</b> for the month to date (excludes AR and Non-Cash). Month Balance recalculates automatically.
      </p>
      {loading && <div className="text-xs text-white/40">Loading…</div>}
      {err && <div className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-300">{err}</div>}

      <table className="w-full overflow-hidden rounded-lg border border-white/10 text-sm">
        <tbody>
          {editRow("Opening Cash Balance", "opening")}
          <tr className="border-t border-white/5 bg-[#16233a]/60">
            <td className={rowL}>
              MTD Cash collected — bruto <span className="text-[10px] text-white/40">(Real Cash)</span>
              <button onClick={() => setModalOpen(true)}
                className="ml-2 rounded border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 text-[10px] text-sky-300 hover:bg-sky-500/20">
                🔧 Comisiones tarjeta
              </button>
            </td>
            <td className="px-3 py-1.5 text-right tabular-nums text-white/70"><span className="mr-2 text-white/30">$</span>{money(gross)}</td>
          </tr>
          <tr className="border-t border-white/5">
            <td className={`${rowL} pl-6 text-white/50`}>
              (−) Comisiones + retención tarjeta <span className="text-[10px] text-white/35">(POS + Ecommerce)</span>
            </td>
            <td className="px-3 py-1.5 text-right tabular-nums text-rose-300/80">
              {totalFees ? <>(<span className="text-white/30">$</span>{money(totalFees)})</> : <span className="text-white/30">—</span>}
            </td>
          </tr>
          <tr className="border-t border-white/5 bg-[#16233a]">
            <td className={rowL}>MTD Cash collected — <b className="text-emerald-300">neto</b> <span className="text-[10px] text-emerald-300/60">(alimenta el cash flow)</span></td>
            <td className="px-3 py-1.5 text-right tabular-nums font-medium text-emerald-300"><span className="mr-2 text-white/30">$</span>{money(netOp)}</td>
          </tr>
          {editRow("Other Cash Collections", "other_collections")}
          <tr><td className="py-1.5" colSpan={2} /></tr>
          {editRow("Payments to Vendors", "pay_vendors")}
          {editRow("Capital payments", "pay_capital")}
          {editRow("Payroll Payment", "pay_payroll")}
          {editRow("Social Security Payment", "pay_social_security")}
          {editRow("INS Payment", "pay_ins")}
          {editRow("Hacienda Taxes", "pay_hacienda")}
          {editRowNamed("other_pay_1")}
          {editRowNamed("other_pay_2")}
          {editRowNamed("other_pay_3")}
          {editRowNamed("other_pay_4")}
          <tr className="border-t border-white/20 bg-[#1E2130] font-medium text-white/80">
            <td className={rowL}>Total Payments</td>
            <td className="px-3 py-1.5 text-right tabular-nums text-rose-300"><span className="mr-2 text-white/30">$</span>({money(totalPayments)})</td>
          </tr>
          <tr className={`border-t-2 border-white/30 font-bold ${balance < 0 ? "bg-red-500/15" : "bg-emerald-500/15"}`}>
            <td className={rowL}>Month Balance</td>
            <td className={`px-3 py-2 text-right tabular-nums ${balance < 0 ? "text-red-300" : "text-emerald-300"}`}>
              <span className="mr-2 text-white/30">$</span>{money(balance)}
            </td>
          </tr>
        </tbody>
      </table>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setModalOpen(false)}>
          <div className="w-full max-w-xl rounded-xl border border-white/15 bg-[#141824] p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-1 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Comisiones y retención de tarjeta</h3>
              <button onClick={() => setModalOpen(false)} className="text-white/40 hover:text-white">✕</button>
            </div>
            <p className="mb-3 text-[11px] text-white/50">
              Tasas que se descuentan al <b>bruto</b> para dejar el <b>neto</b> que va al cash flow.
              Aplican solo a los cobros con tarjeta (POS y Ecommerce). En porcentaje (ej. <b>2.5</b> = 2.5%).
            </p>
            {inheritedFrom && (
              <div className="mb-3 rounded border border-sky-500/30 bg-sky-500/10 px-2.5 py-1.5 text-[11px] text-sky-200">
                ↴ Tasas <b>heredadas de {inheritedFrom}</b> (este mes no tiene propias). Se aplican automáticamente;
                editá y guardá solo si cambiaron para este mes.
              </div>
            )}
            <table className="w-full text-xs">
              <thead>
                <tr className="text-white/50">
                  <th className="px-2 py-1 text-left font-medium">Canal</th>
                  <th className="px-2 py-1 text-right font-medium">Base (Real Cash)</th>
                  <th className="px-2 py-1 text-right font-medium">Comisión %</th>
                  <th className="px-2 py-1 text-right font-medium">Retención %</th>
                  <th className="px-2 py-1 text-right font-medium">Deducción</th>
                  <th className="px-2 py-1 text-right font-medium">Neto</th>
                </tr>
              </thead>
              <tbody>
                {rateRow("POS", posBase, "pos_commission_pct", "pos_retention_pct", posFee)}
                {rateRow("Ecommerce", ecomBase, "ecom_commission_pct", "ecom_retention_pct", ecomFee)}
              </tbody>
            </table>
            <div className="mt-4 space-y-1 rounded-lg border border-white/10 bg-[#0f1118] p-3 text-xs">
              <div className="flex justify-between"><span className="text-white/60">Bruto (Real Cash MTD)</span><span className="tabular-nums text-white/80">${money(gross)}</span></div>
              <div className="flex justify-between"><span className="text-white/60">(−) Comisiones + retención</span><span className="tabular-nums text-rose-300">(${money(totalFees)})</span></div>
              <div className="flex justify-between border-t border-white/10 pt-1 font-semibold"><span className="text-emerald-300">= Neto al cash flow</span><span className="tabular-nums text-emerald-300">${money(netOp)}</span></div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setModalOpen(false)} className="rounded px-3 py-1.5 text-xs text-white/60 hover:text-white">Cerrar</button>
              <button onClick={async () => { await save(); setModalOpen(false); }} disabled={saving}
                className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">
                {saving ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
