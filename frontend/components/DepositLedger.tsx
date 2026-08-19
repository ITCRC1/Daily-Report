"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { usd, valueColor } from "@/lib/fmt";

type Source = "audit" | "manual" | "none";
type Row = {
  date: string; deposited_usd: number; applied_usd: number; balance_usd: number;
  note: string | null; source: Source;
};
type Anchor = { anchor_date: string; balance_usd: number; note: string | null };
type LedgerRange = {
  start: string; end: string; opening_balance: number; closing_balance: number;
  rows: Row[]; anchor: Anchor | null;
};

function toISO(d: Date) { return d.toISOString().slice(0, 10); }
function firstOfMonth(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return toISO(new Date(d.getFullYear(), d.getMonth(), 1));
}

const th = "px-3 py-2 text-left font-medium text-ink/70 whitespace-nowrap";
const thN = "px-3 py-2 text-right font-medium text-ink/70 whitespace-nowrap";
const td = "px-3 py-1.5 text-ink/85 whitespace-nowrap";
const tdEmpty = "px-3 py-1.5";
const numInput = "w-28 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-right text-ink disabled:border-ink/8 disabled:bg-transparent disabled:text-ink/70";

const SOURCE_BADGE: Record<Source, string> = {
  audit: "🔒 from audit",
  manual: "✏️ manual",
  none: "",
};

export default function DepositLedger({ anchor: businessDate }: { anchor: string }) {
  const [from, setFrom] = useState(firstOfMonth(businessDate));
  const [to, setTo] = useState(businessDate);
  const [data, setData] = useState<LedgerRange | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [amountDrafts, setAmountDrafts] = useState<Record<string, { deposited: string; applied: string }>>({});
  const [savingDate, setSavingDate] = useState<string | null>(null);
  const [editingOpening, setEditingOpening] = useState(false);
  const [openingDraft, setOpeningDraft] = useState({ anchor_date: "", balance_usd: "", note: "" });

  const load = useCallback(async () => {
    setLoading(true); setMsg("");
    try {
      const res = await fetch(`${API_URL}/deposit-ledger?date_from=${from}&date_to=${to}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const json: LedgerRange = await res.json();
      setData(json);
      const notes: Record<string, string> = {};
      const amounts: Record<string, { deposited: string; applied: string }> = {};
      for (const r of json.rows) {
        notes[r.date] = r.note ?? "";
        amounts[r.date] = { deposited: String(r.deposited_usd), applied: String(r.applied_usd) };
      }
      setNoteDrafts(notes);
      setAmountDrafts(amounts);
      if (json.anchor) {
        setOpeningDraft({
          anchor_date: json.anchor.anchor_date,
          balance_usd: String(json.anchor.balance_usd),
          note: json.anchor.note ?? "",
        });
      }
    } catch (e: any) {
      setData(null); setMsg(`Error: ${e.message}`);
    } finally { setLoading(false); }
  }, [from, to]);

  useEffect(() => { load(); }, [load]);

  async function saveRow(r: Row, deposited: number, applied: number) {
    setSavingDate(r.date); setMsg("");
    try {
      const res = await fetch(`${API_URL}/deposit-ledger/entries/${r.date}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          deposited_usd: deposited, applied_usd: applied,
          note: (noteDrafts[r.date] ?? "").trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      await load();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
    finally { setSavingDate(null); }
  }

  async function saveOpening() {
    if (!openingDraft.anchor_date) { setMsg("Pick an anchor date first."); return; }
    setMsg("");
    try {
      const res = await fetch(`${API_URL}/deposit-ledger/opening`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anchor_date: openingDraft.anchor_date,
          balance_usd: parseFloat(openingDraft.balance_usd) || 0,
          note: openingDraft.note.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setEditingOpening(false);
      await load();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-ink/75">
          From
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink/75">
          To
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
        </label>
      </div>

      <p className="text-[11px] text-ink/60">
        Deposited/Applied come automatically from Integrity for any day already audited (credits/debits to
        the "ADELANTO HPDS LODGING" suspense account — 🔒 read-only, matches Tab 2 exactly). Days with no
        audit yet (e.g. before Daily-Ops went live) are ✏️ manual entry as a fallback. Balance = running
        (Opening + Deposited − Applied), for your own cash flow. Not related to the "Deposit Ledger" in
        Tab 2.3 (that one is Opera&apos;s guest-advance PMS ledger — a different concept entirely).
      </p>

      {loading && <div className="text-xs text-ink/60">Loading…</div>}
      {msg && <div className="rounded border border-ink/10 bg-[#fcfcfb] p-2 text-xs text-ink/75">{msg}</div>}

      <div className="rounded-lg border border-ink/10 bg-[#fcfcfb]/60 p-3">
        {data?.anchor && !editingOpening ? (
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink/75">
            <span>
              Opening balance anchor: <strong>{usd(data.anchor.balance_usd)}</strong> as of{" "}
              <strong>{data.anchor.anchor_date}</strong>
              {data.anchor.note ? ` — ${data.anchor.note}` : ""}
            </span>
            <button onClick={() => setEditingOpening(true)}
              className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:bg-ink/8">
              Edit
            </button>
          </div>
        ) : !editingOpening ? (
          <div className="flex items-center justify-between gap-2 text-xs text-ink/60">
            <span>No opening balance anchor yet — YTD-June starting balance can be loaded whenever it&apos;s ready.</span>
            <button onClick={() => setEditingOpening(true)}
              className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:bg-ink/8">
              Load opening balance
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-[11px] text-ink/70">
              Anchor date
              <input type="date" value={openingDraft.anchor_date}
                onChange={(e) => setOpeningDraft((p) => ({ ...p, anchor_date: e.target.value }))}
                className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-ink/70">
              Balance ($)
              <div className="flex items-center gap-1">
                <span className="text-ink/60">$</span>
                <input type="number" step="0.01" autoFocus value={openingDraft.balance_usd}
                  onChange={(e) => setOpeningDraft((p) => ({ ...p, balance_usd: e.target.value }))}
                  className={numInput} />
              </div>
            </label>
            <label className="flex flex-1 flex-col gap-1 text-[11px] text-ink/70">
              Note — optional, NOT the balance
              <input type="text" value={openingDraft.note} title="Optional note — the balance goes in the field above"
                onChange={(e) => setOpeningDraft((p) => ({ ...p, note: e.target.value }))}
                placeholder="e.g. YTD close as of Jun 30, 2026"
                className="rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
            </label>
            <button onClick={saveOpening}
              className="rounded bg-accent px-3 py-1.5 text-[11px] font-medium text-white hover:opacity-90">
              Save
            </button>
            <button onClick={() => setEditingOpening(false)}
              className="rounded bg-ink/5 px-3 py-1.5 text-[11px] text-ink/75 hover:bg-ink/8">
              Cancel
            </button>
          </div>
        )}
      </div>

      {data && (
        <div className="overflow-x-auto rounded-lg border border-ink/10">
          <table className="w-full text-sm">
            <thead className="bg-[#fcfcfb]">
              <tr>
                <th className={th}>Date</th>
                <th className={thN}>Deposited</th>
                <th className={thN}>Applied</th>
                <th className={thN}>Balance</th>
                <th className={th}>Source</th>
                <th className={th}>Note</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-ink/8 bg-[#fcfcfb]/40 text-ink/60">
                <td className={td}>Opening ({from})</td>
                <td className={tdEmpty}></td>
                <td className={tdEmpty}></td>
                <td className={`${thN} ${valueColor(data.opening_balance)}`}>{usd(data.opening_balance)}</td>
                <td className={td} colSpan={3}></td>
              </tr>
              {data.rows.map((r) => {
                const readOnly = r.source === "audit";
                const draft = amountDrafts[r.date] ?? { deposited: String(r.deposited_usd), applied: String(r.applied_usd) };
                return (
                  <tr key={r.date} className="border-t border-ink/8">
                    <td className={td}>{r.date}</td>
                    <td className={thN}>
                      <input type="number" step="0.01" value={draft.deposited} disabled={readOnly}
                        placeholder="0.00"
                        onChange={(e) => setAmountDrafts((p) => ({ ...p, [r.date]: { ...draft, deposited: e.target.value } }))}
                        className={numInput} />
                    </td>
                    <td className={thN}>
                      <input type="number" step="0.01" value={draft.applied} disabled={readOnly}
                        placeholder="0.00"
                        onChange={(e) => setAmountDrafts((p) => ({ ...p, [r.date]: { ...draft, applied: e.target.value } }))}
                        className={numInput} />
                    </td>
                    <td className={`${thN} font-medium ${valueColor(r.balance_usd)}`}>{usd(r.balance_usd)}</td>
                    <td className={`${td} text-ink/60`}>{SOURCE_BADGE[r.source]}</td>
                    <td className={td}>
                      <input type="text" value={noteDrafts[r.date] ?? ""}
                        onChange={(e) => setNoteDrafts((p) => ({ ...p, [r.date]: e.target.value }))}
                        placeholder="optional note"
                        className="w-48 rounded border border-ink/12 bg-[#f9f9f7] px-2 py-1 text-ink" />
                    </td>
                    <td className={td}>
                      <button
                        onClick={() => {
                          const deposited = readOnly ? r.deposited_usd : (parseFloat(draft.deposited) || 0);
                          const applied = readOnly ? r.applied_usd : (parseFloat(draft.applied) || 0);
                          saveRow(r, deposited, applied);
                        }}
                        disabled={savingDate === r.date}
                        title={readOnly ? "Saves the note only — amounts come from the audit" : "Save"}
                        className="rounded bg-ink/5 px-2 py-1 text-[11px] text-ink/75 hover:bg-ink/8 disabled:opacity-40">
                        {savingDate === r.date ? "…" : "💾 Save"}
                      </button>
                    </td>
                  </tr>
                );
              })}
              <tr className="border-t-2 border-ink/15 bg-[#fcfcfb] font-bold">
                <td className={td}>Closing ({to})</td>
                <td className={tdEmpty}></td>
                <td className={tdEmpty}></td>
                <td className={`${thN} ${valueColor(data.closing_balance)}`}>{usd(data.closing_balance)}</td>
                <td className={td} colSpan={3}></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
