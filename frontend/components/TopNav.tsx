"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import DaySelector from "./DaySelector";
import { API_URL } from "@/lib/api";
import { NAV_TABS } from "@/lib/navTabs";

export default function TopNav() {
  const pathname = usePathname();
  const [disabled, setDisabled] = useState<string[]>([]);

  useEffect(() => {
    let live = true;
    fetch(`${API_URL}/config/nav`, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => { if (live && Array.isArray(j.disabled)) setDisabled(j.disabled); })
      .catch(() => {});
    return () => { live = false; };
  }, []);

  const tabs = NAV_TABS.filter((t) => !disabled.includes(t.id));

  return (
    <header className="sticky top-0 z-10 bg-[#1a1a19] print:hidden">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold tracking-wide text-white">DAILY-OPS</span>
          <span className="rounded bg-white/10 px-2 py-0.5 text-[11px] font-medium text-white/70">COWLCR</span>
        </div>
        <div className="flex items-center gap-3">
          <DaySelector />
          <Link href="/admin" title="Admin — prender/apagar tabs"
            className={`rounded px-2 py-1 text-xs transition ${pathname === "/admin"
              ? "bg-accent text-white"
              : "text-white/60 hover:bg-white/10 hover:text-white"}`}>
            ⚙
          </Link>
        </div>
      </div>
      {/* Los tabs inactivos van SIN fondo. Antes tenían una caja casi del mismo
          color que la barra: se veían borrosos, sin forma. Ahora la caja
          aparece solo en el activo y en hover, y el estado se lee de una. */}
      <nav className="flex flex-wrap gap-1 px-3 pb-2">
        {tabs.map((t) => {
          const active = pathname === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`rounded px-3 py-1.5 text-xs transition ${
                active
                  ? "bg-accent font-medium text-white"
                  : "text-white/65 hover:bg-white/10 hover:text-white"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
