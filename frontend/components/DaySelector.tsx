"use client";

import { useEffect, useState } from "react";
import { BUSINESS_DATE_DEFAULT, setBusinessDate } from "@/lib/useBusinessDate";

// Global day selector (§4 Tab 1 / dashboard). Persisted in localStorage;
// notifies subscribed views via useBusinessDate().
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
        className="rounded border border-white/10 bg-[#1E2130] px-2 py-1 text-white"
      />
    </label>
  );
}
