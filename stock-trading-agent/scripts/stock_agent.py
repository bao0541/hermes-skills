#!/usr/bin/env python3
"""
📈 自动炒股Agent - 新闻驱动 + 技术分析 + 订单计划
交易日三个时段运行：
  - 09:00 开盘前: 分析 → 生成订单计划（待执行）
  - 11:35 午盘:   复盘 → 生成下午订单计划（待执行）
  - 15:05 收盘:   复盘总结，不生成订单
"""
import json, os, sys, re, hashlib
from datetime import datetime, date
from pathlib import Path

SCRIPTS_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/scripts"))
DATA_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/data"))
LOG_DIR = Path(os.path.expanduser("~/.hermes/stock-trading-logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_DIR = LOG_DIR / "orders"
ORDERS_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DATA_FILE = DATA_DIR / "agent_t1_tracker.json"

sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(str(SCRIPTS_DIR))

import importlib
spec = importlib.util.spec_from_file_location("stock_trader", SCRIPTS_DIR / "stock_trader.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

# ── 交易日历 ──
from market_calendar import is_trading_day


# ── 订单队列管理（按日期分文件） ──
def _orders_path(d=None):
    """返回对应日期的订单文件路径"""
    if d is None:
        d = date.today()
    return ORDERS_DIR / f"orders_{d.isoformat()}.json"

def load_orders(d=None):
    path = _orders_path(d)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"orders": []}

def save_orders(data, d=None):
    path = _orders_path(d)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_order(code, name, action, shares, reason, session, price_ref):
    today = date.today()
    orders = load_orders(today)
    oid = hashlib.md5(f"{today}{code}{action}{session}{datetime.now().timestamp()}".encode()).hexdigest()[:8]
    orders["orders"].append({
        "id": oid,
        "date": today.isoformat(),
        "created_session": session,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "code": code, "name": name,
        "action": action, "shares": shares,
        "reason": reason, "price_ref": round(price_ref, 2),
        "status": "pending",
    })
    save_orders(orders, today)
    return oid

def get_pending_orders(session=None):
    today = date.today()
    orders = load_orders(today)
    today_str = today.isoformat()
    pending = []
    for o in orders["orders"]:
        if o["status"] == "pending" and o["date"] == today_str:
            if session is None or o["created_session"] == session:
                pending.append(o)
    return pending

def cancel_order(oid, reason="超时取消"):
    today = date.today()
    orders = load_orders(today)
    for o in orders["orders"]:
        if o["id"] == oid:
            o["status"] = "cancelled"
            o["cancel_reason"] = reason
            break
    save_orders(orders, today)

def mark_executed(oid, price):
    today = date.today()
    orders = load_orders(today)
    for o in orders["orders"]:
        if o["id"] == oid:
            o["status"] = "executed"
            o["executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            o["executed_price"] = round(price, 2)
            break
    save_orders(orders, today)


# ── T+1 追踪 ──
def load_t1_tracker():
    if AGENT_DATA_FILE.exists():
        with open(AGENT_DATA_FILE) as f:
            return json.load(f)
    return {}

def save_t1_tracker(data):
    with open(AGENT_DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_today_locked_shares(code, tracker):
    today = date.today().isoformat()
    locked = 0
    for buy_date, shares in tracker.get(code, []):
        if buy_date == today:
            locked += shares
    return locked

def record_t1_buy(code, shares, tracker):
    today = date.today().isoformat()
    if code not in tracker:
        tracker[code] = []
    tracker[code].append([today, shares])
    save_t1_tracker(tracker)

def cleanup_t1_tracker(tracker, positions):
    cleaned = {}
    for code, records in tracker.items():
        if code in positions:
            today = date.today().isoformat()
            cleaned[code] = [[d, s] for d, s in records if d == today]
    save_t1_tracker(cleaned)


# ── 候选股票池 ──
CANDIDATES = {
    "SH688981": {"name": "中芯国际", "sector": "半导体/制造", "priority": "hold"},
    "SZ300059": {"name": "东方财富", "sector": "券商/金融", "priority": "hold"},
    "SZ001309": {"name": "德明利", "sector": "存储芯片", "priority": "hold"},
    "SH688041": {"name": "海光信息", "sector": "GPU/AI芯片", "priority": "high"},
    "SH603019": {"name": "中科曙光", "sector": "AI算力基础设施", "priority": "high"},
    "SZ002371": {"name": "北方华创", "sector": "半导体设备", "priority": "medium"},
    "SH603501": {"name": "韦尔股份", "sector": "CIS芯片", "priority": "medium"},
    "SZ000938": {"name": "紫光股份", "sector": "ICT基础设施", "priority": "medium"},
    "SZ300750": {"name": "宁德时代", "sector": "新能源电池", "priority": "watch"},
}

# ── 新闻面评分 ──
def get_news_score(code):
    scores = {
        "SH688981": (5, "Q1营收+8%，406亿收购中芯北方过会；Q2指引环比+14~16%；但MATCH法案被列入管制设施"),
        "SZ300059": (7, "Q1营收+44%/净利+37.67%超预期；经营现金流+765%；A股慢牛行情利好券商"),
        "SZ001309": (4, "存储芯片超级周期：SK海力士+12.5%，DRAM涨幅预期250~280%"),
        "SH688041": (8, "Q1营收+63~76%高速增长；DCU深算三号出货强劲；AI芯片国产份额破55%；减持30亿短期压制"),
        "SH603019": (7, "Q1营收+23.7%/扣非+57.77%高增；曙光云入选数字经济实验室；国产超节点量产元年"),
        "SZ002371": (6, "Q1营收+25.8%新高；十五五'超常规'政策支持；但RSI高位需等待回调"),
        "SH603501": (5, "Q1净利+55%/毛利率+3.1pct改善；汽车CIS放量；业绩反转确认"),
        "SZ000938": (8, "Q1净利+126%全市场最强；Token经济驱动AI需求暴增；但技术面MACD死叉"),
        "SZ300750": (8, "Q1净利+48.5%超预期；超级科技日5款新品；市值破2万亿；但技术面在回调中"),
    }
    if code in scores:
        return {"score": scores[code][0], "reasons": scores[code][1]}
    return {"score": 0, "reasons": "暂无新闻数据"}

def score_technicals(analysis):
    score = 0; reasons = []
    if not analysis or isinstance(analysis, str):
        return {"score": -5, "reasons": "无法获取技术分析"}
    t = analysis.get("trend_signals", [])
    signals_text = [s.lower() for s in t]
    ma_count = sum(1 for s in signals_text if "多头" in s)
    bear_count = sum(1 for s in signals_text if "空头" in s)
    score += (ma_count - bear_count) * 1.5
    if ma_count >= 3: reasons.append("均线多头排列 +3")
    elif bear_count >= 2: reasons.append("均线空头排列 -3")
    rsi_text = analysis.get("rsi", "").lower()
    rsi_match = re.search(r'rsi=(\d+\.?\d*)', rsi_text)
    if rsi_match:
        rsi_val = float(rsi_match.group(1))
        if 30 <= rsi_val <= 40: score += 2; reasons.append(f"RSI={rsi_val:.0f}偏低+2")
        elif 40 < rsi_val <= 55: score += 1; reasons.append(f"RSI={rsi_val:.0f}中性+1")
        elif 55 < rsi_val <= 70: score += 0.5; reasons.append(f"RSI={rsi_val:.0f}偏强+0.5")
        elif rsi_val > 75: score -= 2; reasons.append(f"RSI={rsi_val:.0f}偏高-2")
        elif rsi_val < 25: score += 3; reasons.append(f"RSI={rsi_val:.0f}超卖+3")
    macd_text = analysis.get("macd", "").lower()
    if "金叉" in macd_text: score += 3; reasons.append("MACD金叉+3")
    elif "死叉" in macd_text: score -= 3; reasons.append("MACD死叉-3")
    elif "多头" in macd_text: score += 1; reasons.append("MACD多头+1")
    elif "空头" in macd_text: score -= 1; reasons.append("MACD空头-1")
    boll = analysis.get("boll", "").lower()
    if "突破上轨" in boll: score -= 1; reasons.append("布林上轨-1")
    elif "跌破下轨" in boll: score += 2; reasons.append("布林下轨+2")
    return {"score": round(score, 1), "reasons": "; ".join(reasons)}

def calc_weighted_score(news, tech):
    ns = news["score"]; ts = tech["score"]
    return {"combined": round(ns*0.4+ts*0.6, 1),
            "news_score": ns, "tech_score": ts,
            "news_reason": news["reasons"], "tech_reason": tech["reasons"]}

def decide_action(code, name, score, analysis, positions, session, t1_tracker):
    """决策引擎：生成订单计划（不下单成交）"""
    decision = {"code": code, "name": name, "action": "hold",
                "reason": "", "shares": 0, "price": 0}

    acc = st.get_account()
    cash = acc["cash"]
    pos_info = positions.get(code, None)
    price, _, _ = st.get_realtime_price(code)
    if price is None or price == 0:
        price = analysis.get("latest", {}).get("close", 0)
    decision["price"] = price

    combined = score["combined"]
    tech_score = score["tech_score"]

    # ── 收盘复盘不生成订单 ──
    if session == "close":
        if pos_info:
            profit_pct = (price / pos_info["avg_cost"] - 1) * 100
            decision["reason"] = f"收盘复盘。综合分{combined}，当日盈亏{profit_pct:+.1f}%"
        else:
            decision["reason"] = f"收盘复盘。综合分{combined}"
        return decision

    # ── 卖出判断（生成计划订单） ──
    if pos_info:
        shares_held = pos_info["shares"]
        avg_cost = pos_info["avg_cost"]
        profit_pct = (price / avg_cost - 1) * 100
        locked = get_today_locked_shares(code, t1_tracker)
        sellable = shares_held - locked
        if sellable <= 0:
            decision["action"] = "hold"
            decision["reason"] = f"今日买入股T+1锁定中（{locked}股），不可卖"
            return decision

        if profit_pct <= -8:
            decision["action"] = "sell_all"; decision["shares"] = sellable
            decision["reason"] = f"止损计划：亏损{profit_pct:.1f}%，卖出{sellable}股"
        elif profit_pct >= 20 and tech_score <= -1:
            sell_qty = min(sellable, shares_held // 2)
            decision["action"] = "sell_half"; decision["shares"] = sell_qty
            decision["reason"] = f"止盈计划：盈利{profit_pct:.1f}%+技术转弱，减半"
        elif combined <= -4:
            decision["action"] = "sell_all"; decision["shares"] = sellable
            decision["reason"] = f"强卖出信号：综合分{combined}"
        else:
            decision["action"] = "hold"
            decision["reason"] = f"持有观望。综合分{combined}，盈亏{profit_pct:+.1f}%"

    # ── 买入判断（生成计划订单） ──
    else:
        if combined >= 4 and cash >= 50000:
            buy_amount = min(cash * 0.2, 200000)
            buy_shares = int(buy_amount / price / 100) * 100
            if buy_shares >= 100:
                decision["action"] = "buy"; decision["shares"] = buy_shares
                decision["reason"] = f"买入计划：综合分{combined}(新闻{score['news_score']}+技术{score['tech_score']})"
            else:
                decision["action"] = "hold"
                decision["reason"] = f"综合分{combined}，金额不足1手（需{price*100:.0f}元）"
        elif combined >= 2 and cash >= 30000:
            buy_amount = min(cash * 0.1, 100000)
            buy_shares = int(buy_amount / price / 100) * 100
            if buy_shares >= 100:
                decision["action"] = "buy_light"; decision["shares"] = buy_shares
                decision["reason"] = f"轻仓计划：综合分{combined}"
            else:
                decision["action"] = "hold"
                decision["reason"] = f"综合分{combined}，金额不足1手"
        else:
            decision["action"] = "hold"
            decision["reason"] = f"综合分{combined}，未达买入阈值(>=4)"

    return decision


def run_daily_analysis(session="close"):
    """主流程：分析→生成订单计划（不开盘时段不下单）"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")

    log = []
    
    # ── 休市日跳过 ──
    if session != "close" and not is_trading_day():
        msg = (f"{'='*62}\n"
               f"📅 {date_str}\n"
               f"   今日非交易日（节假日/周末），跳过股票分析任务\n"
               f"{'='*62}")
        print(msg)
        (LOG_DIR / f"skip_{date.today().isoformat()}_{session}.log").write_text(msg)
        return msg

    log.append(f"{'='*62}")
    log.append(f"📈 自动炒股Agent · {date_str}")
    labels = {"pre-market": "开盘前分析 (09:00) → 生成订单，等待09:30开盘执行",
              "midday": "午盘复盘 (11:35) → 生成订单，等待13:00开盘执行",
              "close": "收盘复盘 (15:05) — 仅分析不交易"}
    log.append(f"   📋 {labels.get(session, session)}")
    log.append(f"   T+1锁定 | 涨跌幅±10%~20%")
    if session != "close":
        log.append(f"   订单状态：生成计划 → 由盘执行器在交易时段成交")
    log.append(f"{'='*62}")
    log.append("")

    t1_tracker = load_t1_tracker()
    acc = st.get_account()
    positions = acc.get("positions", {})

    log.append(f"💰 账户: 现金{acc['cash']:.2f} | {len(positions)}只持仓")
    for code, pos in sorted(positions.items()):
        p, n, _ = st.get_realtime_price(code)
        name = pos.get("name", code)
        mv = (p or 0) * pos["shares"]
        cost_val = pos["avg_cost"] * pos["shares"]
        profit_pct = ((p or 0) / pos["avg_cost"] - 1) * 100
        locked = get_today_locked_shares(code, t1_tracker)
        lock_tag = f" 🔒T+1{locked}股" if locked > 0 else ""
        log.append(f"   {name}({code}): {pos['shares']}股 = {mv:.2f} ({profit_pct:+.1f}%){lock_tag}")
    log.append("")

    # 分析决策
    log.append(f"{'─'*62}")
    log.append("📊 逐股分析 & 决策")
    log.append(f"{'─'*62}")

    orders_created = 0
    for code, info in sorted(CANDIDATES.items(), key=lambda x: ["hold","high","medium","watch"].index(x[1].get("priority","watch"))):
        name = info["name"]
        analysis = st.analyze_stock(code)
        if isinstance(analysis, str):
            log.append(f"\n❌ {name}({code}): 分析失败 - {analysis}")
            continue

        news = get_news_score(code)
        tech = score_technicals(analysis)
        combined = calc_weighted_score(news, tech)
        decision = decide_action(code, name, combined, analysis, positions, session, t1_tracker)

        close = analysis.get("latest", {}).get("close", 0)
        log.append(f"\n{name} ({code}) — 现价 {close:.2f}")
        log.append(f"   新闻: {news['score']:+d}/10 | 技术: {tech['score']:+.1f}/10 → 综合: {combined['combined']:+.1f}/10")

        # 生成订单（非收盘时段且非hold）
        if session != "close" and decision["action"] not in ("hold",):
            oid = add_order(code, name, decision["action"], decision["shares"],
                           decision["reason"], session, decision["price"])
            orders_created += 1
            log.append(f"   📌 📋 订单已生成 [{oid[:8]}]: {decision['action']} {decision['shares']}股 — {decision['reason']}")
            log.append(f"   ⏰ 将在下一交易时段（{'09:30' if session=='pre-market' else '13:00'}）由执行器成交")
        else:
            log.append(f"   📌 决策: {decision['action'].upper()} — {decision['reason']}")

        log.append(f"   | 均线: {'/'.join(analysis.get('trend_signals',[]))}")
        log.append(f"   | {analysis.get('macd','')} | {analysis.get('rsi','')}")

    # 订单汇总
    log.append(f"\n{'─'*62}")
    if session == "close":
        log.append("📋 收盘复盘 — 不生成交易订单")
    else:
        log.append(f"📋 订单汇总: 生成 {orders_created} 个订单，等待盘执行器成交")
    log.append(f"{'─'*62}")

    # 清理
    cleanup_t1_tracker(t1_tracker, positions)

    log.append(f"\n{'='*62}")
    log.append(f"✅ {'复盘完成' if session=='close' else '分析完成'} · {date_str}")
    log.append(f"{'='*62}")

    return "\n".join(log)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=str, default="close",
                        choices=["pre-market", "midday", "close"])
    args = parser.parse_args()

    log = run_daily_analysis(session=args.session)
    log_file = LOG_DIR / f"analysis_{date.today().isoformat()}_{args.session}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(log)
    print(log)
    print(f"\n📝 日志: {log_file}")

if __name__ == "__main__":
    main()
