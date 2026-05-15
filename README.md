# Hermes Skills

Hermes Agent 自定义技能集。

## 技能列表

### 📈 stock-trading-agent

自动炒股 Agent — 两阶段架构，新闻驱动 + 技术分析，自主买卖决策。模拟账户实盘运行。

| 组件 | 运行时间 | 说明 |
|:----|:--------:|:-----|
| 开盘前分析 | `09:00` 交易日 | 分析→生成订单计划 |
| 午盘分析 | `11:35` 交易日 | 复盘→生成下午订单计划 |
| 收盘复盘 | `15:05` 交易日 | 纯复盘，不交易 |
| 盘执行器 | `*/15 9-14 * * 1-5` | 盘中每15分钟成交订单 |

**评分系统：** 新闻面评分(40%) + 技术面评分(60%)，触发买入/卖出/止盈/止损。  
**实盘规则：** T+1锁定、涨跌幅限制、节假日日历、交易时段过滤。  
**数据源：** 腾讯行情API（qt.gtimg.cn）

[查看详情 →](stock-trading-agent/SKILL.md)

### 📬 interest-tracker

自动兴趣追踪 — 每天从综合新闻源匹配你关心的领域/话题并推送。被动匹配、按关键词过滤。

| 时间 | 说明 |
|:----:|:-----|
| `09:00` 每天（含周末） | 获取当日新闻 → 关键词匹配 → 推送相关条目 |

**匹配逻辑：** 标题包含任一关键词即命中，按热度排序取前 3 条。  
**数据源：** 依赖 [news-fetcher](news-fetcher/SKILL.md) 模块，4 源聚合（topurl/搜狐/Google/Relevant）

[查看详情 →](interest-tracker/SKILL.md)

### 📰 news-fetcher

多源新闻抓取模块 — 从 4 个免费新闻源统一抓取并去重。可作 Python 模块导入，也支持命令行。

| 源 | 条数 | 语言 | 类型 |
|:---|:----:|:----:|:-----|
| topurl.cn | ~20 | 中文 | 综合 |
| 搜狐新闻 | ~20 | 中文 | 正规媒体 |
| Google News RSS | ~26 | 中文 | 多源聚合 |
| Actually Relevant RSS | ~50 | 英语 | AI 精选 |
| 新浪财经 | ~20 | 中文 | 财经新闻 |
| 36氪 | ~30 | 中文 | 科技/商业 |
| **合计** | **~166** | | |

**无需 API Key，纯标准库依赖。** 供 `interest-tracker` 和 `morning_briefing.py` 等消费者调用。

[查看详情 →](news-fetcher/SKILL.md)

---

## 安装

```bash
# 将所有技能复制到 Hermes Agent skills 目录
cp -r stock-trading-agent ~/.hermes/skills/software-development/
cp -r interest-tracker ~/.hermes/skills/
cp -r news-fetcher ~/.hermes/skills/

# 复制脚本到 scripts 目录
cp stock-trading-agent/scripts/*.py ~/.hermes/scripts/
cp interest-tracker/scripts/*.py ~/.hermes/scripts/
cp news-fetcher/scripts/*.py ~/.hermes/scripts/
```

## 关联

- `interest-tracker` 依赖 `news-fetcher` 获取新闻数据
- `interest-tracker` 与 `stock-trading-agent` 共用开盘前分析时段（09:00）
- 每日定时：新闻简报 08:30 → 兴趣追踪 09:00 → 开盘分析 09:00(仅交易日)
