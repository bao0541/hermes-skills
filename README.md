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
**数据源：** news.topurl.cn API（同每日新闻简报）

[查看详情 →](interest-tracker/SKILL.md)

---

## 安装

```bash
# 将所有技能复制到 Hermes Agent skills 目录
cp -r stock-trading-agent ~/.hermes/skills/software-development/
cp -r interest-tracker ~/.hermes/skills/

# 复制脚本到 scripts 目录
cp stock-trading-agent/scripts/*.py ~/.hermes/scripts/
cp interest-tracker/scripts/*.py ~/.hermes/scripts/
```

## 关联

- `interest-tracker` 是 `stock-trading-agent` 的关联技能（`related_skills`）
- 两者共用每日新闻数据源（news.topurl.cn）
- 定时任务时间错开：新闻简报 08:30 → 兴趣追踪 09:00 → 开盘分析 09:00(仅交易日)
