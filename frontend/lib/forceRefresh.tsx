"use client";

import { createContext, useCallback, useContext, useState } from "react";

// Real force-refresh, not decorative: every Tab 7 data hook (a) includes
// `token` in its fetch dependency array so it genuinely re-runs the request,
// and (b) appends `_r=${token}` to the URL so the request itself changes --
// even if some caching layer got added later (browser, proxy, CDN), a
// different URL can never be served from that cache. `lastRefreshedAt` is
// shown in the UI so the user can SEE it actually happened, not just trust it.
type RefreshCtx = { token: number; lastRefreshedAt: string | null; forceRefresh: () => void };
const Ctx = createContext<RefreshCtx | null>(null);

export function ForceRefreshProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState(0);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);

  const forceRefresh = useCallback(() => {
    setToken((t) => t + 1);
    setLastRefreshedAt(new Date().toLocaleTimeString("en-US"));
  }, []);

  return <Ctx.Provider value={{ token, lastRefreshedAt, forceRefresh }}>{children}</Ctx.Provider>;
}

export function useForceRefresh(): RefreshCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useForceRefresh must be used within a ForceRefreshProvider");
  return ctx;
}
