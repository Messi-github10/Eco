"""AkShare data source.

Fetches fund net-asset-value history and returns a plain DataFrame. This layer
only retrieves data; it does not compute indicators or talk to OpenBB.
"""

from __future__ import annotations

import pandas as pd


def fetch_nav_history(fund_code: str) -> pd.DataFrame:
    """Fetch a fund's unit NAV history from AkShare.

    Returns a DataFrame with columns ``date`` (YYYY-MM-DD), ``nav`` (float),
    and ``fund_code``. Raises ``RuntimeError`` when the source returns nothing
    or its columns cannot be recognized.
    """
    import akshare as ak  # deferred so the package imports without AkShare

    df = ak.fund_open_fund_info_em(symbol=fund_code.strip(), indicator="单位净值走势")
    if df is None or df.empty:
        raise RuntimeError(f"AkShare returned no data for {fund_code}")

    date_col = _match_col(df.columns, ["净值日期", "日期", "date"])
    nav_col = _match_col(df.columns, ["单位净值", "nav"])
    if not date_col or not nav_col:
        raise RuntimeError(f"unrecognized columns from AkShare: {list(df.columns)}")

    out = pd.DataFrame(
        {
            "date": df[date_col].astype(str).str.slice(0, 10),
            "nav": pd.to_numeric(df[nav_col], errors="coerce"),
            "fund_code": fund_code.strip(),
        }
    )
    out = out.dropna(subset=["nav"]).reset_index(drop=True)
    if out.empty:
        raise RuntimeError(f"no usable NAV rows for {fund_code}")
    return out


def _match_col(columns, candidates) -> str | None:
    """Return the first column whose name contains one of the candidates."""
    for column in columns:
        for candidate in candidates:
            if candidate in str(column):
                return column
    return None
