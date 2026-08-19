"use client";

import { useEffect, useState } from "react";
import { BUSINESS_DATE_DEFAULT, setBusinessDate } from "@/lib/useBusinessDate";

// Global day selector (§4 Tab 1 / dashboard). Persisted in localStorage;
// notifies subscribed views via useBusinessDate().
// Vive dentro de la barra OSCURA: la etiqueta va en blanco, pero el campo se
// deja claro a propósito para que se lea como un control y no como texto.
export default function DaySelector() {
  const [day, setDay] = useState<string>("");

  useEffect(() => {
    setDay(localStorage.getItem("dailyops.business_date") || BUSINESS_DATE_DEFAULT);
  }, []);

  function onChange(v: string) {
    setDay(v);
    setBusinessDate(v);
  }

  return (
    <label className="flex items-center gap-2 text-xs text-white/70">
      Day:
      <input
        type="date"
        value={day}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-white/20 bg-[#fcfcfb] px-2 py-1 text-ink"
      />
    </label>
  );
}
