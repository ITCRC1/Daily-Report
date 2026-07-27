"use client";

import { PERIOD_TABS, PeriodKey } from "@/lib/periods";

export default function PeriodTabs({ value, onChange }: { value: PeriodKey; onChange: (p: PeriodKey) => void }) {
  return (
    <nav className="flex gap-1">
      {PERIOD_TABS.map((p) => (
        <button key={p.key} onClick={() => onChange(p.key)}
          className={`rounded px-2.5 py-1 text-[11px] ${value === p.key ? "bg-accent text-white" : "bg-[#1E2130] text-white/60 hover:text-white"}`}>
          {p.label}
        </button>
      ))}
    </nav>
  );
}
