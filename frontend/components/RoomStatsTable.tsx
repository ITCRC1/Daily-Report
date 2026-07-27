// Same column structure everywhere room-category stats are shown (Tab 3
// Today/MTD, Tab 4 Weekly/YTD) -- Category is the only thing that differs in
// meaning, not in shape -- Units | RN | Pax | Available | Revenue | Occ % | ADR | % of Total.
export type RoomCategory = {
  category: string; units: number; revenue: number; revenue_pct: number;
  stay_rooms: number; stay_persons: number; physical_rooms: number;
  occupancy_pct: number; adr: number;
};
export type RoomCategoryOverall = {
  units: number; revenue: number; stay_rooms: number; stay_persons: number;
  physical_rooms: number; occupancy_pct: number; adr: number;
};
// Línea de comps/in-house (RN/Pax/Revenue que se restaron del ADR/Occ).
export type RoomCategoryComps = { stay_rooms: number; stay_persons: number; revenue: number };

const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—"
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const valueColor = (v: number) => (v < 0 ? "!text-rose-400" : "");

const th = "px-3 py-2.5 text-left font-bold text-white/70";
const thN = "px-3 py-2.5 text-right font-bold text-white/70";
const td = "px-3 py-1.5 text-white/80";
const tdN = "px-3 py-1.5 text-right tabular-nums text-white/80";

export default function RoomStatsTable({ rows, overall, comps, reconciled, net }: {
  rows: RoomCategory[]; overall: RoomCategoryOverall;
  comps?: RoomCategoryComps; reconciled?: RoomCategoryOverall;
  // `net` = modo "bruto por categoría → menos comps → neto" (Tab 4 YTD, donde
  // el ancla no permite netear por categoría). `reconciled` = modo "neto por
  // categoría → más comps → bruto" (Tab 3 / Weekly). Excluyentes.
  net?: RoomCategoryOverall;
}) {
  const grossMode = !!net;
  return (
    <div className="overflow-hidden rounded-xl border border-white/10 shadow-lg">
      <table className="w-full text-xs">
        <thead className="bg-gradient-to-r from-[#1a2744] to-[#1E2130]"><tr>
          <th className={th}>Category</th><th className={thN}>Units</th>
          <th className={thN}>RN</th><th className={thN}>Pax</th><th className={thN}>Available</th>
          <th className={thN}>Revenue</th><th className={thN}>Occ %</th>
          <th className={thN}>ADR</th><th className={thN}>% of Total</th>
        </tr></thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.category} className="border-t border-white/5">
              <td className={td}>{c.category}</td>
              <td className={tdN}>{intFmt(c.units)}</td>
              <td className={tdN}>{intFmt(c.stay_rooms)}</td>
              <td className={tdN}>{intFmt(c.stay_persons)}</td>
              <td className={tdN}>{intFmt(c.physical_rooms)}</td>
              <td className={`${tdN} ${valueColor(c.revenue)}`}>${money(c.revenue)}</td>
              <td className={tdN}>{(c.occupancy_pct * 100).toFixed(1)}%</td>
              <td className={`${tdN} ${valueColor(c.adr)}`}>${money(c.adr)}</td>
              <td className={tdN}>{(c.revenue_pct * 100).toFixed(1)}%</td>
            </tr>
          ))}
          {/* Fila Comps/In-House (compartida por ambos modos) */}
          {(() => {
            const compsRow = comps ? (
              <tr className="border-t border-white/10 bg-[#231c17] italic text-amber-200/80">
                <td className={td}>{grossMode ? "+ " : ""}Comps &amp; In-House <span className="not-italic text-[10px] text-amber-200/50">(excl. from ADR/Occ)</span></td>
                <td className={tdN}>—</td>
                <td className={tdN}>{intFmt(comps.stay_rooms)}</td>
                <td className={tdN}>{intFmt(comps.stay_persons)}</td>
                <td className={tdN}>—</td>
                <td className={`${tdN} ${valueColor(comps.revenue)}`}>${money(comps.revenue)}</td>
                <td className={tdN}>—</td>
                <td className={tdN}>—</td>
                <td className={tdN}>—</td>
              </tr>
            ) : null;
            // Fila overall (= habitaciones ocupadas): en modo bruto es el TOTAL
            // (Net + Comps) y va al FINAL; en modo weekly es el TOTAL (revenue
            // rooms) y va primero.
            const overallRow = (
              <tr className={`border-t-2 ${grossMode ? "border-white/30" : "border-white/20"} bg-[#1E2130] font-bold`}>
                <td className={td}>{grossMode ? "TOTAL (occupied = Net + Comps)" : "TOTAL (revenue rooms)"}</td>
                <td className={tdN}>{intFmt(overall.units)}</td>
                <td className={tdN}>{intFmt(overall.stay_rooms)}</td>
                <td className={tdN}>{intFmt(overall.stay_persons)}</td>
                <td className={tdN}>{intFmt(overall.physical_rooms)}</td>
                <td className={`${tdN} ${valueColor(overall.revenue)}`}>${money(overall.revenue)}</td>
                <td className={tdN}>{(overall.occupancy_pct * 100).toFixed(1)}%</td>
                <td className={`${tdN} ${valueColor(overall.adr)}`}>${money(overall.adr)}</td>
                <td className={tdN}>{overall.revenue > 0 ? "100.0%" : "—"}</td>
              </tr>
            );
            if (grossMode && net) {
              // Modo bruto (Tab 4 YTD / 6.6): NET -> + Comps -> TOTAL (ocupadas).
              return (
                <>
                  <tr className="border-t-2 border-white/20 bg-[#16233a] font-bold text-emerald-300/90">
                    <td className={td}>NET (revenue rooms)</td>
                    <td className={tdN}>{intFmt(net.units)}</td>
                    <td className={tdN}>{intFmt(net.stay_rooms)}</td>
                    <td className={tdN}>{intFmt(net.stay_persons)}</td>
                    <td className={tdN}>{intFmt(net.physical_rooms)}</td>
                    <td className={`${tdN} ${valueColor(net.revenue)}`}>${money(net.revenue)}</td>
                    <td className={tdN}>{(net.occupancy_pct * 100).toFixed(1)}%</td>
                    <td className={`${tdN} ${valueColor(net.adr)}`}>${money(net.adr)}</td>
                    <td className={tdN}>—</td>
                  </tr>
                  {compsRow}
                  {overallRow}
                </>
              );
            }
            // Modo weekly (revenue rooms): TOTAL -> + Comps -> GRAND TOTAL.
            return (
              <>
                {overallRow}
                {compsRow}
                {reconciled && (
                  <tr className="border-t border-white/20 bg-[#16233a] font-bold text-white/90">
                    <td className={td}>GRAND TOTAL (incl. comps)</td>
                    <td className={tdN}>{intFmt(reconciled.units)}</td>
                    <td className={tdN}>{intFmt(reconciled.stay_rooms)}</td>
                    <td className={tdN}>{intFmt(reconciled.stay_persons)}</td>
                    <td className={tdN}>{intFmt(reconciled.physical_rooms)}</td>
                    <td className={`${tdN} ${valueColor(reconciled.revenue)}`}>${money(reconciled.revenue)}</td>
                    <td className={tdN}>{(reconciled.occupancy_pct * 100).toFixed(1)}%</td>
                    <td className={tdN}>—</td>
                    <td className={tdN}>—</td>
                  </tr>
                )}
              </>
            );
          })()}
        </tbody>
      </table>
    </div>
  );
}
