# L1 数据层方案

## 1. 数据源映射（AKShare）

| 目标表 | AKShare 接口 | 频率 | 状态 |
|---|---|---|---|
| dim_fund | `fund_etf_spot_em` | 快照 | ✅ |
| dim_fund（费率/上市日） | `fund_etf_fund_info_em` | 快照 | ✅ 待验证字段 |
| dim_trade_calendar | `tool_trade_date_hist_sina` | 一次性 | ✅ |
| fact_fund_quote_daily | `fund_etf_hist_em(adjust="qfq")` | 日频 | ✅ |
| fact_fund_quote_daily（LOF） | `fund_lof_hist_em` | 日频 | ✅ |
| fact_fund_nav_daily | `fund_etf_fund_info_em` / `fund_open_fund_info_em` | 日频 | ✅ 有滞后 |
| fact_fund_share_daily（沪） | `fund_etf_scale_sse` 系列 | 日频 | ✅ |
| fact_fund_share_daily（深） | `fund_etf_scale_szse` 系列 | 日频 | ✅ |
| fact_index_quote_daily | `index_zh_a_hist` / `stock_zh_index_daily` | 日频 | ✅ |
| fact_macro_monthly | 宏观数据各接口 | 月/季 | ✅ |
| fact_factor_daily | 本地计算 | 日频 | 派生 |

**接口名以实际版本为准**，落地前先逐个冒烟测试；AKShare 接口会随版本改名。

## 2. 表结构（DuckDB DDL）

```sql
-- 标的主数据
CREATE TABLE dim_fund (
  code          VARCHAR PRIMARY KEY,  -- 6位列代码
  name          VARCHAR,
  fund_type     VARCHAR,              -- ETF/LOF/QDII/REITs
  track_index   VARCHAR,              -- 跟踪指数代码
  market        VARCHAR,              -- SH/SZ/BJ
  is_cross_border BOOLEAN,            -- 是否跨境(QDII类)
  list_date     DATE,
  delist_date   DATE,
  mgmt_fee      DECIMAL(6,4),
  custody_fee   DECIMAL(6,4),
  updated_at    TIMESTAMP
);

-- 交易日历
CREATE TABLE dim_trade_calendar (
  cal_date      DATE PRIMARY KEY,
  is_open       BOOLEAN,
  prev_open     DATE,
  next_open     DATE
);

-- 日频行情（前复权 + 原始并存）
CREATE TABLE fact_fund_quote_daily (
  code          VARCHAR,
  trade_date    DATE,
  open_raw      DECIMAL(12,4),
  high_raw      DECIMAL(12,4),
  low_raw       DECIMAL(12,4),
  close_raw     DECIMAL(12,4),
  open_qfq      DECIMAL(12,4),   -- 前复权
  close_qfq     DECIMAL(12,4),
  volume        BIGINT,          -- 手
  amount        DECIMAL(20,2),   -- 元
  turnover_rate DECIMAL(10,6),
  adj_factor    DECIMAL(12,6),   -- 复权因子，用于对账
  PRIMARY KEY (code, trade_date)
);

-- 净值
CREATE TABLE fact_fund_nav_daily (
  code            VARCHAR,
  nav_date        DATE,
  unit_nav        DECIMAL(12,6), -- 单位净值
  acc_nav         DECIMAL(12,6), -- 累计净值
  publish_date    DATE,          -- 实际公布日(防信息泄漏)
  PRIMARY KEY (code, nav_date)
);

-- 份额/规模
CREATE TABLE fact_fund_share_daily (
  code            VARCHAR,
  trade_date      DATE,
  shares          DECIMAL(20,2),
  aum             DECIMAL(20,2),
  PRIMARY KEY (code, trade_date)
);

-- 指数行情
CREATE TABLE fact_index_quote_daily (
  index_code      VARCHAR,
  trade_date      DATE,
  open            DECIMAL(14,4),
  high            DECIMAL(14,4),
  low             DECIMAL(14,4),
  close           DECIMAL(14,4),
  volume          BIGINT,
  amount          DECIMAL(20,2),
  PRIMARY KEY (index_code, trade_date)
);

-- 宏观
CREATE TABLE fact_macro_monthly (
  indicator       VARCHAR,
  period          DATE,
  value           DECIMAL(20,6),
  publish_date    DATE,          -- 实际公布日
  PRIMARY KEY (indicator, period)
);

-- 因子宽表（L2 产出）
CREATE TABLE fact_factor_daily (
  code            VARCHAR,
  trade_date      DATE,
  factor_name     VARCHAR,
  value           DECIMAL(20,8),
  PRIMARY KEY (code, trade_date, factor_name)
);
```

## 3. 三个必须做对的地方

### 3.1 复权（最高优先级）

ETF 分红/拆分不做前复权 → 收益率全错。

- 优先用接口自带 `adjust="qfq"`
- 但**必须自己验算**：取 3~5 只有分红记录的标的，手工核对 `close_qfq` 连续性
- 保留 `adj_factor` 字段，便于回溯与对账
- 若接口复权不可靠 → 自己按分红公告算复权因子

### 3.2 发布日对齐（防信息泄漏）

| 数据 | 报告期 | 实际公布日 | 滞后 |
|---|---|---|---|
| 季报持仓 | 3/31 | 4 月下旬 | ~3 周 |
| 半年报持仓 | 6/30 | 8 月底 | ~2 月 |
| 年报持仓 | 12/31 | 次年 3 月底 | ~3 月 |
| QDII 净值 | T | T+1~T+2 | 视产品 |

**所有表都带 `publish_date`**，特征工程按 `publish_date` 对齐，不按 `period`。

### 3.3 QDII 净值滞后

跨境 ETF 净值天然滞后 + 时区差。一期先不做 QDII，二期单独处理：
- 净值对齐到公布日
- 引入跟踪指数在 A 股休市期间的表现作为代理信号

## 4. 数据质量校验清单

| 检查项 | 规则 | 处理 |
|---|---|---|
| 主键重复 | 唯一性断言 | 报错阻断 |
| 缺失值 | 交易日应有行情 | 记录 + 插值策略 |
| 异常收益 | 单日 \|ret\| > 20%（非 ETF 合理） | 人工复核 |
| 复权连续性 | 复权后无跳空（除权日除外） | 对账 |
| 时区 | 全部转 Asia/Shanghai | 统一 |
| 份额突变 | 单日变化 > 50% | 复核拆分/合并 |

校验产出：`data/quality_report_YYYYMMDD.json`

### 4.1 双源交叉验证（东财 vs 新浪，具体执行细节）

`05-risks.md` 提到"单源数据错误 → 关键字段交叉验证"，这里给出可直接落地的执行方案：

| 项 | 方案 |
|---|---|
| 交叉验证字段 | `close_raw`（原始收盘价）、`volume`（成交量）——这两个字段两个源都有且定义一致，其他字段（如 turnover_rate 计算口径可能不同）不纳入交叉验证 |
| 数据源 A | AKShare `fund_etf_hist_em`（东方财富） |
| 数据源 B | AKShare `fund_etf_hist_sina` 或 `stock_zh_a_hist`（新浪，若无对应ETF接口则退化为只对指数行情做交叉验证） |
| 对比频率 | **每日取数后立即跑一次**（不是事后批量抽查），成本低（20~40只标的，两源各拉一次，几秒钟） |
| 阈值 | `\|close_A - close_B\| / close_A > 0.5%` 触发告警；`volume` 允许口径差异（手/股不统一是常见坑），只做数量级校验（差异 > 20% 才告警） |
| 触发后动作 | 写入 `data/quality_report_YYYYMMDD.json` 的 `cross_source_mismatch` 字段，**当日不自动选源覆盖**，标记为待复核，落库时优先使用东财（主源），新浪仅作校验，不参与建模 |
| 覆盖范围 | 全量标的每日跑，不做抽样——抽样会漏掉真正出问题的那只 |
| 历史回溯 | 首次建库时对 5 年历史数据做一次全量双源对账（可以放宽到抽样 20%，因为历史数据出错概率低于当日数据源故障，且全量对账 5年×40只成本较高） |

**为什么不做更复杂的三源交叉**：个人项目维护成本要控制，两源交叉已能覆盖"单一接口挂了/返回脏数据"这个最常见的故障模式；如果东财和新浪都同时出同样的错误（比如都用同一个上游数据商），交叉验证会失效——这是已知局限，不追加第三方数据源（如Wind/Tushare Pro）的原因是个人项目成本不划算，此处接受这个残余风险。

## 5. 目录结构

```
etf-alloc/
  docs/                 方案文档（本目录）
  src/
    fetch/              AKShare 取数脚本
    transform/          清洗 + 复权 + 校验
    factor/             因子计算
    model/              模型
    optimize/           组合优化
    backtest/           回测引擎
    viz/                Streamlit 看板
  data/
    raw/                原始落地（parquet）
    warehouse.duckdb    数仓
    quality_reports/
  notebooks/            探索用
  config/
    universe.yaml       标的池
    params.yaml         L0 参数
```

## 6. AKShare 使用注意

- **版本漂移**：接口随时改名/失效 → `requirements.txt` 锁版本，且取数层加降级逻辑
- **限频**：批量拉取需间隔，加退避重试
- **数据校验**：不信任单源，关键字段交叉验证（具体阈值与执行频率见 §4.1）
- **合规**：官方声明仅学术研究，商用自担风险
