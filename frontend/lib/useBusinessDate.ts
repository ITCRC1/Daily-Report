"use client";

import { useEffect, useState } from "react";

const KEY = "dailyops.business_date";
const EVENT = "dailyops:daychange";
const DEFAULT = "2026-07-01";

/** Reads the global day (localStorage) and re-renders when the selector changes it. */
export function useBusinessDate(): string {
  const [day, setDay] = useState<string>(DEFAULT);

  useEffect(() => {
    setDay(localStorage.getItem(KEY) || DEFAULT);
    const onChange = (e: Event) => {
      const d = (e as CustomEvent<string>).detail;
      if (d) setDay(d);
    };
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);

  return day;
}

/** Persists the day and notifies subscribed views. */
export function setBusinessDate(day: string) {
  localStorage.setItem(KEY, day);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: day }));
}

export const BUSINESS_DATE_DEFAULT = DEFAULT;
