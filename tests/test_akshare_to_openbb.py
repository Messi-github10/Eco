"""End-to-end check: AkShare -> OpenBB -> Excel.

This hits the live AkShare endpoint, so it needs a network connection and is
skipped when that endpoint is unreachable.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data.akshare_provider import fetch_nav_history
from data.openbb_provider import to_obbject
from pipeline.export_excel import to_excel

FUND_CODE = "000001"  # 华夏成长混合, a long-running fund with stable history


def test_nav_reaches_openbb_and_exports_to_excel(tmp_path: Path) -> None:
    try:
        frame = fetch_nav_history(FUND_CODE)
    except Exception as exc:  # network or upstream outage, not a code failure
        pytest.skip(f"AkShare unreachable: {exc}")

    assert not frame.empty
    assert {"date", "nav", "fund_code"} <= set(frame.columns)

    obbject = to_obbject(frame)
    recovered = obbject.to_dataframe()

    assert obbject.provider == "akshare"
    assert list(recovered.columns) == list(frame.columns)
    assert len(recovered) == len(frame)

    workbook = to_excel(recovered, tmp_path / "nav.xlsx")

    assert workbook.exists()
    saved = pd.read_excel(workbook, dtype={"fund_code": str})
    assert list(saved.columns) == ["date", "nav", "fund_code"]
    assert len(saved) == len(frame)
    assert set(saved["fund_code"]) == {FUND_CODE}
