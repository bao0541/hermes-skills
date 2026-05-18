---
name: crypto-trading-agent
description: 🤖 AI盯盘自动炒币系统 — 基于研究的趋势跟踪策略。1h SuperTrend + 200EMA过滤 + 反马丁格尔仓位管理。
version: 1.2.1
tags: [crypto, trading, eth, supertrend, ema200, anti-martingale, 自动炒币, 量化]
---

# 🤖 加密货币AI盯盘交易系统 v1.2

> 基于研究的最优方案，非朋友亏损策略。

## 策略核心

**来源：** 综合 TradingView社区、QuantifiedStrategies、Reddit r/algotrading、知乎等多源研究得出的优化方案。

| 组件 | 选择 | 依据 |
|:----|:----|:------|
| 信号指标 | 1h SuperTrend (ATR=10, 倍率=3) | 标准参数，广泛测试 |
| 趋势过滤 | **200 EMA** | 研究证实加200EMA过滤后胜率从35%→50-57% |
| 出场方式 | **SuperTrend翻回即出**（非固定止盈） | 趋势跟踪最佳实践，避免矛盾 |
| 仓位管理 | **反马丁格尔**（赢×1.5，输归1） | 经典马丁格尔数学上必然爆仓 |
| 风险控制 | 每单固定亏$10（1%） | 公认的仓位管理标准 |
| 双向交易 | ✅ 做多/做空 | 200EMA上下分别做 |

## 入场规则

```
做多: 价格 > 200 EMA + 1h SuperTrend翻多 → 开多
做空: 价格 < 200 EMA + 1h SuperTrend翻空 → 开空
```

## 出场规则

```
做多: 1h SuperTrend翻空 → 平仓（SuperTrend线自动跟踪价格作为止损）
做空: 1h SuperTrend翻多 → 平仓
```

**不设固定止盈。** SuperTrend线本身就是移动止损，趋势持续多久拿多久。

## 仓位计算

```
风险/单:        $10（账户1%）
止损距离:      abs(现价 - SuperTrend线值) 或 3 × ATR（取较大者）
基础仓位:      $10 ÷ 止损距离(美元)

反马丁格尔乘数:
  初始:         1.0
  盈利后:       ×1.5（乘数累积，上限3.0）
  亏损后:       =1.0（重置）

实际仓位:      基础仓位 × 反马丁格尔乘数
```

## 黑天鹅应急预案

每次定时任务执行前，先运行预警检查 `black_swan_check.py`。

| 级别 | 触发条件 | 操作 | 冷静期 |
|:----:|:---------|:-----|:------|
| 🟡 **黄色** | 波动率extreme / 布林带突破+24h波幅>5% | 暂停开仓，持仓不动 | 6小时 |
| 🟠 **橙色** | 24h跌幅 > **10%** | 强制平仓所有持仓 | 24小时 |
| 🔴 **红色** | 24h跌幅 > **20%**（312级事件） | 全平台停止，仅发通知 | 72小时 |

冷静期内不开新仓。到期自动恢复。

## 修改历史

| 版本 | 变更 |
|:----:|:-----|
| 1.0.0 | 初始版，参考朋友马丁格尔策略 |
| 1.0.1 | 加费用约定、运行成本 |
| 1.0.2 | 加SuperTrend指标 |
| 1.1.0 | 支持双向交易、动态止盈、分批止盈 |
| **1.2.1** | **Bugfix: 做空时总资产/收益率计算错误。修复total_assets公式为 free_balance + unrealized_pnl；修复crypto_agent.py做空未实现盈亏计算复用 `value-cost` 导数为0的问题** |
| 1.2.0 | 全面重构 — 研究驱动的新策略。去掉固定止盈/动态止盈/分批止盈/半仓试探/日线过滤，改用200EMA趋势过滤+SuperTrend翻转出场+反马丁格尔仓位管理 |

## 脚本路径

| 脚本 | 路径 | 说明 |
|------|------|------|
| 市场数据 | `~/.hermes/crypto-simulator/scripts/crypto_market.py` | 币安行情+技术指标（SuperTrend, EMA200, ATR） |
| 账户管理 | `~/.hermes/crypto-simulator/scripts/crypto_account.py` | 双向交易+反马丁格尔跟踪 |
| 综合分析 | `~/.hermes/crypto-simulator/scripts/crypto_agent.py` | AI消费用摘要输出 |

## 使用

```bash
# 查看账户
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py status

# 手动分析
python3 ~/.hermes/crypto-simulator/scripts/crypto_agent.py "ETH/USDT"

# 开仓
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py open ETH/USDT long <数量> <价格> "<理由>"

# 平仓
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py close ETH/USDT <数量> <价格> "<理由>"

# 重置
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py reset 1000
```
