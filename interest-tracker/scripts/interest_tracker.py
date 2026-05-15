#!/usr/bin/env python3
"""
📬 兴趣追踪器 - 每天从综合新闻源匹配你关心的方向
"""
import json, os, re, urllib.request, urllib.parse
from datetime import datetime, date
from pathlib import Path

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

# 综合新闻API（同每日简报用的数据源）
API_URL = "https://news.topurl.cn/api?ip=202.106.0.20&count=20"


def load_interests():
    if INTERESTS_FILE.exists():
        with open(INTERESTS_FILE) as f:
            return json.load(f)
    return {"interests": DEFAULT_INTERESTS, "updated_at": datetime.now().isoformat()}


def fetch_all_news():
    """获取今日全部新闻"""
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        return data.get("data", {}).get("newsList", [])
    except Exception:
        return []


def match_interest(title, keywords):
    """判断标题是否匹配兴趣关键词"""
    t = title.lower()
    for kw in keywords:
        if kw.lower() in t:
            return True
    return False


def run_tracker():
    data = load_interests()
    interests = data["interests"]
    
    # 获取新闻
    news_list = fetch_all_news()
    
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
        
        # 从全部新闻中匹配
        matched = []
        for item in news_list:
            title = item.get("title", "")
            url = item.get("url", "")
            score = item.get("score", 0)
            if match_interest(title, interest["keywords"]):
                matched.append({"title": title, "url": url, "score": score})
        
        # 按分数排序取前3
        matched.sort(key=lambda x: x["score"], reverse=True)
        top = matched[:3]
        
        if top:
            has_any = True
            for i, item in enumerate(top, 1):
                t = item["title"]
                u = item["url"]
                link = f"[{t}]({u})" if u else t
                log.append(f"   {i}. {link}")
        else:
            log.append(f"   暂无匹配新闻")
        log.append("")
    
    log.append(f"{'='*62}")
    log.append(f"💡 想新增/修改追踪方向？直接跟我说")
    log.append(f"{'='*62}")
    
    return "\n".join(log)


def main():
    if not INTERESTS_FILE.exists():
        with open(INTERESTS_FILE, "w") as f:
            json.dump({"interests": DEFAULT_INTERESTS, "updated_at": datetime.now().isoformat()},
                      f, ensure_ascii=False, indent=2)
    
    log = run_tracker()
    log_file = LOG_DIR / f"interests_{date.today().isoformat()}.log"
    with open(log_file, "w") as f:
        f.write(log)
    print(log)


if __name__ == "__main__":
    main()
