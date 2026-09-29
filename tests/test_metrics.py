"""Metric calculations against a hand-built NAV series, no network."""

from __future__ import annotations

import math

import pandas as pd

from compute.metrics import (
    compute_metrics,
    max_drawdown,
    period_return,
    sharpe,
    to_nav_series,
    total_return,
    volatility,
    win_rate,
)

DATES = pd.bdate_range("2024-01-02", periods=300)


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, index=DATES[: len(values)], dtype=float)


def test_period_return_uses_trading_days() -> None:
    nav = _series([1.0, 1.1, 1.2, 1.3, 1.5])
    # 2 trading days back: 1.5 against 1.2
    assert period_return(nav, 2) == (1.5 - 1.2) / 1.2


def test_total_return_and_drawdown() -> None:
    nav = _series([1.0, 1.2, 0.9, 1.1, 1.05])
    assert total_return(nav) == (1.05 - 1.0) / 1.0
    # Peak 1.2 falls to 0.9; needs at least 5 points, matching ZFundPilot.
    assert max_drawdown(nav) == (0.9 - 1.2) / 1.2


def test_volatility_and_sharpe_are_finite() -> None:
    nav = _series([1 + i * 0.001 for i in range(40)])
    assert volatility(nav) > 0
    assert sharpe(nav) > 0


def test_win_rate_counts_up_months() -> None:
    # One point per business day across several months, rising every day.
    nav = pd.Series(
        [1 + i * 0.001 for i in range(90)],
        index=pd.bdate_range("2024-01-02", periods=90),
        dtype=float,
    )
    rate = win_rate(nav)
    assert rate == 1.0


def test_compute_metrics_matches_the_pieces() -> None:
    nav = pd.Series(
        [1 + math.sin(i / 5) * 0.02 + i * 0.0005 for i in range(120)],
        index=pd.bdate_range("2024-01-02", periods=120),
        dtype=float,
    )
    row = compute_metrics(nav, fund_code="000001")
    assert row["fund_code"] == "000001"
    assert row["latest_nav"] == float(nav.iloc[-1])
    assert row["max_drawdown"] == max_drawdown(nav)
    assert row["volatility"] == volatility(nav)
    assert set(row) >= {
        "1w", "1m", "3m", "6m", "1y", "3y", "ytd", "since",
        "sharpe", "calmar", "win_rate",
    }


def test_to_nav_series_sorts_and_drops_duplicate_dates() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2024-01-03", "2024-01-02", "2024-01-03"],
            "nav": [1.2, 1.0, 1.3],
        }
    )
    series = to_nav_series(frame)
    assert list(series.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert float(series.iloc[-1]) == 1.3
