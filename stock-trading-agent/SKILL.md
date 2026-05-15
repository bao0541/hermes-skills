---
name: stock-trading-agent
description: 自动炒股Agent - 两阶段架构：分析计划(09:00/11:35/15:05) + 盘执行器(每15分钟盘中成交)。新闻+技术评分→自主买卖，T+1锁定，涨跌幅限制。
version: 1.3.0
tags: [stock, trading, agent, ai-trading, 自动选股, 量化, a-share]
related_skills: [interest-tracker]
---

# 📈 自动炒股Agent

## 概述

新闻驱动 + 技术分析 + 自主交易的自动化炒股系统。**两阶段分离架构**：

1. **📋 分析计划** — 在休市期生成买入/卖出订单计划
2. **⚡ 盘执行器** — 在交易时段（每15分钟）执行待处理订单

遵循A股实盘规则：T+1锁定、涨跌幅限制、交易时段过滤、按手取整。

---

## 架构详解

| 组件 | 脚本 | 运行时间 | 职责 |
|:----|:----|:--------:|:----|
| 📋 开盘前分析 | `stock_agent.py --session pre-market` | `09:00` 交易日 | 分析→生成订单计划（不下单成交） |
| 📋 午盘分析 | `stock_agent.py --session midday` | `11:35` 交易日 | 复盘→生成下午订单计划 |
| 📋 收盘复盘 | `stock_agent.py --session close` | `15:05` 交易日 | 纯复盘，不生成任何订单 |
| ⚡ 盘执行器 | `stock_executor.py` | `*/15 9-14 * * 1-5` | 盘中每15分钟成交待处理订单 |

### 实盘规则

| 规则 | 实现 |
|------|------|
| **T+1 锁定** | `agent_t1_tracker.json` 记录今日买入股数，当日不可卖 |
| **涨跌幅限制** | 主板±10%，688/300开头±20%（`stock_agent.py` 代码级限制） |
| **交易时段过滤** | 09:30-11:30 / 13:00-14:57，执行器自行判断，非交易时段静默退出 |
| **休市不下单** | Agent只在09:00/11:35生成订单计划，盘执行器只在交易时段成交 |

---

## 文件清单

### 脚本（`~/.hermes/scripts/`）

| 文件 | 说明 |
|------|------|
| `stock_agent.py` | 分析计划主脚本，3个session模式 |
| `stock_executor.py` | 盘执行器，盘中每15分钟运行 |
| `stock_premarket.sh` | 包装脚本：`python3 stock_agent.py --session pre-market` |
| `stock_midday.sh` | 包装脚本：`python3 stock_agent.py --session midday` |
| `stock_close.sh` | 包装脚本：`python3 stock_agent.py --session close` |
| `stock_executor.sh` | 包装脚本：`python3 stock_executor.py` |
| `morning_briefing.py` | 每日新闻简报（独立任务，08:30运行） |

### 数据文件（`~/.hermes/stock-trading-logs/orders/`）

订单文件按日期生成，**只有生成订单的交易日才会创建文件**（全HOLD不产生文件）：

| 文件 | 说明 |
|------|------|
| `orders_2026-05-18.json` | 5月18日有交易操作 |
| (不存在) | 5月19日全HOLD，无文件 |

文件结构：
```json
{
  "orders": [
    {
      "id": "abc12345",
      "date": "2026-05-18",
      "created_session": "pre-market",
      "code": "SH688041",
      "action": "buy",
      "shares": 300,
      "status": "executed",    // pending→executed/cancelled
      "executed_price": 305.20
    }
  ]
}
```

### 其他数据文件（`~/.hermes/skills/stock-trading-simulator/data/`）

| 文件 | 说明 |
|------|------|
| `account.json` | 模拟账户：现金、持仓、初始本金 |
| `trades.json` | 交易历史记录 |
| `agent_t1_tracker.json` | **T+1锁定**：记录今日买入股数 |

### 日志（`~/.hermes/stock-trading-logs/`）

| 文件模式 | 说明 |
|----------|------|
| `analysis_YYYY-MM-DD_pre-market.log` | 开盘前分析结果 |
| `analysis_YYYY-MM-DD_midday.log` | 午盘分析结果 |
| `analysis_YYYY-MM-DD_close.log` | 收盘复盘 |
| `executor_YYYY-MM-DD.log` | 盘执行器成交记录（追加模式） |

---

## 候选股票池

**当前持仓（8只，总资产~100万）：**
| 代码 | 名称 | 成本 | 状态 |
|------|------|:----:|:----:|
| SH688981 | 中芯国际 | 1,600股 @ 119.02 | 芯片制造龙头 |
| SZ300059 | 东方财富 | 10,100股 @ 19.73 | 券商受益牛市 |
| SZ001309 | 德明利 | 50股 @ 712.06 | 迷你仓位 |
| SH688041 | 海光信息 | 300股 @ 303.01 | 国产GPU/AI芯片 |
| SH603019 | 中科曙光 | 1,200股 @ 94.46 | AI算力基础设施 |
| SH603501 | 韦尔股份(豪威集团) | 500股 @ 101.39 | 汽车CIS放量 |
| SZ000938 | 紫光股份 | 1,800股 @ 31.91 | Q1净利+126% |
| SZ300750 | 宁德时代 | 100股 @ 423.60 | 新能源电池龙头 |

**候选观察：**
| 代码 | 名称 | 逻辑 | 优先级 |
|------|------|------|:------:|
| SZ002371 | 北方华创 | 半导体设备，RSI高位需等待 | medium |

---

## 评分系统

### 新闻面评分（-10~10，权重40%）

由 `get_news_score()` 函数维护在 `stock_agent.py` 中。评分标准：
- 业绩超预期：+2~3
- 行业景气度确认：+1~2
- 政策重大利好：+2
- 国产替代利好：+1~2
- 短期利空（减持/制裁）：-1~2

**需每周更新**以反映最新新闻。更新方式：
```bash
grep -A3 'scores = {' ~/.hermes/scripts/stock_agent.py
# 编辑后测试
python3 ~/.hermes/scripts/stock_agent.py --session close
```

### 技术面评分（-10~10，权重60%）

| 指标 | 加分 | 减分 |
|------|:----:|:----:|
| 均线排列 | 多头+3 | 空头-3 |
| RSI | 30~55之间+1~2 | >75超买-2，<25超卖+3 |
| MACD | 金叉+3，多头+1 | 死叉-3，空头-1 |
| 布林带 | 跌破下轨+2 | 突破上轨-1 |

### 综合评分
`综合分 = 新闻分×0.4 + 技术分×0.6`

### 决策阈值

| 条件 | 操作 | 仓位 |
|------|------|:----:|
| 综合分 >= 5.0 | 生成买入订单 | 现金的20%（最高20万） |
| 综合分 >= 2.0 | 生成轻仓订单 | 现金的10%（最高10万） |
| 亏损 >= 8% | 生成止损卖出订单 | 全部 |
| 盈利 >= 20% + 技术转弱 | 生成止盈订单 | 一半 |
| 综合分 <= -4.0 | 生成卖出订单 | 全部 |
| MACD死叉 + RSI>=70 | 生成减仓订单 | 一半 |

---

## 订单生命周期

```
agent_orders.json 结构：
{
  "orders": [
    {
      "id": "abc12345",           ← 哈希ID
      "date": "2026-05-18",
      "created_session": "pre-market",  ← 哪个时段生成的
      "created_at": "2026-05-18 09:00",
      "code": "SH688041",
      "name": "海光信息",
      "action": "buy",              ← buy/buy_light/sell_all/sell_half
      "shares": 300,
      "reason": "综合分5.0，买入",
      "price_ref": 303.01,
      "status": "pending"           ← pending→executed/cancelled
    }
  ]
}

生命周期：
  09:00 Agent生成 → status=pending
  09:30 执行器检查 → 盘中 → 调用stock_trader.py成交 → status=executed
              非盘中 → 保留pending，下次再试
  11:35 Agent生成新的 → 继续pending
  13:00 执行器成交
  15:05 收盘总结
  次日清理旧的cancelled/executed订单
```

---

## 定时任务一览

```bash
cronjob action=list
```

| 名称 | 时间 | 脚本 | 节假日 | 说明 |
|:----|:----:|:----|:------:|:----|
| 每日新闻简报 | `30 8 * * *` 每天08:30 | `morning_briefing.py` | ✅ 不休 | 综合+极客新闻 |
| 选股-开盘前 | `0 9 * * 1-5` 工作日09:00 | `stock_premarket.sh` | ❌ 休市跳过 | 分析→生成订单 |
| 选股-午盘 | `35 11 * * 1-5` 工作日11:35 | `stock_midday.sh` | ❌ 休市跳过 | 复盘→生成订单 |
| 选股-收盘 | `5 15 * * 1-5` 工作日15:05 | `stock_close.sh` | ❌ 休市跳过 | 仅复盘不交易 |
| 盘执行器 | `*/15 9-14 * * 1-5` 每15分钟 | `stock_executor.sh` | ❌ 休市跳过 | 盘中成交订单 |

## 交易日历

参考文件：`~/.hermes/scripts/market_calendar.py`

所有股票分析/交易任务（09:00/11:35/15:05 + 盘执行器）在进入主逻辑前先调用 `is_trading_day()` 判断：

- **周末** → 跳过
- **法定节假日**（元旦/春节/清明/劳动/端午/国庆）→ 跳过
- **调休工作日**（周末补班）→ 正常交易（`MAKEUP_DAYS_2026` 集合维护）

**注意**：`market_calendar.py` 中 `HOLIDAYS_2026` 集合只记录了 **非周末的休市日**，周末已由 `weekday() >= 5` 自动处理。

### 2026年已知休市日

```
1/1(四) 1/2(五)     → 元旦
2/16(一)~2/20(五) 2/23(一) → 春节
4/6(一)             → 清明
5/1(五) 5/4(一) 5/5(二) → 劳动节
6/19(五)            → 端午
10/1(四) 10/2(五) 10/5(一)~10/7(三) → 国庆
```

若有新的调休安排，更新 `MAKEUP_DAYS_2026` 和 `HOLIDAYS_2026` 即可。

---

每日日志对比分析：
```bash
# 查看今日所有日志
cat ~/.hermes/stock-trading-logs/analysis_$(date +%Y-%m-%d)_*.log

# 查看执行记录
cat ~/.hermes/stock-trading-logs/executor_$(date +%Y-%m-%d).log

# 查看账户状态
python3 ~/.hermes/skills/stock-trading-simulator/scripts/stock_trader.py positions
```

改进方向：
1. 新闻评分需每周更新，反映最新市场变化
2. 候选股池可按新闻主线动态调整
3. 评分权重（新闻40%/技术60%）可根据复盘结果调整
4. 可增加更多技术指标（成交量、OBV等）
