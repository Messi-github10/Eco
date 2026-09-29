from __future__ import annotations

import pandas as pd

TRADING_DAYS = 252  # 一年按 252 个交易日计
RISK_FREE_RATE = 0.02  # 无风险利率

# 指标列名到中文含义，写 Excel 时作为表头说明。
METRIC_LABELS = {
    "fund_code": "基金代码",
    "latest_date": "最新净值日期",
    "latest_nav": "最新单位净值",
    "1w": "近一周收益",
    "1m": "近一月收益",
    "3m": "近三月收益",
    "6m": "近六月收益",
    "1y": "近一年收益",
    "3y": "近三年收益",
    "ytd": "今年以来收益",
    "since": "成立以来收益",
    "max_drawdown": "最大回撤",
    "volatility": "年化波动率",
    "sharpe": "夏普比率",
    "calmar": "卡玛比率",
    "win_rate": "月度胜率",
}
PERIODS = {
    "1w": 5,
    "1m": 22,
    "3m": 66,
    "6m": 132,
    "1y": 252,
    "3y": 756,
}


def period_return(nav: pd.Series, periods: int) -> float | None:
    # 近若干个交易日的收益率，即最新净值相对回看位置净值的涨跌幅
    if len(nav) < 2:
        return None
    earlier = nav.iloc[max(0, len(nav) - 1 - periods)]
    if earlier == 0:
        return None
    return (nav.iloc[-1] - earlier) / earlier


def ytd_return(nav: pd.Series) -> float | None:
    # 今年以来收益率
    if nav.empty:
        return None
    this_year = nav[nav.index.year == nav.index.year.max()]
    return period_return(nav, len(this_year))


def total_return(nav: pd.Series) -> float | None:
    # 成立以来收益率
    if len(nav) < 2 or nav.iloc[0] == 0:
        return None
    return (nav.iloc[-1] - nav.iloc[0]) / nav.iloc[0]


def max_drawdown(nav: pd.Series) -> float | None:
    # 最大回撤：净值从阶段高点跌到低点的最大幅度
    if len(nav) < 5:
        return None
    peak = nav.expanding().max()
    return float(((nav - peak) / peak).min())


def volatility(nav: pd.Series, trading_days: int = TRADING_DAYS) -> float | None:
    # 年化波动率：日收益率的标准差乘以一年交易日数的平方根
    if len(nav) < 10:
        return None
    daily = nav.pct_change().dropna()
    if len(daily) < 5:
        return None
    return float(daily.std() * (trading_days ** 0.5))


def sharpe(nav: pd.Series, risk_free: float = RISK_FREE_RATE) -> float | None:
    # 夏普比率：(年化收益 - 无风险利率) / 年化波动率，衡量单位风险换来的超额收益
    vol = volatility(nav)
    if vol is None or vol == 0:
        return None
    daily = nav.pct_change().dropna()
    if len(daily) < 5:
        return None
    annual_return = (1 + daily.mean()) ** TRADING_DAYS - 1
    return (annual_return - risk_free) / vol


def calmar(nav: pd.Series) -> float | None:
    # 卡玛比率：成立以来总收益除以最大回撤的绝对值，回撤越小比值越高
    drawdown = max_drawdown(nav)
    if drawdown is None or drawdown == 0:
        return None
    overall = total_return(nav)
    if overall is None:
        return None
    return overall / abs(drawdown)


def win_rate(nav: pd.Series) -> float | None:
    # 胜率：收涨月份占全部月份的比例。先把日收益合成月收益再统计
    if len(nav) < 30:
        return None
    daily = nav.pct_change().dropna()
    if len(daily) < 5:
        return None
    monthly = daily.resample("ME").apply(lambda x: (1 + x).prod() - 1).dropna()
    if len(monthly) < 3:
        return None
    return float((monthly > 0).sum() / len(monthly))


def correlation(nav_a: pd.Series, nav_b: pd.Series) -> float | None:
    # 两只基金的相关系数：取日期重叠的部分算皮尔逊相关，越接近 1 走势越同步
    if nav_a.empty or nav_b.empty:
        return None
    aligned = pd.concat([nav_a, nav_b], axis=1, join="inner").dropna()
    if len(aligned) < 10:
        return None
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))


def compute_metrics(nav: pd.Series, fund_code: str = "") -> dict:
    # 把一只基金的全部指标合成一行，多只基金拼起来就是一张表
    returns = {name: period_return(nav, periods) for name, periods in PERIODS.items()}
    return {
        "fund_code": fund_code,
        "latest_date": str(nav.index[-1].date()) if not nav.empty else None,
        "latest_nav": float(nav.iloc[-1]) if not nav.empty else None,
        **returns,
        "ytd": ytd_return(nav),
        "since": total_return(nav),
        "max_drawdown": max_drawdown(nav),
        "volatility": volatility(nav),
        "sharpe": sharpe(nav),
        "calmar": calmar(nav),
        "win_rate": win_rate(nav),
    }


def to_nav_series(frame: pd.DataFrame) -> pd.Series:
    # 把数据层拉到的净值表转成按日期索引的序列
    # 重复日期只保留最后一条，并按日期升序排列
    if frame.empty:
        return pd.Series(dtype=float)
    series = pd.Series(
        frame["nav"].to_numpy(),
        index=pd.to_datetime(frame["date"]),
        dtype=float,
    )
    series = series[~series.index.duplicated(keep="last")]
    return series.sort_index()
