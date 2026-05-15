#!/usr/bin/env python3
"""
📬 兴趣追踪器 — 从多源新闻匹配你关心的方向
每天由 cron 在 09:00 运行。
"""

import json, os, re
from datetime import datetime, date
from pathlib import Path

# 导入新闻抓取模块
import sys
sys.path.insert(0, os.path.expanduser("~/.hermes/scripts"))
from news_fetcher import fetch_all_flat, ALL_SOURCES

LOG_DIR = Path(os.path.expanduser("~/.hermes/interest-tracker"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
INTERESTS_FILE = LOG_DIR / "interests.json"

DEFAULT_INTERESTS = [
    {"topic": "半导体/芯片", "keywords": ["半导体","芯片","中芯国际","海光信息","集成电路"],
     "priority": "high", "category": "📈 持仓", "note": "中芯国际、海光信息持仓"},
    {"topic": "AI/算力", "keywords": ["算力","AI","中科曙光","人工智能","大模型"],
     "priority": "high", "category": "📈 持仓", "note": "中科曙光持仓"},
    {"topic": "金融/券商", "keywords": ["券商","A股","东方财富","股市","牛市"],
     "priority": "high", "category": "📈 持仓", "note": "东方财富持仓"},
    {"topic": "新能源", "keywords": ["宁德时代","新能源","电池","电动汽车"],
     "priority": "medium", "category": "📈 持仓", "note": "宁德时代持仓"},
    {"topic": "商业航天", "keywords": ["商业航天","火箭","发射","卫星"],
     "priority": "low", "category": "👀 关注", "note": "蓝箭航天IPO"},
    {"topic": "售货机", "keywords": ["售货机","无人零售","智能柜","自动贩卖"],
     "priority": "medium", "category": "🏪 项目", "note": "山西售货机项目"},
]


def load_interests():
    if INTERESTS_FILE.exists():
        with open(INTERESTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"interests": DEFAULT_INTERESTS, "updated_at": datetime.now().isoformat()}


def match_interest(title, keywords):
    t = title.lower()
    for kw in keywords:
        if kw.lower() in t:
            return True
    return False


def run_tracker():
    data = load_interests()
    interests = data["interests"]

    # 从 news_fetcher 获取全部新闻（去重）
    news_list = fetch_all_flat()

    log = []
    log.append(f"{'='*62}")
    log.append(f"📬 兴趣追踪 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.append(f"{'='*62}")
    log.append("")

    has_any = False
    priority_mark = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    for interest in interests:
        mark = priority_mark.get(interest["priority"], "⚪")
        log.append(f"{mark} {interest['category']} {interest['topic']}")
        log.append(f"   {interest['note']}")

        matched = []
        for item in news_list:
            title = item.get("title", "")
            if match_interest(title, interest["keywords"]):
                matched.append(item)

        # 按 score 排序取前 3
        matched.sort(key=lambda x: x.get("score", 0), reverse=True)
        top = matched[:3]

        if top:
            has_any = True
            for i, item in enumerate(top, 1):
                t = item["title"]
                u = item.get("url", "")
                src = item.get("source", "")
                link = f"[{t}]({u})" if u else t
                log.append(f"   {i}. {link} ({src})")
        else:
            log.append(f"   暂无匹配新闻")
        log.append("")

    # 底部显示数据来源统计
    source_counts = {}
    for item in news_list:
        src = item.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    log.append(f"{'='*62}")
    log.append(f"📡 今日新闻来源: {' | '.join(f'{k} {v}条' for k, v in source_counts.items())}")
    log.append(f"{'='*62}")
    log.append(f"💡 想新增/修改追踪方向？直接跟我说")
    log.append(f"{'='*62}")

    return "\n".join(log)


def main():
    if not INTERESTS_FILE.exists():
        with open(INTERESTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"interests": DEFAULT_INTERESTS, "updated_at": datetime.now().isoformat()},
                      f, ensure_ascii=False, indent=2)

    log = run_tracker()
    log_file = LOG_DIR / f"interests_{date.today().isoformat()}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(log)
    print(log)


if __name__ == "__main__":
    main()
