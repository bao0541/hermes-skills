---
name: news-fetcher
description: 📰 多源新闻抓取模块 — 从 topurl.cn、搜狐新闻、Google News、Actually Relevant、新浪财经、36氪 六个免费源抓取中文+英文新闻。可导入作为 Python 模块使用，也支持命令行。
version: 1.2.0
tags: [news, fetching, rss, api, scrapy, 新闻抓取, 多源聚合]
---

# 📰 News Fetcher

## 概述

统一的多源新闻抓取模块，从 **6 个免费新闻源**同时抓取并去重。可作 Python 模块导入，也支持命令行直接运行。

技能设计原则：**源发现 → 测试 → 记录 → 编码集成 → 文档更新**。`references/source-discovery.md` 记录所有已验证/不可用/待测的源。

## 已集成的新闻源（6 个）

| 源 | 条数/次 | 语言 | 类型 | 是否需要 Key |
|:---|:-------:|:----:|:-----|:-----------:|
| **topurl.cn** | ~20 | 中文 | 综合（含自媒体） | ❌ 免费 |
| **搜狐新闻** | ~20 | 中文 | 正规媒体（新华社/澎湃等） | ❌ 免费 |
| **Google News RSS** | ~26 | 中文 | 多源聚合头条 | ❌ 免费 |
| **Actually Relevant RSS** | ~50 | 英语 | AI 精选全球新闻 | ❌ 免费 |
| **新浪财经** | ~20 | 中文 | 财经新闻 | ❌ 免费 |
| **36氪** | ~30 | 中文 | 科技/商业 | ❌ 免费 |
| **合计** | **~166条/次** | 中文136+英文50 | | |

## 已验证不可用的源

以下源已测试但无法从首尔服务器直接抓取：

| 源 | 状态 | 原因 |
|:---|:----:|:-----|
| 网易新闻 | ❌ 403 | RSS/API 均被服务器拒绝 |
| 今日头条 | ❌ Error | API 返回 error，需签名验证 |
| 雪球 | ❌ WAF | 阿里云WAF阻止 |
| 百度热搜 | ❌ 需渲染 | 纯前端页面，curl 拿不到数据 |
| 微信公众号 | ❌ 需登录 | 需要Cookie/Token |

详见 `references/source-discovery.md`。

## 文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 主模块 | `~/.hermes/scripts/news_fetcher.py` | 可导入/可执行 |
| 源配置参考 | `references/news-sources.md` | 各源端点、格式说明 |
| 源发现记录 | `references/source-discovery.md` | 源测试结果、编码注意事项 |

## Python 用法

```python
from news_fetcher import fetch_all, fetch, fetch_all_flat

# 1. 全部源
results = fetch_all()
# → {"topurl": [...], "sohu": [...], "google": [...], "relevant": [...], "sinafin": [...], "36kr": [...]}

# 2. 平铺合并（去重）
all_news = fetch_all_flat()
# → [{"title": "...", "url": "...", "source": "...", "score": N}, ...]

# 3. 只抓某个源
sohu_news = fetch("sohu")
topurl_news = fetch("topurl")
google_news = fetch("google")
relevant_news = fetch("relevant")
sinafin_news = fetch("sinafin")
kr36_news = fetch("36kr")
```

### 返回格式

每个 item 的结构：

```python
{
    "title": "新闻标题",
    "url": "https://...",
    "source": "搜狐新闻",       # 来源名称
    "score": 10,                # 热度/优先级（用于排序）
}
```

### 只抓指定源

```python
results = fetch_all(sources=["topurl", "sohu"])
flat = fetch_all_flat(sources=["google", "relevant"])
```

## CLI 用法

```bash
# 全部源汇总
python3 ~/.hermes/scripts/news_fetcher.py

# 只抓某个源
python3 ~/.hermes/scripts/news_fetcher.py --source=sohu
python3 ~/.hermes/scripts/news_fetcher.py --source=topurl
python3 ~/.hermes/scripts/news_fetcher.py --source=sinafin
python3 ~/.hermes/scripts/news_fetcher.py --source=36kr
```

## 导入方式

脚本在 `~/.hermes/scripts/` 下，推荐从该目录直接导入：

```python
import sys
sys.path.insert(0, "/home/ubuntu/.hermes/scripts")
from news_fetcher import fetch_all
```

如果是其他也在 `~/.hermes/scripts/` 下的脚本，直接 `from news_fetcher import fetch_all` 即可（Python 自动解析同目录）。

## 定时任务

不需要独立定时任务 — 由消费者（如 `interest-tracker`）在运行时调用。

## 依赖

- Python 标准库（urllib, xml.etree, json）
- 无第三方依赖

## 更新记录

### v1.2.0 (2026-05-16)
- 新增 2 源：新浪财经(+20条)、36氪(+30条)
- 总池从 ~116 条增至 ~166 条/次（中文136+英文50）
- 源列表从 4 个更新为 6 个

### v1.1.0 (2026-05-16)
- 文档化新浪财经 API 和 36氪 RSS 为新验证待集成的源
- 新增 `references/source-discovery.md` — 源测试结果、编码注意事项、待测源清单
- 确立技能设计原则：发现→测试→记录→（确认后）编码

### v1.0.0
- 集成 4 个免费新闻源：topurl.cn / 搜狐 / Google News / Actually Relevant
- 支持按源过滤、去重平铺
- CLI 调试模式
