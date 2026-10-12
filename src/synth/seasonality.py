"""Monthly seasonality for the synthetic purchases, taken from real Bangladesh figures.

Purpose: turn the Bangladesh Bank monthly merchant-payment series into twelve
    multipliers (one per calendar month) that shape when synthetic merchants buy more
    or less.
Owner role: B (data engineer).
Implements: docs/GENERATOR_SPEC.md ("Calibration to Bangladesh"); the source file and how
    it was read are described in config/calibration/README.md.

Method, in plain words:
1. The series grows strongly over time, so first remove the growth trend (a straight
   line through the logarithm of the values).
2. What is left is how far each month sits above or below the trend.
3. Average that for each calendar month across the years available.
4. Scale the twelve numbers so their average is 1.0.

Limit to state honestly: Eid moves about 11 days earlier each year, and this index
follows the calendar months of the source years (2023 to early 2025). It gives a
realistic seasonal shape, not exact Eid timing for the synthetic window.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT


def monthly_index(path: Path | str, strength: float = 1.0) -> dict[int, float]:
    """Return {calendar month 1-12: multiplier}, averaging 1.0.

    Args:
        path: CSV with columns `month` (YYYY-MM) and `merchant_payment_crore_bdt`.
        strength: 0 gives no seasonality (all 1.0); 1 gives the shape in the data.
    """
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = PROJECT_ROOT / file_path
    series = pd.read_csv(file_path)

    log_value = np.log(series["merchant_payment_crore_bdt"].to_numpy(dtype=float))
    position = np.arange(len(series), dtype=float)
    slope, intercept = np.polyfit(position, log_value, deg=1)
    away_from_trend = log_value - (intercept + slope * position)

    calendar_month = pd.to_datetime(series["month"], format="%Y-%m").dt.month
    by_month = pd.Series(away_from_trend).groupby(calendar_month.to_numpy()).mean()
    if len(by_month) != 12:
        missing = sorted(set(range(1, 13)) - set(by_month.index))
        raise ValueError(f"Seasonality file has no data for calendar months {missing}.")

    multipliers = np.exp(strength * by_month.to_numpy())
    multipliers = multipliers / multipliers.mean()
    return {int(month): float(value) for month, value in zip(by_month.index, multipliers)}
