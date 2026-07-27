"""Gate engine (stage 8, §2.7) — controls whether a daily can be released to owners.

Pure Python. `gate_hard` (app_config, default 'false' -- TODO(bismark): confirm
the final default) decides the policy:
  - Soft (gate_hard=False): release is always allowed. Open exceptions stay
    visible in the report, but don't block the release.
  - Hard (gate_hard=True): blocks the release if there are open discrepancies
    or missing items, unless override_flag=True is passed (with override_note
    -- validating that the note isn't empty is the caller's/API's responsibility).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    allowed: bool
    reason: str
    open_issues: int


def evaluate_gate(kpi_discrepancia: int, kpi_faltante: int,
                  gate_hard: bool, override_flag: bool = False) -> GateResult:
    open_issues = (kpi_discrepancia or 0) + (kpi_faltante or 0)

    if not gate_hard:
        reason = ("No open exceptions." if open_issues == 0
                  else f"Soft gate: releasing with {open_issues} open exception(s) "
                       f"(discrepancy={kpi_discrepancia}, missing={kpi_faltante}), visible in the report.")
        return GateResult(allowed=True, reason=reason, open_issues=open_issues)

    if open_issues == 0:
        return GateResult(allowed=True, reason="No open exceptions.", open_issues=0)

    if override_flag:
        return GateResult(
            allowed=True,
            reason=f"Hard gate with override: {open_issues} open exception(s) "
                   f"(discrepancy={kpi_discrepancia}, missing={kpi_faltante}).",
            open_issues=open_issues,
        )

    return GateResult(
        allowed=False,
        reason=f"Blocked (hard gate): {open_issues} open exception(s) "
               f"(discrepancy={kpi_discrepancia}, missing={kpi_faltante}). "
               "Requires override_flag + override_note to release anyway.",
        open_issues=open_issues,
    )
