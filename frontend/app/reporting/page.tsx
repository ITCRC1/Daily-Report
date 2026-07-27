"use client";

import { useState } from "react";
import { useBusinessDate } from "@/lib/useBusinessDate";
import { useSubtabs } from "@/lib/useSubtabs";
import { ForceRefreshProvider } from "@/lib/forceRefresh";
import RevenueActualPeriodTable from "@/components/reporting/RevenueActualPeriodTable";
import BudgetDailyPeriodTable from "@/components/reporting/BudgetDailyPeriodTable";
import RoomStatsPeriodTable from "@/components/reporting/RoomStatsPeriodTable";
import CompsYtdTable from "@/components/reporting/CompsYtdTable";
import CompsDailyTable from "@/components/reporting/CompsDailyTable";
import MarketCodesPeriodTable from "@/components/reporting/MarketCodesPeriodTable";
import PowerQuery from "@/components/PowerQuery";
import DepositLedger from "@/components/DepositLedger";
import TipsLedger from "@/components/TipsLedger";
import IvaLedger from "@/components/IvaLedger";

const ALL_SUBTABS = [
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
];

export default function ReportingPage() {
  const { subtabs: SUBTABS, tab, setTab } = useSubtabs(ALL_SUBTABS, "7.1");
  const anchor = useBusinessDate();

  return (
    <ForceRefreshProvider>
      <section className="w-[calc(100vw-1.5rem)] -translate-x-1/2 relative left-1/2 space-y-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Tab 7 · Reporting</h1>
          <p className="text-xs text-white/50">
            Quick Today/Weekly/MTD/Full Year views for validation and ad hoc reporting (COWLCR). Every
            table always shows a TOTAL row and every dollar amount is formatted as currency.
          </p>
        </div>

        <nav className="flex flex-wrap gap-1 border-b border-white/10 pb-2">
          {SUBTABS.map((s) => (
            <button key={s.id} onClick={() => setTab(s.id)}
              className={`rounded px-2.5 py-1 text-[11px] ${tab === s.id ? "bg-accent text-white" : "bg-[#1E2130] text-white/60 hover:text-white"}`}>
              {s.label}
            </button>
          ))}
        </nav>

        {tab === "7.1" && <RevenueActualPeriodTable anchor={anchor} />}
        {tab === "7.2" && <BudgetDailyPeriodTable anchor={anchor} />}
        {tab === "7.3" && <RoomStatsPeriodTable anchor={anchor} />}
        {tab === "7.4" && <PowerQuery anchor={anchor} />}
        {tab === "7.5" && <DepositLedger anchor={anchor} />}
        {tab === "7.6" && (
          <TipsLedger anchor={anchor} kind="all" description={
            "Combined total of Tip 10% (Tab 7.6.1) + Extra Tips (Tab 7.6.2) — Collected comes automatically " +
            "from Integrity for any day already audited, since 2026-07-01. Read-only: to record a payout to " +
            "employees, use Tab 7.6.1 or 7.6.2 individually (this view is the sum of both, not its own ledger)."
          } />
        )}
        {tab === "7.6.1" && (
          <TipsLedger anchor={anchor} kind="service_charge_10" description={
            'Collected comes automatically from Integrity (credits to the "10% SERVICE CHARGE" account) for ' +
            "any day already audited, since 2026-07-01. Paid to employees is always manual — the service " +
            "charge is distributed in cash, outside any system, so there's no automatic source for it. " +
            "Balance = running (Collected − Paid)."
          } />
        )}
        {tab === "7.6.2" && (
          <TipsLedger anchor={anchor} kind="extra_tips" description={
            'Collected comes automatically from Integrity (credits to the "TIPS - PAYABLE" account — F&B Extra ' +
            "Tips + Extra Tips-Operation) for any day already audited, since 2026-07-01. Paid to employees is " +
            "always manual — tips are handed out in cash, outside any system, so there's no automatic source " +
            "for it. Balance = running (Collected − Paid)."
          } />
        )}
        {tab === "7.7" && <IvaLedger anchor={anchor} />}
        {tab === "7.8" && <CompsYtdTable />}
        {tab === "7.9" && <CompsDailyTable />}
        {tab === "7.10" && <MarketCodesPeriodTable anchor={anchor} />}
      </section>
    </ForceRefreshProvider>
  );
}
