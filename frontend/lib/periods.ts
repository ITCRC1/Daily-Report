// Shared Today/Weekly/MTD/Full Year quick-period logic for Tab 7 (Reporting).
// Every period is computed off the global business date (the day selector at
// the top of the app) -- never off the real browser clock, so it stays
// consistent with the rest of the app when validating a past day.

export type PeriodKey = "today" | "weekly" | "mtd" | "year";

export const PERIOD_TABS: { key: PeriodKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "weekly", label: "Weekly" },
  { key: "mtd", label: "MTD" },
  { key: "year", label: "Full Year" },
];

const pad2 = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;

export function periodRange(period: PeriodKey, anchorIso: string): { from: string; to: string } {
  const d = new Date(anchorIso + "T00:00:00");

  if (period === "today") return { from: anchorIso, to: anchorIso };

  if (period === "weekly") {
    const dow = (d.getDay() + 6) % 7; // Monday = 0
    const monday = new Date(d); monday.setDate(d.getDate() - dow);
    const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6);
    return { from: iso(monday), to: iso(sunday) };
  }

  if (period === "mtd") {
    const first = new Date(d.getFullYear(), d.getMonth(), 1);
    return { from: iso(first), to: anchorIso };
  }

  // "year" -- Full Year (Jan 1 -> Dec 31 of the anchor's year). Future days
  // simply have no data yet -- never fabricated, same rule as everywhere else.
  const jan1 = new Date(d.getFullYear(), 0, 1);
  const dec31 = new Date(d.getFullYear(), 11, 31);
  return { from: iso(jan1), to: iso(dec31) };
}
