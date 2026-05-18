# Hermes Skills

Hermes Agent 自定义技能集 — 包含量化交易、新闻追踪、AI 自动化等实用技能。

---

## 技能列表

### 🤖 crypto-trading-agent

AI 自动盯盘炒币系统 — 1h SuperTrend + 200EMA 趋势过滤 + 反马丁格尔仓位管理。策略基于 TradingView 社区、QuantifiedStrategies、Reddit r/algotrading 等多源研究优化。

| 组件 | 说明 |
|:----|:-----|
| 信号指标 | 1h SuperTrend (ATR=10, 倍率=3) |
| 趋势过滤 | 200 EMA（研究证实加过滤后胜率从 35% → 50-57%） |
| 出场方式 | SuperTrend 翻回即出（不设固定止盈） |
| 仓位管理 | 反马丁格尔（赢 ×1.5，输归 1，上限 3x） |
| 双向交易 | ✅ 做多/做空 |
| 黑天鹅预案 | 🟡橙色(跌10%平仓) / 🔴红色(跌20%全面停止) |

**运行频率：** 每30分钟自动分析，策略信号触发时入场/出场。

[查看详情 →](crypto-trading-agent/SKILL.md)

---

### 📈 stock-trading-agent

自动炒股 Agent — A股两阶段架构：分析计划 + 盘执行器。

| 组件 | 运行时间 | 说明 |
|:----|:--------:|:-----|
| 开盘前分析 | `09:00` 交易日 | 分析 → 生成订单计划 |
| 午盘分析 | `11:35` 交易日 | 复盘 → 生成下午订单计划 |
| 收盘复盘 | `15:05` 交易日 | 纯复盘，不交易 |
| 盘执行器 | `*/15 9-14 * * 1-5` | 盘中每15分钟成交订单 |

**评分系统：** 新闻面评分(40%) + 技术面评分(60%)，触发买入/卖出/止盈/止损。  
**实盘规则：** T+1锁定、涨跌幅限制、节假日日历、交易时段过滤。  
**数据源：** 腾讯行情API（qt.gtimg.cn）

[查看详情 →](stock-trading-agent/SKILL.md)

---

### 📬 interest-tracker

自动兴趣追踪 — 每天从综合新闻源匹配你关心的领域/话题并推送。用户只需说"关注XXX"，自动配置关键词和优先级。

| 时间 | 说明 |
|:----:|:-----|
| `09:00` 每天 | 获取当日新闻 → 关键词匹配 → 推送相关条目 |

**匹配逻辑：** 标题包含任一关键词即命中，按热度排序取前 3 条。  
**数据源：** 依赖 [news-fetcher](#-news-fetcher) 模块，6 源聚合（~166条/天）

[查看详情 →](interest-tracker/SKILL.md)

---

### 📰 news-fetcher

多源新闻抓取模块 — 从 6 个免费新闻源统一抓取并去重。可作 Python 模块导入，也支持命令行。

| 源 | 条数 | 语言 | 类型 |
|:---|:----:|:----:|:-----|
| topurl.cn | ~20 | 中文 | 综合 |
| 搜狐新闻 | ~20 | 中文 | 正规媒体 |
| Google News RSS | ~26 | 中文 | 多源聚合 |
| Actually Relevant RSS | ~50 | 英语 | AI 精选 |
| 新浪财经 | ~20 | 中文 | 财经新闻 |
| 36氪 | ~30 | 中文 | 科技/商业 |
| **合计** | **~166** | | |

**无需 API Key，纯标准库依赖。** 供 `interest-tracker` 和每日简报等消费者调用。

[查看详情 →](news-fetcher/SKILL.md)

---

## 安装

```bash
# 将所有技能复制到 Hermes Agent skills 目录
cp -r crypto-trading-agent ~/.hermes/skills/
cp -r stock-trading-agent ~/.hermes/skills/software-development/
cp -r stock-trading-simulator ~/.hermes/skills/
cp -r interest-tracker ~/.hermes/skills/
cp -r news-fetcher ~/.hermes/skills/

# 复制脚本到脚本目录
cp crypto-trading-agent/scripts/*.py ~/.hermes/scripts/
cp stock-trading-agent/scripts/*.py ~/.hermes/scripts/
cp interest-tracker/scripts/*.py ~/.hermes/scripts/
cp news-fetcher/scripts/*.py ~/.hermes/scripts/
```

## 依赖关系

- `interest-tracker` 依赖 `news-fetcher` 获取新闻数据
- `crypto-trading-agent` 独立运行，依赖币安/CoinGecko 行情
- 每日定时链：新闻简报 08:30 → 兴趣追踪 09:00 → 开盘分析 09:00（仅交易日）
