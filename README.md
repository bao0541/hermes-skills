# hermes-skills

Hermes Agent 自定义技能集，用于 A 股量化交易分析。

## 技能列表

### stock-trading-agent
自动炒股Agent — 两阶段架构（分析计划 + 盘执行器），新闻驱动 + 技术分析，自主买卖决策。

- **评分系统**：新闻面评分(40%) + 技术面评分(60%)
- **实盘规则**：T+1锁定、涨跌幅限制、节假日日历
- **运行时段**：09:00开盘前 / 11:35午盘 / 15:05收盘复盘 + 盘中每15分钟执行器
- **数据源**：腾讯行情API（qt.gtimg.cn）

### 安装

```bash
# 复制技能到 Hermes Agent skills 目录
cp -r stock-trading-agent ~/.hermes/skills/software-development/

# 复制脚本到 scripts 目录
cp stock-trading-agent/scripts/*.py ~/.hermes/scripts/
```
