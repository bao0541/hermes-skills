---
name: crypto-trading-agent
description: 🤖 AI盯盘自动炒币系统 — 30分钟/次 + 波动密集检查。模拟/真盘双模式，币安数据源，ETH为主。分析市场→决策买卖→通知飞书。
version: 1.0.1
tags: [crypto, trading, eth, binance, ai-trading, 自动炒币, 量化]
---

> **费用约定：** 日常沟通中金额默认用人民币（元）计价。数字货币买卖按ETH/BTC计价时才保留U/美元。

## 运行成本

DeepSeek V4 Flash 定价（2026年5月）：
- 缓存命中输入: $0.0028/百万tokens
- 新输入: $0.14/百万tokens
- 输出: $0.28/百万tokens

| 项目 | 每次 | 每天(48次) | 每月 |
|:----|:---:|:----------:|:----:|
| 成本 | ~0.7分 | ~3毛5 | ~10~15元 |

# 🤖 加密货币AI盯盘交易系统

## 概述

AI驱动的主动盯盘交易系统，不是死板跑策略机器人。每30分钟定时触发AI分析，遇到波动自动加密检查频次。模拟盘验证稳定后再切真盘。

**核心资产：ETH/USDT**（可选BTC/USDT双币）

## 架构

```
cron 每30分钟 → 触发AI分析
       │
       ▼
crypto_agent.py → 输出市场+账户数据
       │
       ▼
AI分析决策 → buy/sell/hold/stop-loss/scale-in
       │
       ▼
crypto_account.py → 执行模拟交易/更新持仓
       │
       ▼
飞书通知 → 用户看到实时决策
```

## 脚本路径

| 脚本 | 路径 | 说明 |
|------|------|------|
| 市场数据 | `~/.hermes/crypto-simulator/scripts/crypto_market.py` | 币安行情+技术指标 |
| 账户管理 | `~/.hermes/crypto-simulator/scripts/crypto_account.py` | 虚拟账户：买/卖/持仓/历史 |
| 综合分析 | `~/.hermes/crypto-simulator/scripts/crypto_agent.py` | 合二为一，供AI消费 |

## 数据文件

| 文件 | 说明 |
|------|------|
| `~/.hermes/crypto-simulator/data/account.json` | 账户余额、持仓 |
| `~/.hermes/crypto-simulator/data/trades.json` | 交易记录 |
| `~/.hermes/crypto-simulator/logs/` | 分析日志 |

## 定时任务

| 名称 | 频率 | 说明 |
|:----|:----:|:----|
| 🟢 常规盯盘 | 每30分钟 | 行情分析+AI决策+飞书通知 |
| 🔴 波动密集 | 波动时10分钟 | 检测到剧烈波动自动加密 |

## AI决策逻辑

每次触发，AI分析以下维度：

1. **趋势方向** — 多时间框架对齐（15m/1h/4h）
2. **SuperTrend指标** — 趋势跟踪信号（ATR=10, 倍数=3），所有周期都向上才是强信号
3. **RSI位置** — 超买/超卖/中性
4. **MACD信号** — 金叉/死叉/柱线变化
5. **布林带** — 突破上下轨/带宽收窄扩张
6. **成交量** — 异常放量/缩量
7. **波动率** — ATR、日均波动幅度
8. **持仓状态** — 浮盈浮亏、保证金占用
9. **市场情绪** — 综合评分

### 参考策略（朋友的实战参数）

朋友用的 SuperTrend + 马丁格尔混合策略：
- **开仓信号：** SuperTrend 转方向时入场（趋势跟踪）
- **初始仓位：** 0.1 ETH（1000u为基准）
- **止盈：** 2%（价格涨2%自动止盈）
- **止损：** 2%（价格跌2%自动止损）
- **翻倍补仓：** 若止损出局，下次信号翻倍开仓（0.1→0.2→0.4...）

> ⚠️ 注意：翻倍补仓是马丁格尔变种，N连败后仓位会指数级增长。AI应根据市场环境判断是否启用该策略。

### 决策选项

| 动作 | 条件举例 |
|------|---------|
| 开仓买入 | 趋势明确+RSI合理+量价配合 |
| 马丁格尔补仓 | 持仓浮亏达到预设档位间距 |
| 减仓/部分止盈 | RSI超买+MACD走弱 |
| 止损退出 | 趋势逆转/跌幅超阈值 |
| 暂停交易 | 波动极端/方向不明 |
| 空仓等待 | 无明显机会 |

## 马丁格尔策略参数（参考）

初始1000u，ETH为例：
| 层级 | 仓位 | 所需保证金 | 价格跌幅 |
|:----:|:----:|:---------:|:--------:|
| 1 | 0.05 ETH | ~110u | - |
| 2 | 0.10 ETH | ~330u | -3% |
| 3 | 0.20 ETH | ~770u | -6% |
| 4 | 0.30 ETH | ~1430u | -9% (超支) |

**注意：** 1000u最多扛3层。建议设总止损线（如总亏-15%强制清仓），不要让马丁格尔无限滚下去。

## 波动密集检测规则

当以下任一条件触发，自动排入10分钟密集检查：
- 最近1根15分钟K线涨跌幅 > 1.5%
- 波动率等级为 "high" 或 "extreme"
- 价格突破布林带上下轨
- 15分钟MACD柱线突增

## 使用

```bash
# 查看账户状态
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py status

# 手动分析市场
python3 ~/.hermes/crypto-simulator/scripts/crypto_agent.py "ETH/USDT"

# 查看交易历史
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py history

# 重置模拟盘
python3 ~/.hermes/crypto-simulator/scripts/crypto_account.py reset 1000
```

## 切换真盘

1. 注册币安，获取API Key（仅开交易权限）
2. 安装 `ccxt` 配置真实API密钥
3. 修改 `crypto_account.py` 添加真盘执行器（继承模拟接口）
4. 冲U到账户
5. 关闭模拟盘，开启真盘cron
