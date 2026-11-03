"""The credit-range engine: verified purchases and a company's policy in, a range (or the reason
there is none) out.

Purpose: turn evidence into an indicative range with every step written down, so a person can
    check it and a stored assessment can be recomputed. A pure function: no database, no clock.
Owner role: C (assessment).
Implements: Phase 6 of the unified platform plan (section 15).

Inputs are the shop's verified wholesale purchases only (rows that reached the contract table
by a submitted sheet or an officer's entry; drafts never do). Sales are shown elsewhere and are
not used here. The score never becomes money: the band only picks the multiples.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

# What a policy must say. None of these has a shipped default value.
REQUIRED = (
    "window_days",
    "min_verified_months",
    "min_purchase_records",
    "multiples_by_band",
    "round_to_bdt",
    "cap_at_requested",
)

# Reasons there is no range (also the `range_reason` stored on an assessment).
NO_POLICY = "policy_not_configured"
NOT_ENOUGH = "not_enough_verified"
NEEDS_MORE_INFO = "needs_more_info"
NO_APPLICATION = "no_application"


class PolicyError(ValueError):
    """The policy parameters are incomplete or out of range."""


def check_parameters(params: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise policy parameters; raise PolicyError naming the problem."""
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        raise PolicyError("Missing: " + ", ".join(missing))
    out = {
        "window_days": int(params["window_days"]),
        "min_verified_months": int(params["min_verified_months"]),
        "min_purchase_records": int(params["min_purchase_records"]),
        "round_to_bdt": float(params["round_to_bdt"]),
        "cap_at_requested": bool(params["cap_at_requested"]),
        "multiples_by_band": {},
    }
    if not 30 <= out["window_days"] <= 730:
        raise PolicyError("window_days must be between 30 and 730.")
    if not 1 <= out["min_verified_months"] <= 24:
        raise PolicyError("min_verified_months must be between 1 and 24.")
    if out["min_purchase_records"] < 1:
        raise PolicyError("min_purchase_records must be at least 1.")
    if out["round_to_bdt"] < 1:
        raise PolicyError("round_to_bdt must be at least 1.")
    bands = params["multiples_by_band"]
    if not isinstance(bands, dict) or not bands:
        raise PolicyError("multiples_by_band needs at least one band.")
    for band, pair in bands.items():
        try:
            low, high = float(pair[0]), float(pair[1])
        except (TypeError, ValueError, IndexError):
            raise PolicyError(f"Multiples for {band} must be [low, high].") from None
        if not 0 <= low <= high <= 12:
            raise PolicyError(f"Multiples for {band} must satisfy 0 <= low <= high <= 12.")
        out["multiples_by_band"][str(band)] = [low, high]
    return out


@dataclass
class RangeResult:
    available: bool
    reason: str | None = None
    low_bdt: float | None = None
    high_bdt: float | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    steps: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def compute(
    params: dict[str, Any] | None,
    band: str | None,
    purchases: list[tuple[date, float]],
    requested_bdt: float | None,
    today: date,
) -> RangeResult:
    """The range for one assessment, with the steps behind it. `purchases` are verified only."""
    if params is None:
        return RangeResult(False, NO_POLICY, steps=["No range policy is approved."])
    p = check_parameters(params)
    if requested_bdt is None:
        return RangeResult(False, NO_APPLICATION, steps=["There is no open application."])
    start = today - timedelta(days=p["window_days"])
    rows = [(d, a) for d, a in purchases if start < d <= today and a > 0]
    months = len({(d.year, d.month) for d, _ in rows})
    inputs = {
        "window_days": p["window_days"],
        "records": len(rows),
        "months_with_purchases": months,
        "total_bdt": round(sum(a for _, a in rows), 2),
        "requested_bdt": requested_bdt,
        "band": band,
        "as_of": today.isoformat(),
    }
    steps = [
        f"Verified purchases in the last {p['window_days']} days: {len(rows)} in {months} month(s)."
    ]
    missing = []
    if months < p["min_verified_months"]:
        missing.append(
            f"verified purchases in {p['min_verified_months']} different months (have {months})"
        )
    if len(rows) < p["min_purchase_records"]:
        missing.append(f"{p['min_purchase_records']} verified purchase records (have {len(rows)})")
    if missing:
        steps.append("Not enough verified information: " + "; ".join(missing) + ".")
        return RangeResult(False, NOT_ENOUGH, inputs=inputs, steps=steps, missing=missing)
    multiples = p["multiples_by_band"].get(band or "")
    if not multiples:
        steps.append(f"The policy gives no range for the band {band or 'none'}.")
        return RangeResult(False, NEEDS_MORE_INFO, inputs=inputs, steps=steps)
    monthly = inputs["total_bdt"] / p["window_days"] * 30
    inputs["monthly_purchases_bdt"] = round(monthly, 2)
    steps.append(f"Average monthly purchases: {monthly:,.0f} BDT.")
    steps.append(f"Band {band}: multiples {multiples[0]} to {multiples[1]}.")

    def end(multiple: float) -> float:
        value = monthly * multiple
        if p["cap_at_requested"]:
            value = min(value, requested_bdt)
        return float(int(value // p["round_to_bdt"]) * p["round_to_bdt"])

    low, high = end(multiples[0]), end(multiples[1])
    if p["cap_at_requested"]:
        steps.append(f"Capped at the requested amount ({requested_bdt:,.0f} BDT).")
    steps.append(f"Rounded down to {p['round_to_bdt']:,.0f} BDT: {low:,.0f} to {high:,.0f} BDT.")
    return RangeResult(True, None, low, high, inputs, steps)
