"""Data adapters: every data source sits behind one of these.

Purpose: map a source (synthetic, Kiva, Taiwan, Home Credit, a future ShopUp extract) into
    the same seven tables, so the pipeline never depends on one source.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 5 (data contract), 15 and 18; docs/DATASET_PLAN.md section 3.
"""

from src.adapters.base import CONTRACT, DataAdapter, check_frame, empty_frame
from src.adapters.factory import get_adapter

__all__ = ["CONTRACT", "DataAdapter", "check_frame", "empty_frame", "get_adapter"]
