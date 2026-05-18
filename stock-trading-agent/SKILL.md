---
name: stock-trading-agent
description: 自动炒股Agent v2.0 — 三层选股池+多因子评分+动态止盈止损+5只持仓上限+A股T+1适配
version: 2.0.0
tags: [stock, trading, agent, ai-trading, 自动选股, 量化, a-share, 多因子, 止盈止损]
related_skills: [interest-tracker]
---

# 📈 自动炒股Agent v2.0

## 概述

多因子选股 + 动态止盈止损 + 突发事件监控的自动化A股交易系统。

**核心改进：**
- 🎯 **三层选股池**：全市场 → 粗筛(~30只) → 精选(最多5只持仓)
- 📊 **多因子评分**：技术面+新闻面+板块+估值，纯Python粗筛，LLM精评
- 🛡️ **动态止盈止损**：初始-8%/+15%，浮动追踪上移
- 🚨 **事件监控**：个股急跌>5%/大盘暴跌>3%/板块暴跌>4%，被动推送
- 💰 **10万起步**，T+1适配，1手100股规则

---

## 架构

```
08:00 ─────→ 选股粗筛 (纯Python，零LLM)
             stock_screener.py
             ↓ 候选30只JSON
08:30 ─────→ 每日新闻简报 (morning_briefing.py)
09:00 ─────→ 开盘前分析 (stock_agent.py --session pre-market)
             │  ① 加载候选池
             │  ② 多因子评分
             │  ③ 生成买入/卖出订单
             ↓ 订单JSON
09:15-14:45 ─→ 事件监控 (stock_event_watcher.py, 每15分钟)
             │  遇突发→飞书推送
             ↓
09:30-14:57 ─→ 盘执行器 (stock_executor.py, 每15分钟)
                 执行待处理订单
                 触发止盈止损
11:35 ─────→ 午盘分析 (stock_agent.py --session midday)
             复盘+止盈止损调整
15:05 ─────→ 收盘复盘 (stock_agent.py --session close)
             统计+浮动止盈更新
```

### 三层股票池

| 层 | 名称 | 脚本 | LLM | 数量 | 说明 |
|:--|:-----|:-----|:---:|:----:|:-----|
| A | 粗筛池 | `stock_screener.py` | ❌ | ~30只 | 按成交量排前500→基础过滤(ST/市值/价格)→技术评分 |
| B | 精选池 | `stock_agent.py` (pre-market) | ✅ | 候选 | 多因子评分+LLM精评 |
| C | 执行池 | `stock_executor.py` | ❌ | ≤5只 | 持仓上限5只，买入执行 |

### 核心配置

| 参数 | 值 | 说明 |
|:-----|:--:|:------|
| 初始资金 | ¥100,000 | 模拟盘 |
| 最大持仓 | 5只 | 分散风险 |
| 最低现金 | ¥20,000 | 应急保留 |
| 单板块上限 | 40% | 避免板块集中 |
| 止损 | -8% → 浮动追踪 | 初始固定，盈利后浮动 |
| 止盈 | +15% → 浮动上移 | 盈利超过后追踪回撤5% |
| 浮动止盈激活 | +10% | 盈利超过后启动追踪 |
| T+1 | 当日买入不可卖 | agent_t1_tracker.json记录 |

---

## 组件清单

### 脚本 (`~/.hermes/scripts/`)

| 文件 | 类型 | LLM | 运行时间 | 说明 |
|------|:----:|:---:|:--------:|:------|
| `stock_screener.py` | 纯Python | ❌ | 08:00 | 选股粗筛 |
| `stock_agent.py` | AI Agent | ✅ | 09:00/11:35/15:05 | 多因子分析+决策 |
| `stock_executor.py` | 纯Python | ❌ | 每15分钟盘中 | 订单成交 |
| `stock_event_watcher.py` | 纯Python | ❌ | 每15分钟盘中 | 突发事件监控 |
| `market_calendar.py` | 工具 | ❌ | - | 交易日历 |

### Shell 包装脚本

| 文件 | 调用 |
|------|:-----|
| `stock_screener.sh` | `python3 ~/.hermes/scripts/stock_screener.py` |
| `stock_premarket.sh` | `python3 ~/.hermes/scripts/stock_agent.py --session pre-market` |
| `stock_midday.sh` | `python3 ~/.hermes/scripts/stock_agent.py --session midday` |
| `stock_close.sh` | `python3 ~/.hermes/scripts/stock_agent.py --session close` |
| `stock_executor.sh` | `python3 ~/.hermes/scripts/stock_executor.py` |
| `stock_event_watcher.sh` | `python3 ~/.hermes/scripts/stock_event_watcher.py` |

### 数据文件

| 文件 | 说明 |
|:-----|:------|
| `~/.hermes/skills/stock-trading-simulator/data/account.json` | 模拟账户(现金+持仓) |
| `~/.hermes/skills/stock-trading-simulator/data/trades.json` | 交易历史 |
| `~/.hermes/skills/stock-trading-simulator/data/agent_t1_tracker.json` | T+1锁定记录 |
| `~/.hermes/stock-trading-logs/orders/orders_YYYY-MM-DD.json` | 当日订单 |
| `~/.hermes/stock-trading-logs/candidates_YYYY-MM-DD.json` | 选股候选池 |
| `~/.hermes/stock-trading-logs/stop_config.json` | 止盈止损配置 |

### 日志

| 文件模式 | 说明 |
|:---------|:------|
| `screener_YYYY-MM-DD.log` | 选股粗筛日志 |
| `analysis_YYYY-MM-DD_pre-market.log` | 开盘前分析 |
| `analysis_YYYY-MM-DD_midday.log` | 午盘分析 |
| `analysis_YYYY-MM-DD_close.log` | 收盘复盘 |
| `executor_YYYY-MM-DD.log` | 盘执行器成交记录 |
| `event_watcher_YYYY-MM-DD.log` | 事件监控日志 |
| `event_log.json` | 事件去重记录 |
| `skip_YYYY-MM-DD_*.log` | 非交易日跳过记录 |

---

## 选股粗筛 (`stock_screener.py`)

纯Python脚本，零LLM消耗。

**数据源：** 新浪财经API (`vip.stock.finance.sina.com.cn`)

**过滤条件：**
1. 排除 `ST/*ST/退市/N/C` 股
2. 总市值 > 5亿
3. 股价 3~500元
4. 换手率 > 0.3%

**评分维度：**
- 均线排列（多头/空头，±6分）
- MACD（金叉/死叉，±3分）
- RSI（超卖/超买，±2分）
- 成交量（放量，+2分）
- 换手率活跃度（+3分）

**输出：** `candidates_YYYY-MM-DD.json` + 控制台日志

---

## 多因子分析 (`stock_agent.py`)

### 评分权重

| 因子 | 权重 | 说明 |
|:-----|:----:|:------|
| 技术面 | 30% | 选股器评分 + 二次确认 |
| 新闻面 | 30% | LLM实时分析当日新闻 |
| 板块 | 20% | 热门板块 + 分散度检查 |
| 资金/估值 | 20% | PE/PB + 资金流向 |

### 买入规则

| 条件 | 操作 |
|:-----|:------|
| 选股评分 >= 5 | `buy`（正常买入） |
| 选股评分 < 5 | **空仓观望，不买入** |
| 已有5只持仓 | 不买入 |
| 现金 < 最低保留 | 不买入 |
| 同板块已有持仓 | 跳过多只同板块 |
| 1手 > 3万元 | 跳过（资金限制） |

### 仓位计算

```
可用资金 = 总现金 - 最低保留(¥20,000)
每只投入 = 可用资金 / 剩余空位
买入股数 = floor(每只投入 / 股价 / 100) × 100
```

---

## 动态止盈止损

### 初始设置
- **止损价** = 买入价 × (1 - 8%) = 买入价的92%
- **止盈价** = 买入价 × (1 + 15%) = 买入价的115%

### 浮动追踪
- 当盈利 > **+10%** 时，启动浮动止损
- 浮动止损价 = 最高价 × (1 - 5%)
- 当盈利 > **+15%** 时，止盈线上移
- 止盈线 = 最高价 × (1 - 5%)，但高于上一个止盈价

### 每日更新
- 每次analysis运行（09:00/11:35/15:05）更新全部持仓的止盈止损
- 最高价更新 → 浮动止损自动上移
- 数据持久化在 `stop_config.json`

---

## 事件监控 (`stock_event_watcher.py`)

| 事件类型 | 阈值 | 触发操作 |
|:---------|:----:|:---------|
| 🔴 大盘暴跌 | 上证/深证/创业板 < -3% | 通知agent暂停开仓 |
| 🟠 板块暴跌 | 板块指数 < -4% | 通知agent检查板块持仓 |
| 🟠 持仓股急跌 | 持仓个股 < -5% | 通知agent检查止损 |

- 同类型同标的同一天不重复推送
- 无事件时静默（不发送飞书）
- 每次触发写入事件日志

---

## 定时任务

| 名称 | 时间 | 脚本 | 节假日 | 说明 |
|:----|:----:|:----|:------:|:-----|
| 选股-粗筛 | `0 8 * * 1-5` 工作日08:00 | `stock_screener.sh` | ❌ 休市跳过 | 全市场选股 |
| 每日新闻简报 | `30 8 * * *` 每天08:30 | `morning_briefing.py` | ✅ 不休 | 综合新闻 |
| 选股-开盘前 | `0 9 * * 1-5` 工作日09:00 | `stock_premarket.sh` | ❌ 休市跳过 | 分析→生成订单 |
| 事件监控 | `*/15 9-14 * * 1-5` 盘中每15分钟 | `stock_event_watcher.sh` | ❌ 休市跳过 | 突发事件推送 |
| 盘执行器 | `*/15 9-14 * * 1-5` 盘中每15分钟 | `stock_executor.sh` | ❌ 休市跳过 | 成交订单 |
| 选股-午盘 | `35 11 * * 1-5` 工作日11:35 | `stock_midday.sh` | ❌ 休市跳过 | 复盘→生成订单 |
| 选股-收盘 | `5 15 * * 1-5` 工作日15:05 | `stock_close.sh` | ❌ 休市跳过 | 仅复盘 |

> 参考：`references/trading-agents-architecture.md` — TauricResearch/TradingAgents 多代理金融交易框架架构详解

## 版本

| 版本 | 日期 | 变更 |
|:-----|:----|:------|
| **2.0.0** | 2026-05-18 | **全面重构**：三层选股池+动态池+多因子评分+动态止盈止损+5只上限+事件监控+10万重置 |
| 1.3.0 | 2026-05-15 | 盘执行器静默模式 |
| 1.0.0 | 2026-05-15 | 初始版本 |
