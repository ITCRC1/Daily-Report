// Shared number/currency formatting for Tab 7 (Reporting) period tables and
// Power Query -- "que todo tenga moneda": every currency column always shows
// with a $ sign and 2 decimals, never a bare number.
export const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const usd = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `$${money(v)}`;

export const intFmt = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 0 });

export const pctFmt = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`;

export const valueColor = (v: number | null | undefined) =>
  v !== null && v !== undefined && v < 0 ? "!text-rose-400" : "";
