"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

export function useReportQuery<T = Record<string, any>>(
  dataset: string, columns: string[], dateFrom: string, dateTo: string, refreshToken: number,
) {
  const [rows, setRows] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    const params = new URLSearchParams({
      dataset, columns: columns.join(","), date_from: dateFrom, date_to: dateTo,
      // Cache-bust: a real force-refresh must change the request itself, not
      // just re-trust `cache: "no-store"` -- see lib/forceRefresh.tsx.
      _r: String(refreshToken),
    });
    fetch(`${API_URL}/reporting/query?${params.toString()}`, { cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); })
      .then((d) => { if (!cancelled) setRows(d); })
      .catch((e) => { if (!cancelled) { setRows([]); setError(e.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, columns.join(","), dateFrom, dateTo, refreshToken]);

  return { rows, loading, error };
}
