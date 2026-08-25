// Lista canónica de tabs de la nav principal (compartida por TopNav y el Admin).
// El `id` es la clave que guarda el Admin en la config de "tabs deshabilitados".
export const NAV_TABS = [
  { id: "data-input", href: "/data-input", label: "1 · Data Input" },
  { id: "audit", href: "/audit", label: "2 · Daily Audit" },
  { id: "revenue-daily", href: "/revenue-daily", label: "3 · Daily Revenue" },
  { id: "revenue-weekly", href: "/revenue-weekly", label: "4 · Weekly Revenue" },
  { id: "cash", href: "/cash", label: "5 · Daily Cash" },
  { id: "master-data", href: "/master-data", label: "6 · Master Data" },
  { id: "reporting", href: "/reporting", label: "7 · Reporting" },
  { id: "on-the-books", href: "/on-the-books", label: "8 · On the Books" },
  { id: "daily-extended", href: "/daily-extended", label: "9 · Daily Extendido" },
];

// Sub-tabs por página (id = mismo que la SUBTABS de cada page). El Admin los
// puede prender/apagar; se guardan en la misma lista `disabled` que los tabs.
export const SUB_TABS: Record<string, { id: string; label: string }[]> = {
  cash: [
    { id: "5", label: "5 · Daily Cash from Operation" },
    { id: "5.1", label: "5.1 · Monthly Summary (Currency Basis)" },
    { id: "5.2", label: "5.2 · Monthly Cash Position" },
  ],
  "master-data": [
    { id: "6.1", label: "6.1 Monthly Budget" },
    { id: "6.1.1", label: "6.1.1 Forecast" },
    { id: "6.2", label: "6.2 Cash Mapping" },
    { id: "6.3", label: "6.3 Integrity Mapping" },
    { id: "6.4", label: "6.4 Daily Revenue by Day/Dept" },
    { id: "6.5", label: "6.5 Daily Budget by Day/Dept" },
    { id: "6.6", label: "6.6 Rooms Statistics YTD" },
    { id: "6.7", label: "6.7 Rooms Mapping" },
    { id: "6.8", label: "6.8 Market Codes Mapping" },
    { id: "6.9", label: "6.9 Parámetros / Cuentas" },
    { id: "6.10", label: "6.10 Weekly Calendar" },
  ],
  reporting: [
    { id: "7.1", label: "7.1 Daily Revenue Actual" },
    { id: "7.2", label: "7.2 Daily Budget" },
    { id: "7.3", label: "7.3 Daily Revenue by Room Type" },
    { id: "7.4", label: "7.4 Power Query" },
    { id: "7.5", label: "7.5 Deposit Ledger (Bank)" },
    { id: "7.6", label: "7.6 Tips & Extra Tips" },
    { id: "7.6.1", label: "7.6.1 Tip 10%" },
    { id: "7.6.2", label: "7.6.2 Extra Tips" },
    { id: "7.7", label: "7.7 IVA 13%" },
    { id: "7.8", label: "7.8 YTD June 30 Comps" },
    { id: "7.9", label: "7.9 Daily Comps by Room Type" },
    { id: "7.10", label: "7.10 Market Codes" },
  ],
  "daily-extended": [
    { id: "9.1", label: "9.1 Summary" },
    { id: "9.2", label: "9.2 Revenue Detail" },
    { id: "9.3", label: "9.3 Rooms by Segment" },
    { id: "9.4", label: "9.4 Residential Rental" },
    { id: "9.5", label: "9.5 F&B by Meal Period" },
  ],
  "on-the-books": [
    { id: "8.1", label: "8.1 ONTB Report" },
    { id: "8.2", label: "8.2 Dashboard" },
    { id: "8.3", label: "8.3 Daily Heatmap" },
    { id: "8.4", label: "8.4 Pacing" },
    { id: "8.5", label: "8.5 Revenue Trend" },
    { id: "8.5.1", label: "8.5.1 Análisis 2027" },
    { id: "8.6", label: "8.6 Occupancy Trend" },
    { id: "8.7", label: "8.7 Variance Breakdown" },
  ],
};
