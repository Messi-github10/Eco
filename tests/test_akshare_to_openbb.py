"""贯通测试：AkShare 拉净值 -> 装进 OpenBB -> 计算指标 -> 写到 Excel。

会访问真实的 AkShare 接口，需要网络；接口不可达时跳过而不是判失败。
生成的 Excel 留在 data/ 下，方便直接打开查看。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from compute.metrics import METRIC_LABELS, compute_metrics, to_nav_series
from data.akshare_provider import NAV_LABELS, fetch_nav_history
from data.openbb_provider import to_obbject
from pipeline.export_excel import to_excel

FUND_CODE = "000001"  # 华夏成长混合，历史长、数据稳定

# 指标表必须包含的列。
METRIC_COLUMNS = {
    "fund_code", "latest_date", "latest_nav",
    "1w", "1m", "3m", "6m", "1y", "3y", "ytd", "since",
    "max_drawdown", "volatility", "sharpe", "calmar", "win_rate",
}

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "fund_metrics.xlsx"


def test_nav_flows_through_openbb_and_metrics_to_excel() -> None:
    try:
        frame = fetch_nav_history(FUND_CODE)
    except Exception as exc:  # 网络或上游故障，不是代码问题
        pytest.skip(f"AkShare 不可达: {exc}")

    assert not frame.empty
    assert {"date", "nav", "fund_code"} <= set(frame.columns)

    # 数据交给 OpenBB，再原样取回。
    obbject = to_obbject(frame)
    recovered = obbject.to_dataframe()
    assert obbject.provider == "akshare"
    assert len(recovered) == len(frame)

    # 用取回的净值计算指标。
    metrics = compute_metrics(to_nav_series(recovered), fund_code=FUND_CODE)
    assert metrics["fund_code"] == FUND_CODE
    assert metrics["latest_nav"] is not None
    # 这只基金有二十多年历史，长期指标都应该算得出来。
    for column in ("since", "max_drawdown", "volatility", "sharpe", "calmar", "win_rate"):
        assert metrics[column] is not None, f"{column} 不应为空"

    workbook = to_excel(
        recovered,
        OUTPUT,
        sheets={"净值": recovered, "指标": pd.DataFrame([metrics])},
        labels={"净值": NAV_LABELS, "指标": METRIC_LABELS},
    )

    assert workbook.exists()
    # 两张表的第一行都是中文含义，第二行才是列名，所以跳过一行再读。
    saved_nav = pd.read_excel(
        workbook, sheet_name="净值", dtype={"fund_code": str}, skiprows=1
    )
    saved_metrics = pd.read_excel(
        workbook, sheet_name="指标", dtype={"fund_code": str}, skiprows=1
    )
    nav_labels = pd.read_excel(workbook, sheet_name="净值", nrows=0)
    metric_labels = pd.read_excel(workbook, sheet_name="指标", nrows=0)

    assert list(nav_labels.columns) == [NAV_LABELS[column] for column in saved_nav.columns]
    assert list(metric_labels.columns) == [
        METRIC_LABELS[column] for column in saved_metrics.columns
    ]

    assert len(saved_nav) == len(frame)
    assert set(saved_nav["fund_code"]) == {FUND_CODE}
    assert METRIC_COLUMNS <= set(saved_metrics.columns)
    assert saved_metrics.loc[0, "fund_code"] == FUND_CODE
    assert saved_metrics.loc[0, "max_drawdown"] < 0
