---
name: interest-tracker
description: 📬 自动兴趣追踪 — 每天从综合新闻源匹配你关心的领域/话题并推送。用户只说"关注XXX"，我配好关键词和优先级，每天09:00自动跑。
version: 1.2.0
tags: [interest, tracking, news, automation, 兴趣追踪, 新闻推送]
related_skills: [news-fetcher]
---

# 📬 兴趣追踪器

## 概述

每天上午 09:00（含周末节假日）从综合新闻 API 获取当日新闻，按用户指定的兴趣方向逐一关键词匹配，将匹配到的相关新闻推送给你。

**匹配逻辑：** 新闻标题包含任一关键词即视为匹配，按 score 排序取前 3 条。

---

## 使用方式

### 添加兴趣方向

直接跟我说：
> "关注机器人板块"
> "追踪一下低空经济"
> "关注光伏行业"

我会自动生成关键词列表，写入配置文件，次日 09:00 开始推送。

### 修改/删除

> "把售货机的关键词改成智能零售"
> "不用追踪商业航天了"

---

## 文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 主脚本 | `~/.hermes/scripts/interest_tracker.py` | 匹配新闻→推送 |
| 包装脚本 | `~/.hermes/scripts/interest_tracker.sh` | cron 包装（`python3 ~/.hermes/scripts/interest_tracker.py`） |
| 配置文件 | `~/.hermes/interest-tracker/interests.json` | 兴趣方向/关键词/优先级 |
| 每日日志 | `~/.hermes/interest-tracker/interests_YYYY-MM-DD.log` | 推送历史 |
| 新闻源参考 | `references/news-sources.md` | 已验证可用的新闻源清单、端点、格式 |

### 配置文件格式

```json
{
  "interests": [
    {
      "topic": "半导体/芯片",
      "keywords": ["半导体", "芯片", "中芯国际", "海光信息", "集成电路"],
      "priority": "high",
      "category": "📈 持仓",
      "note": "中芯国际、海光信息持仓"
    }
  ],
  "updated_at": "2026-05-16T01:11:50"
}
```

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `topic` | 兴趣方向名称 | 任意字符串 |
| `keywords` | 多个独立关键词，任一匹配即命中 | 字符串数组 |
| `priority` | 优先级 | `high` / `medium` / `low` |
| `category` | 分类标签（显示用） | 任意 Emoji 前缀字符串 |
| `note` | 备注 | 任意字符串 |

---

## 数据源

依赖 [news-fetcher](skill:news-fetcher) 模块，从 **4 个免费新闻源**同时抓取并去重：

| 源 | 条数 | 语言 | 类型 |
|:---|:----:|:----:|:-----|
| topurl.cn | ~20 | 中文 | 综合（含自媒体） |
| 搜狐新闻 channel 8 | ~20 | 中文 | 正规媒体（新华社/澎湃等） |
| Google News RSS | ~26 | 中文 | 多源聚合头条 |
| Actually Relevant RSS | ~50 | 英语 | AI 精选全球新闻 |

匹配逻辑：`any(kw.lower() in title.lower() for kw in keywords)`

---

## 定时任务

| 名称 | 时间 | 模式 | 说明 |
|:----|:----:|:----|:----|
| 📬 兴趣追踪 | `0 9 * * *` 每天09:00 | 脚本模式 | 含周末节假日，每日匹配推送 |

通过 `cronjob action=list` 查看。

---

## ⚠️ 兴趣识别原则（用户偏好）

**只收录用户主动要求关注的方向。** 不要通过"我发给你什么内容"来推断用户的兴趣。

用户明确纠正过：
- ❌ 我发送的新闻内容不代表用户的兴趣
- ✅ 用户主动说"关注XXX"才算
- ✅ 已有持仓/项目方向（如用户确认的）可收录

如果你不确定某个方向是不是用户兴趣，**不要自行添加**，直接问用户。

---

## 更新记录

### v1.2.0 (2026-05-16)
- 集成 4 源新闻（topurl/搜狐/Google/Relevant），由 `news-fetcher` 模块统一抓取
- 匹配源增加到 ~116条/次，中文66+英文50
- 底部新增来源统计行

### v1.1.0 (2026-05-16)
- 新增 `references/news-sources.md` — 已测试的新闻源清单（搜狐/Google/Actually Relevant）
- SKILL.md 数据源部分扩展为可配多源架构

### v1.0.0 (2026-05-16)
- 从 `stock-trading-agent` 技能独立拆分
- 数据目录从 `~/.hermes/stock-trading-logs/` 迁至 `~/.hermes/interest-tracker/`
