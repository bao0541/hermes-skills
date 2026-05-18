#!/usr/bin/env python3
"""
🚨 A股突发事件监控 — 被动推送 + Agent响应
盘中每15分钟运行，监控三类事件：

1. 个股急跌 > 5%（持仓股或候选股）
2. 大盘暴跌 > 3%（上证、深证、创业板）
3. 板块利空（板块指数单日跌幅 > 4%）

设计原则：
  - 纯Python检查（零LLM），只有事件触发时才通知
  - 通知包含事件详情 + 建议操作（由AI agent处理）
  - 同一天同一事件不重复推送
"""
import json, os, sys, re, urllib.request
from datetime import datetime, date
from pathlib import Path

SCRIPTS_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/scripts"))
DATA_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/data"))
LOG_DIR = Path(os.path.expanduser("~/.hermes/stock-trading-logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
import importlib
spec = importlib.util.spec_from_file_location("stock_trader", SCRIPTS_DIR / "stock_trader.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

# ── 配置 ──────────────────────────────────────────────

STOCK_DROP_THRESHOLD = -5.0    # 个股急跌阈值 %
MARKET_CRASH_THRESHOLD = -3.0  # 大盘暴跌阈值 %
SECTOR_DROP_THRESHOLD = -4.0   # 板块暴跌阈值 %

# 大盘指数代码
MARKET_INDICES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创板指",
}

# 重点板块指数代码
SECTOR_INDICES = {
    "sh000016": "上证50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sz399437": "AI芯片",
    "sz399678": "半导体",
    "sz399395": "新能源",
}

# ── 事件重复检查 ──────────────────────────────────────

EVENT_LOG = LOG_DIR / "event_log.json"

def load_event_log():
    if EVENT_LOG.exists():
        with open(EVENT_LOG) as f:
            return json.load(f)
    return {"events": []}

def save_event_log(data):
    with open(EVENT_LOG, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_event_duplicate(event_type, code, today):
    """同一天同类型同标的已推送过就不重复发"""
    log = load_event_log()
    for e in log["events"]:
        if e["type"] == event_type and e["code"] == code and e["date"] == today:
            return True
    return False

def record_event(event_type, code, name, detail):
    """记录事件"""
    today = date.today().isoformat()
    log = load_event_log()
    log["events"].append({
        "type": event_type,
        "code": code,
        "name": name,
        "detail": detail,
        "date": today,
        "time": datetime.now().strftime("%H:%M:%S"),
    })
    save_event_log(log)


# ── 数据获取 ──────────────────────────────────────────

def get_quote(symbol):
    """获取单只股票/指数的实时行情"""
    try:
        req = urllib.request.Request(
            f"https://qt.gtimg.cn/q={symbol}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")
        fields = raw.split("~")
        if len(fields) < 33:
            return None
        return {
            "name": fields[1],
            "price": safe_float(fields[3]),
            "change_pct": safe_float(fields[32]) if len(fields) > 32 else 0,
        }
    except:
        return None

def safe_float(v, default=0):
    try:
        return float(v)
    except:
        return default


# ── 监控检查 ──────────────────────────────────────────

def check_events():
    """执行所有事件检查，返回事件列表"""
    now = datetime.now()
    today = date.today().isoformat()
    events = []
    
    # 1. 大盘检查
    for code, name in MARKET_INDICES.items():
        data = get_quote(code)
        if data and data["change_pct"] < MARKET_CRASH_THRESHOLD:
            if not is_event_duplicate("market_crash", code, today):
                events.append({
                    "type": "market_crash",
                    "level": "🔴",
                    "code": code,
                    "name": name,
                    "change_pct": data["change_pct"],
                    "price": data["price"],
                    "detail": f"{name} 暴跌 {data['change_pct']:+.2f}%（阈值{MARKET_CRASH_THRESHOLD}%）",
                })
                record_event("market_crash", code, name,
                            f"暴跌 {data['change_pct']:+.2f}%")
    
    # 2. 板块检查
    for code, name in SECTOR_INDICES.items():
        data = get_quote(code)
        if data and data["change_pct"] < SECTOR_DROP_THRESHOLD:
            if not is_event_duplicate("sector_crash", code, today):
                events.append({
                    "type": "sector_crash",
                    "level": "🟠",
                    "code": code,
                    "name": name,
                    "change_pct": data["change_pct"],
                    "price": data["price"],
                    "detail": f"{name} 板块暴跌 {data['change_pct']:+.2f}%（阈值{SECTOR_DROP_THRESHOLD}%）",
                })
                record_event("sector_crash", code, name,
                            f"板块暴跌 {data['change_pct']:+.2f}%")
    
    # 3. 持仓股急跌检查
    acc = st.get_account()
    positions = acc.get("positions", {})
    for code, pos in positions.items():
        # 构建腾讯格式代码
        c = code.lower().replace("sz", "").replace("sh", "")
        if c.startswith("6"):
            prefix = "sh"
        else:
            prefix = "sz"
        symbol = f"{prefix}{c}"
        
        data = get_quote(symbol)
        if data and data["change_pct"] < STOCK_DROP_THRESHOLD:
            if not is_event_duplicate("stock_plunge", code, today):
                events.append({
                    "type": "stock_plunge",
                    "level": "🟠",
                    "code": code,
                    "name": pos.get("name", data["name"]),
                    "change_pct": data["change_pct"],
                    "price": data["price"],
                    "shares": pos["shares"],
                    "cost": pos["avg_cost"],
                    "detail": (f"持仓 {pos.get('name', code)} ({code}) 急跌 {data['change_pct']:+.2f}%"
                               f" | 持仓 {pos['shares']}股 @ {pos['avg_cost']:.2f}"
                               f" | 现价 {data['price']:.2f}"),
                })
                record_event("stock_plunge", code, pos.get("name", code),
                            f"急跌 {data['change_pct']:+.2f}%")
    
    return events


# ── 输出 ──────────────────────────────────────────────

def format_events(events):
    if not events:
        return ""  # 无事件，静默
    
    lines = []
    lines.append(f"{'='*62}")
    lines.append(f"🚨 突发事件报告 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"{'='*62}")
    
    for e in events:
        lines.append(f"\n{e['level']} [{e['type']}] {e['detail']}")
        if e['type'] == 'stock_plunge':
            lines.append(f"   建议：检查是否需要触发止损或减仓")
        elif e['type'] == 'market_crash':
            lines.append(f"   建议：市场系统性风险，关注持仓风险，暂不新开仓")
        elif e['type'] == 'sector_crash':
            lines.append(f"   建议：检查该板块持仓，考虑减仓")
    
    lines.append(f"\n{'='*62}")
    lines.append(f"⚠️ 以上事件需AI agent处理决策")
    lines.append(f"{'='*62}")
    
    return "\n".join(lines)


def main():
    events = check_events()
    report = format_events(events)
    
    if report:
        print(report)  # 有事件时print，cron自动推送飞书
    # 无事件时静默（不print → cron静默模式）
    
    # 始终写日志
    if events:
        log_file = LOG_DIR / f"event_watcher_{date.today().isoformat()}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(report + "\n\n")


if __name__ == "__main__":
    main()
