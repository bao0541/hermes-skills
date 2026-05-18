#!/usr/bin/env python3
"""
📈 自动炒股Agent v2.0 — 多因子分析 + 动态止盈止损 + 5只持仓限制

交易日三个时段：
  - 08:30 选股粗筛 (stock_screener.py, 纯Python)
  - 09:00 开盘前: 加载候选池 → 多因子评分 → 生成订单计划
  - 11:35 午盘:   复盘 → 动态止盈止损调整 → 生成下午订单
  - 15:05 收盘:   复盘总结，调整次日止盈止损位

设计原则：
  - 数据采集用纯Python（零LLM消耗）
  - LLM只在"综合决策"环节使用（打分+买入理由）
  - 所有数据持久化到JSON，供LLM分析使用
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
STOP_CONFIG_FILE = LOG_DIR / "stop_config.json"  # 止盈止损配置持久化

sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(str(SCRIPTS_DIR))

import importlib
spec = importlib.util.spec_from_file_location("stock_trader", SCRIPTS_DIR / "stock_trader.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

from market_calendar import is_trading_day

# ═══════════════════════════════════════════════════════════
# 核心配置
# ═══════════════════════════════════════════════════════════

MAX_HOLDINGS = 5              # 最大持仓数
INITIAL_CAPITAL = 100_000     # 初始资金
MIN_CASH_RESERVE = 20_000     # 最低现金保留（20%）
MAX_PRICE_PER_LOT = 30_000    # 1手最高3万（价格上限300元）
MIN_BUY_AMOUNT = 5_000        # 单笔最小买入
SECTOR_MAX_RATIO = 0.4        # 单个板块持仓占比上限

# 止盈止损默认参数
DEFAULT_STOP_LOSS = -0.08     # 初始止损 -8%
DEFAULT_TAKE_PROFIT = 0.15    # 初始止盈 +15%
TRAILING_ACTIVATE = 0.10      # 浮动止盈激活线 +10%
TRAILING_DRAWDOWN = 0.05      # 浮动止盈回撤 5%

# ── 订单管理 ──────────────────────────────────────────

def _orders_path(d=None):
    if d is None: d = date.today()
    return ORDERS_DIR / f"orders_{d.isoformat()}.json"

def load_orders(d=None):
    path = _orders_path(d)
    if path.exists():
        with open(path) as f: return json.load(f)
    return {"orders": []}

def save_orders(data, d=None):
    with open(_orders_path(d), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_order(code, name, action, shares, reason, session, price_ref):
    today = date.today()
    orders = load_orders(today)
    oid = hashlib.md5(f"{today}{code}{action}{session}{datetime.now().timestamp()}".encode()).hexdigest()[:8]
    orders["orders"].append({
        "id": oid, "date": today.isoformat(),
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

# ── T+1 追踪 ──────────────────────────────────────────

def load_t1_tracker():
    if AGENT_DATA_FILE.exists():
        with open(AGENT_DATA_FILE) as f: return json.load(f)
    return {}

def save_t1_tracker(data):
    with open(AGENT_DATA_FILE, "w") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def get_today_locked_shares(code, tracker):
    today = date.today().isoformat()
    locked = 0
    for buy_date, shares in tracker.get(code, []):
        if buy_date == today: locked += shares
    return locked

def record_t1_buy(code, shares, tracker):
    today = date.today().isoformat()
    if code not in tracker: tracker[code] = []
    tracker[code].append([today, shares])
    save_t1_tracker(tracker)

def cleanup_t1_tracker(tracker, positions):
    cleaned = {}
    for code, records in tracker.items():
        if code in positions:
            today = date.today().isoformat()
            cleaned[code] = [[d, s] for d, s in records if d == today]
    save_t1_tracker(cleaned)

# ── 止盈止损管理 ──────────────────────────────────────

def load_stop_configs():
    """加载每只股票的止盈止损配置"""
    if STOP_CONFIG_FILE.exists():
        with open(STOP_CONFIG_FILE) as f: return json.load(f)
    return {}

def save_stop_configs(configs):
    with open(STOP_CONFIG_FILE, "w") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)

def init_stop_config(code, buy_price):
    """初始化某只股票的止盈止损"""
    configs = load_stop_configs()
    configs[code] = {
        "buy_price": buy_price,
        "stop_loss": round(buy_price * (1 + DEFAULT_STOP_LOSS), 2),   # 止损价
        "take_profit": round(buy_price * (1 + DEFAULT_TAKE_PROFIT), 2), # 止盈价
        "highest_since_buy": buy_price,   # 买入后最高价（浮动止盈用）
        "initial_stop_pct": DEFAULT_STOP_LOSS,
        "initial_tp_pct": DEFAULT_TAKE_PROFIT,
        "updated_at": datetime.now().isoformat(),
    }
    save_stop_configs(configs)
    return configs[code]

def update_stop_configs(positions):
    """每日更新所有持仓的止盈止损（浮动止盈/动态止损）"""
    configs = load_stop_configs()
    changed = False
    
    for code, pos in positions.items():
        if code not in configs:
            continue
        cfg = configs[code]
        price, _, _ = st.get_realtime_price(code)
        if price is None or price == 0:
            continue
        
        buy_price = cfg["buy_price"]
        profit_pct = (price / buy_price - 1) * 100
        
        # 更新最高价
        if price > cfg["highest_since_buy"]:
            cfg["highest_since_buy"] = price
            # 如果盈利超过TRAILING_ACTIVATE，启动浮动止盈
            if profit_pct >= TRAILING_ACTIVATE * 100:
                new_stop = price * (1 - TRAILING_DRAWDOWN)
                if new_stop > cfg["stop_loss"]:
                    cfg["stop_loss"] = round(new_stop, 2)
                    changed = True
        
        # 如果盈利超过DEFAULT_TAKE_PROFIT，上移止盈线
        if profit_pct >= DEFAULT_TAKE_PROFIT * 100:
            new_tp = price * (1 - TRAILING_DRAWDOWN)
            # 但不止损止盈在同一价位
            if new_tp > cfg["stop_loss"] and new_tp > cfg["take_profit"]:
                cfg["take_profit"] = round(new_tp, 2)
                changed = True
        
        cfg["current_price"] = round(price, 2)
        cfg["profit_pct"] = round(profit_pct, 2)
        cfg["updated_at"] = datetime.now().isoformat()
    
    if changed:
        save_stop_configs(configs)
    return configs


def get_trade_signal(code, price, stop_configs):
    """检查止盈止损是否触发"""
    if code not in stop_configs:
        return None
    cfg = stop_configs[code]
    
    # 止损触发
    if price <= cfg["stop_loss"]:
        return {
            "action": "sell_all",
            "reason": f"止损触发：现价{price:.2f} ≤ 止损价{cfg['stop_loss']:.2f}",
        }
    
    # 止盈触发
    if price >= cfg["take_profit"]:
        # 如果价格超过止盈线且开始回落（当前价低于最高价2%以上），止盈
        highest = cfg["highest_since_buy"]
        if price < highest * 0.98:
            return {
                "action": "sell_half",
                "reason": f"止盈触发：现价{price:.2f}回落，止盈价{cfg['take_profit']:.2f}",
            }
    
    return None


# ── 选股池加载（从stock_screener输出） ────────────────

def load_candidate_pool():
    """加载当日候选股票池（由stock_screener.py生成）"""
    today = date.today().isoformat()
    pool_file = LOG_DIR / f"candidates_{today}.json"
    
    if not pool_file.exists():
        # 兜底：加载最近的候选池
        pools = sorted(LOG_DIR.glob("candidates_*.json"), reverse=True)
        if pools:
            pool_file = pools[0]
        else:
            return []
    
    try:
        with open(pool_file) as f:
            data = json.load(f)
        return data.get("candidates", [])
    except:
        return []


def get_news_score(code):
    """新闻面评分（简化版，基于当前持仓和候选池的更新）"""
    # 此函数会在09:00被LLM调用时补充详细评分
    # 简化版返回中性分，由LLM在分析中补充
    return {"score": 0, "reasons": "等待LLM分析补充"}


def load_screener_scores():
    """加载选股器输出中的技术评分"""
    today = date.today().isoformat()
    pool_file = LOG_DIR / f"candidates_{today}.json"
    if pool_file.exists():
        try:
            with open(pool_file) as f:
                data = json.load(f)
            return {c["code"]: c["score"] for c in data.get("candidates", [])}
        except:
            pass
    return {}


# ── 核心分析流程 ──────────────────────────────────────

def run_daily_analysis(session="close"):
    """
    主分析流程：
    1. 加载账户和持仓
    2. 更新止盈止损
    3. 检查持仓止盈止损触发
    4. 评估候选股票
    5. 生成订单
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    
    log = []
    
    # ── 休市日跳过（收盘复盘除外） ──
    if session != "close" and not is_trading_day():
        msg = (f"{'='*62}\n"
               f"📅 {date_str}\n"
               f"   今日非交易日，跳过股票分析任务\n"
               f"{'='*62}")
        print(msg)
        (LOG_DIR / f"skip_{date.today().isoformat()}_{session}.log").write_text(msg)
        return msg
    
    log.append(f"{'='*62}")
    log.append(f"📈 自动炒股Agent v2.0 · {date_str}")
    labels = {
        "pre-market": "开盘前分析 (09:00) → 选股+评分+订单",
        "midday": "午盘复盘 (11:35) → 止盈止损调整+订单",
        "close": "收盘复盘 (15:05) — 统计+浮动止盈调整",
    }
    log.append(f"   📋 {labels.get(session, session)}")
    log.append(f"   🎯 最大持仓5只 | T+1锁定 | 动态止盈止损")
    log.append(f"{'='*62}\n")
    
    t1_tracker = load_t1_tracker()
    acc = st.get_account()
    positions = acc.get("positions", {})
    cash = acc["cash"]
    
    # ── 账户概览 ──
    total_mv = cash
    log.append(f"💰 账户概览")
    log.append(f"   现金: ¥{cash:,.2f}")
    log.append(f"   持仓: {len(positions)}/{MAX_HOLDINGS} 只")
    
    for code, pos in sorted(positions.items()):
        p, n, _ = st.get_realtime_price(code)
        name = pos.get("name", code)
        mv = (p or 0) * pos["shares"]
        cost_val = pos["avg_cost"] * pos["shares"]
        profit_pct = ((p or 0) / pos["avg_cost"] - 1) * 100
        total_mv += mv
        locked = get_today_locked_shares(code, t1_tracker)
        lock_tag = f" 🔒T+1{locked}股" if locked > 0 else ""
        log.append(f"   {name}({code}): {pos['shares']}股 @ {pos['avg_cost']:.2f} = ¥{mv:,.2f} ({profit_pct:+.1f}%){lock_tag}")
    
    total_pnl = total_mv - INITIAL_CAPITAL
    total_pnl_pct = (total_pnl / INITIAL_CAPITAL) * 100
    log.append(f"   总资产: ¥{total_mv:,.2f} ({total_pnl_pct:+.2f}%)")
    log.append("")
    
    # ── 更新浮动止盈止损 ──
    if positions:
        log.append(f"{'─'*62}")
        log.append("📊 止盈止损检查")
        log.append(f"{'─'*62}")
        stop_configs = update_stop_configs(positions)
        for code, pos in sorted(positions.items()):
            p, name, _ = st.get_realtime_price(code)
            if code in stop_configs:
                cfg = stop_configs[code]
                log.append(f"   {name}({code}):")
                log.append(f"     买入价 {cfg['buy_price']:.2f} | 最高 {cfg['highest_since_buy']:.2f}")
                log.append(f"     止损 {cfg['stop_loss']:.2f} ({(p/cfg['stop_loss']-1)*100:+.1f}%)")
                log.append(f"     止盈 {cfg['take_profit']:.2f} ({(p/cfg['take_profit']-1)*100:+.1f}%)")
                if p and p <= cfg['stop_loss'] * 1.02:
                    log.append(f"     ⚠️ 接近止损!")
                elif p and p >= cfg['take_profit'] * 0.98:
                    log.append(f"     ⚠️ 接近止盈!")
        log.append("")
    
    # ── 卖出检查（止盈止损触发） ──
    if session != "close":
        stop_configs = load_stop_configs()
        log.append(f"{'─'*62}")
        log.append("🔴 卖出信号检查")
        log.append(f"{'─'*62}")
        
        for code, pos in sorted(positions.items()):
            p, name, _ = st.get_realtime_price(code)
            if p is None:
                continue
            
            # T+1 检查
            locked = get_today_locked_shares(code, t1_tracker)
            sellable = pos["shares"] - locked
            if sellable <= 0:
                log.append(f"   {name}({code}): T+1锁定中，跳过")
                continue
            
            # 止盈止损检查
            signal = get_trade_signal(code, p, stop_configs)
            if signal:
                oid = add_order(code, name, signal["action"], sellable,
                               signal["reason"], session, p)
                log.append(f"   🚨 {name}({code}): {signal['reason']}")
                log.append(f"   📌 订单已生成: sell_all {sellable}股")
        
        # 技术面卖出检查（综合分<-4 或 MACD死叉+RSI高位）
        for code, pos in sorted(positions.items()):
            if any(o["code"] == code and o["status"] == "pending" 
                   for o in get_pending_orders()):
                continue  # 已有卖出订单，跳过
            
            analysis = st.analyze_stock(code)
            if isinstance(analysis, str):
                continue
            
            macd_text = analysis.get("macd", "").lower()
            rsi_text = analysis.get("rsi", "").lower()
            trend_signals = analysis.get("trend_signals", [])
            
            # MACD死叉 + 趋势转弱
            is_dead_cross = "死叉" in macd_text
            trend_weak = any("空头" in s for s in trend_signals)
            
            if is_dead_cross and trend_weak:
                p, name, _ = st.get_realtime_price(code)
                locked = get_today_locked_shares(code, t1_tracker)
                sellable = pos["shares"] - locked
                if sellable > 0:
                    oid = add_order(code, name, "sell_all", sellable,
                                   f"策略卖出：MACD死叉+趋势转弱", session, p)
                    log.append(f"   📉 {name}({code}): 策略卖出(MACD死叉+趋势转弱)")
                    log.append(f"   📌 订单已生成: sell_all {sellable}股")
        
        log.append("")
    
    # ── 买入评估（仅pre-market和midday） ──
    if session != "close":
        log.append(f"{'─'*62}")
        log.append("🟢 买入评估")
        log.append(f"{'─'*62}")
        
        if len(positions) >= MAX_HOLDINGS:
            log.append(f"   已满仓 {MAX_HOLDINGS} 只，暂不评估买入")
        elif cash < MIN_CASH_RESERVE:
            log.append(f"   现金 ¥{cash:,.0f} < 保留 ¥{MIN_CASH_RESERVE:,}，暂不评估买入")
        else:
            # 加载候选池
            candidates = load_candidate_pool()
            if not candidates:
                log.append("   ⚠️ 无候选池数据，请先运行 stock_screener.py")
            else:
                # 排除已持仓的
                candidates = [c for c in candidates if c["code"] not in positions]
                # 排除已有买入订单的
                pending_buy = {o["code"] for o in get_pending_orders() 
                              if o["action"] in ("buy", "buy_light")}
                candidates = [c for c in candidates if c["code"] not in pending_buy]
                
                log.append(f"   候选池可用: {len(candidates)} 只")
                
                # 逐一分析候选股
                buys_created = 0
                for c in candidates[:10]:  # 只看前10只
                    if buys_created >= (MAX_HOLDINGS - len(positions)):
                        break
                    
                    code = c["code"]
                    name = c["name"]
                    price = c.get("price", 0)
                    screener_score = c.get("score", 0)
                    
                    # 价格过滤（10万资金，1手不能太贵）
                    if price <= 0:
                        continue
                    lot_cost = price * 100
                    if lot_cost > MAX_PRICE_PER_LOT:
                        log.append(f"   {name}({code}): 1手¥{lot_cost:,.0f}超限，跳过")
                        continue
                    
                    # 技术分析二次确认
                    tech_analysis = st.analyze_stock(code)
                    if isinstance(tech_analysis, str):
                        log.append(f"   {name}({code}): 分析失败 - {tech_analysis}")
                        continue
                    
                    # 计算可买手数
                    available = cash - MIN_CASH_RESERVE
                    max_shares = int(available / price / 100) * 100
                    if max_shares < 100:
                        continue
                    
                    # 板块分散度检查
                    sector = c.get("sector", "其他")
                    sector_count = sum(1 for p in positions.values() 
                                       if p.get("sector") == sector)
                    if sector_count >= 1:
                        log.append(f"   {name}({code}): 板块[{sector}]已有持仓，跳过多只同板块")
                        continue
                    
                    # 仓位计算：每只约 (总资产 - 保留) / 剩余仓位
                    slots_left = MAX_HOLDINGS - len(positions) - buys_created
                    if slots_left <= 0:
                        continue
                    per_position = (available) / slots_left
                    buy_shares = int(min(per_position, max_shares * price) / price / 100) * 100
                    if buy_shares < 100:
                        continue
                    
                    # 评分门槛：低于5分空仓观望，不买
                    if screener_score < 5:
                        log.append(f"   ⏭️ {name}({code}): 评分{screener_score}<5，空仓观望")
                        continue
                    
                    oid = add_order(code, name, "buy", buy_shares,
                                   f"选股评分{screener_score}≥5，买入{buy_shares}股", 
                                   session, price)
                    buys_created += 1
                    log.append(f"   🟢 {name}({code}): 评分{screener_score}≥5→买入{buy_shares}股 @ {price:.2f}")
                    log.append(f"   📌 订单已生成 [{oid[:8]}]: buy {buy_shares}股")
                    
                    # 初始化止盈止损
                    init_stop_config(code, price)
                
                if buys_created == 0:
                    log.append(f"   没有符合买入条件的候选股")
        
        log.append("")
    
    # ── 收盘后清理 ──
    if session == "close":
        cleanup_t1_tracker(t1_tracker, positions)
        # 打印当日Summary
        log.append(f"{'─'*62}")
        log.append("📋 收盘汇总")
        log.append(f"{'─'*62}")
        log.append(f"   现金: ¥{cash:,.2f}")
        log.append(f"   持仓: {len(positions)}/{MAX_HOLDINGS} 只")
        log.append(f"   总资产: ¥{total_mv:,.2f} ({total_pnl_pct:+.2f}%)")
        log.append(f"   浮动止盈止损已更新")
    
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


if __name__ == "__main__":
    main()
