"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { NAV_TABS, SUB_TABS } from "@/lib/navTabs";

// El app no tiene login, así que esta página entra directa (antes pedía el
// admin password) y ya no administra usuarios/roles: solo qué tabs se ven.
export default function AdminPage() {
  const [disabled, setDisabled] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/config/nav`, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => Array.isArray(j.disabled) && setDisabled(j.disabled))
      .catch(() => {});
  }, []);

  const toggle = (id: string) => {
    setDisabled((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
    setMsg("");
  };

  const save = async () => {
    setSaving(true); setErr(""); setMsg("");
    try {
      const r = await fetch(`${API_URL}/config/nav`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disabled }),
      });
      if (!r.ok) { setErr(`Error ${r.status}`); return; }
      setMsg("✓ Guardado — recargá para ver la nav.");
    } finally { setSaving(false); }
  };

  return (
    <section className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Admin</h1>
        <p className="text-xs text-ink/60">Tabs elegibles.</p>
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-ink/90">Tabs elegibles</h2>
        <p className="text-[11px] text-ink/55">Prendé/apagá tabs principales y sus sub-tabs. Apagar un tab principal lo saca de la barra; apagar un sub-tab lo saca dentro de esa página.</p>
        <div className="divide-y divide-ink/8 rounded-lg border border-ink/10 bg-[#fcfcfb]">
          {NAV_TABS.map((t) => {
            const on = !disabled.includes(t.id);
            const subs = SUB_TABS[t.id] ?? [];
            const pill = (id: string, isOn: boolean) => (
              <button onClick={() => toggle(id)} className={`w-14 rounded-full px-2 py-1 text-[11px] font-medium ${isOn ? "bg-emerald-500/25 text-emerald-700" : "bg-ink/5 text-ink/60"}`}>{isOn ? "ON" : "OFF"}</button>
            );
            return (
              <div key={t.id}>
                <div className="flex items-center justify-between px-4 py-2.5">
                  <span className={`text-sm font-medium ${on ? "text-ink/90" : "text-ink/55 line-through"}`}>{t.label}</span>
                  {pill(t.id, on)}
                </div>
                {on && subs.map((s) => {
                  const son = !disabled.includes(s.id);
                  return (
                    <div key={s.id} className="flex items-center justify-between bg-[#181b26] px-4 py-1.5 pl-9">
                      <span className={`text-[12px] ${son ? "text-ink/75" : "text-ink/50 line-through"}`}>{s.label}</span>
                      {pill(s.id, son)}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3">
          <button onClick={save} disabled={saving} className="rounded bg-accent px-4 py-2 text-sm text-ink hover:brightness-110 disabled:opacity-50">{saving ? "Guardando…" : "Guardar tabs"}</button>
          {msg && <span className="text-xs text-emerald-600">{msg}</span>}
          {err && <span className="text-xs text-red-600">{err}</span>}
        </div>
      </div>
    </section>
  );
}
