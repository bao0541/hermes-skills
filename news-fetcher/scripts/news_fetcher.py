#!/usr/bin/env python3
"""
📰 news_fetcher — 多源新闻抓取模块

可导入（import）使用，也可直接命令行运行测试。

用法:
    python3 news_fetcher.py                    # 全部源汇总
    python3 news_fetcher.py --source topurl    # 只抓 topurl
    python3 news_fetcher.py --source sohu      # 只抓搜狐
    python3 news_fetcher.py --source google    # 只抓 Google News
    python3 news_fetcher.py --source relevant  # 只抓 Actually Relevant
    python3 news_fetcher.py --source sinafin   # 只抓新浪财经
    python3 news_fetcher.py --source 36kr      # 只抓36氪

返回格式（每个 item）:
    {"title": str, "url": str, "source": str, "score": int}
"""

import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from typing import Optional

# ── 各源配置 ──────────────────────────────────

SOURCES = {
    "topurl": {
        "name": "topurl.cn",
        "url": "https://news.topurl.cn/api?ip=202.106.0.20&count=20",
        "parser": "_parse_topurl",
    },
    "sohu": {
        "name": "搜狐新闻",
        "url": "https://v2.sohu.com/public-api/feed?scene=CHANNEL&sceneId=8&page=1&size=20",
        "parser": "_parse_sohu",
    },
    "google": {
        "name": "Google News",
        "url": "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "parser": "_parse_google_rss",
    },
    "relevant": {
        "name": "Actually Relevant",
        "url": "https://actually-relevant-api.onrender.com/api/feed",
        "parser": "_parse_relevant_rss",
    },
    "sinafin": {
        "name": "新浪财经",
        "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=20&page=1",
        "parser": "_parse_sinafin",
    },
    "36kr": {
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "parser": "_parse_36kr_rss",
    },
}

ALL_SOURCES = list(SOURCES.keys())

# ── HTTP 请求工具 ─────────────────────────────

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _get_json(url: str, timeout: int = 15) -> Optional[dict | list]:
    """GET 请求并解析 JSON"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception:
        return None


def _get_text(url: str, timeout: int = 15) -> Optional[str]:
    """GET 请求并返回 UTF-8 文本"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        # 自动检测编码
        for enc in ["utf-8", "gbk", "gb2312"]:
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")
    except Exception:
        return None


# ── 各源解析器 ────────────────────────────────


def _parse_topurl(raw) -> list[dict]:
    """解析 topurl.cn JSON"""
    if not raw:
        return []
    news_list = raw.get("data", {}).get("newsList", [])
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": "topurl.cn",
            "score": item.get("score", 0),
        }
        for item in news_list
        if item.get("title")
    ]


def _parse_sohu(raw) -> list[dict]:
    """解析搜狐 channel 8 JSON"""
    if not isinstance(raw, list):
        return []
    results = []
    for item in raw:
        title = item.get("title", "") or item.get("content", "")
        if not title:
            continue
        article_id = item.get("id", "")
        url = item.get("url", "") or (
            f"https://www.sohu.com/a/{article_id}" if article_id else ""
        )
        results.append({
            "title": title,
            "url": url,
            "source": "搜狐新闻",
            "score": 10,
        })
    return results


def _parse_google_rss(raw_text: str) -> list[dict]:
    """解析 Google News RSS"""
    if not raw_text:
        return []
    try:
        root = ET.fromstring(raw_text.encode("utf-8"))
    except Exception:
        return []
    items = root.findall(".//item")
    results = []
    seen = set()
    for item in items:
        title_el = item.find("title")
        link_el = item.find("link")
        title = title_el.text if title_el is not None and title_el.text else ""
        link = link_el.text if link_el is not None and link_el.text else ""
        if not title or title in seen:
            continue
        seen.add(title)
        results.append({
            "title": title,
            "url": link,
            "source": "Google News",
            "score": 8,
        })
    return results


def _parse_relevant_rss(raw_text: str) -> list[dict]:
    """解析 Actually Relevant RSS"""
    if not raw_text:
        return []
    try:
        root = ET.fromstring(raw_text.encode("utf-8"))
    except Exception:
        return []
    items = root.findall(".//item")
    results = []
    seen = set()
    for item in items:
        title_el = item.find("title")
        link_el = item.find("link")
        cat_el = item.find("category")
        title = title_el.text if title_el is not None and title_el.text else ""
        link = link_el.text if link_el is not None and link_el.text else ""
        cat = cat_el.text if cat_el is not None and cat_el.text else ""
        if not title or title in seen:
            continue
        seen.add(title)
        results.append({
            "title": f"[{cat}] {title}",
            "url": link,
            "source": "Act. Relevant",
            "score": 6,
        })
    return results


def _parse_sinafin(raw) -> list[dict]:
    """解析新浪财经滚动新闻 JSON"""
    if not raw:
        return []
    items = raw.get("result", {}).get("data", [])
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": "新浪财经",
            "score": 8,
        }
        for item in items
        if item.get("title")
    ]


def _parse_36kr_rss(raw_text: str) -> list[dict]:
    """解析 36氪 RSS"""
    if not raw_text:
        return []
    try:
        root = ET.fromstring(raw_text.encode("utf-8"))
    except Exception:
        return []
    items = root.findall(".//item")
    results = []
    seen = set()
    for item in items:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        title = title_el.text if title_el is not None and title_el.text else ""
        link = link_el.text if link_el is not None and link_el.text else ""
        if not title or title in seen:
            continue
        seen.add(title)
        results.append({
            "title": title,
            "url": link,
            "source": "36氪",
            "score": 7,
        })
    return results


# ── 公共 API ──────────────────────────────────


def fetch(source: str) -> list[dict]:
    """抓取单个新闻源，返回 item 列表"""
    cfg = SOURCES.get(source)
    if not cfg:
        raise ValueError(f"未知新闻源: {source}，可选: {', '.join(ALL_SOURCES)}")

    parser_name = cfg["parser"]
    parser = globals().get(parser_name)
    if not parser:
        return []

    if source in ("google", "relevant", "36kr"):
        raw = _get_text(cfg["url"])
    else:
        raw = _get_json(cfg["url"])

    return parser(raw) if raw is not None else []


def fetch_all(sources: Optional[list[str]] = None) -> dict[str, list[dict]]:
    """抓取多个新闻源，返回 {source_name: [items]}"""
    if sources is None:
        sources = ALL_SOURCES

    result = {}
    for src in sources:
        try:
            items = fetch(src)
            result[src] = items
        except Exception:
            result[src] = []
    return result


def fetch_all_flat(sources: Optional[list[str]] = None) -> list[dict]:
    """抓取多个新闻源，返回合并平铺的 list（去重 by title）"""
    grouped = fetch_all(sources)
    all_items = []
    seen_titles = set()
    for src in ALL_SOURCES if sources is None else sources:
        for item in grouped.get(src, []):
            t = item["title"].strip()
            if t and t not in seen_titles:
                seen_titles.add(t)
                all_items.append(item)
    return all_items


# ── CLI ───────────────────────────────────────


def main():
    import sys

    sources = ALL_SOURCES
    if len(sys.argv) > 1 and sys.argv[1].startswith("--source="):
        src = sys.argv[1].split("=", 1)[1]
        if src in SOURCES:
            sources = [src]
        else:
            print(f"未知源: {src}，可选: {', '.join(ALL_SOURCES)}")
            sys.exit(1)

    results = fetch_all(sources)
    total = sum(len(v) for v in results.values())
    print(f"📰 共 {total} 条新闻（{', '.join(f'{k}={len(v)}' for k, v in results.items())}）")
    print("=" * 62)

    for src in sources:
        items = results.get(src, [])
        print(f"\n── {SOURCES[src]['name']} ({len(items)}条) ──")
        for item in items[:5]:
            print(f"  {item['title'][:60]}")
            if item["url"]:
                print(f"  → {item['url'][:70]}")
        if len(items) > 5:
            print(f"  ... 还有 {len(items)-5} 条")


if __name__ == "__main__":
    main()
