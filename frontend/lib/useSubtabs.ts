"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

/** Filtra los sub-tabs por la config de Admin (tabs deshabilitados) y mantiene
 * el tab activo válido. `all` = catálogo completo de sub-tabs de la página. */
export function useSubtabs<T extends { id: string }>(all: T[], initial?: string) {
  const [disabled, setDisabled] = useState<string[]>([]);
  const [tab, setTab] = useState(initial ?? all[0]?.id);

  useEffect(() => {
    let live = true;
    fetch(`${API_URL}/config/nav`, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => { if (live && Array.isArray(j.disabled)) setDisabled(j.disabled); })
      .catch(() => {});
    return () => { live = false; };
  }, []);

  const subtabs = all.filter((t) => !disabled.includes(t.id));
  // Si el tab activo quedó deshabilitado, caer al primero habilitado.
  const active = subtabs.some((t) => t.id === tab) ? tab : (subtabs[0]?.id ?? tab);
  return { subtabs, tab: active, setTab };
}
