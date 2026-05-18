#!/usr/bin/env python3
"""
⚡ 盘执行器 - 交易时段实时执行待处理订单
每15分钟运行一次，从 orders/ 目录读取当日待执行订单，在交易时间成交。
运行时段：09:30-11:30 (上午盘) | 13:00-14:57 (下午盘)
"""
import json, os, sys
from datetime import datetime, date, time
from pathlib import Path

SCRIPTS_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/scripts"))
DATA_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/data"))
LOG_DIR = Path(os.path.expanduser("~/.hermes/stock-trading-logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(str(SCRIPTS_DIR))

import importlib
spec = importlib.util.spec_from_file_location("stock_trader", SCRIPTS_DIR / "stock_trader.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

# ── 交易日历 ──
from market_calendar import is_trading_day

# ── 订单目录（按日期分文件） ──
ORDERS_DIR = LOG_DIR / "orders"
ORDERS_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DATA_FILE = DATA_DIR / "agent_t1_tracker.json"

def _orders_path(d=None):
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
    with open(_orders_path(d), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_pending_orders():
    today = date.today()
    orders = load_orders(today)
    today_str = today.isoformat()
    return [o for o in orders["orders"] if o["status"] == "pending" and o["date"] == today_str]

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

def cancel_order(oid, reason):
    today = date.today()
    orders = load_orders(today)
    for o in orders["orders"]:
        if o["id"] == oid:
            o["status"] = "cancelled"
            o["cancel_reason"] = reason
            break
    save_orders(orders, today)

# ── T+1 ──
def load_t1_tracker():
    if AGENT_DATA_FILE.exists():
        with open(AGENT_DATA_FILE) as f:
            return json.load(f)
    return {}

def save_t1_tracker(data):
    with open(AGENT_DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_t1_buy(code, shares, tracker):
    today = date.today().isoformat()
    if code not in tracker:
        tracker[code] = []
    tracker[code].append([today, shares])
    save_t1_tracker(tracker)

# ── 交易时段判断 ──
MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(14, 57)

def is_trading_time() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    if MORNING_START <= t <= MORNING_END:
        return True
    if AFTERNOON_START <= t <= AFTERNOON_END:
        return True
    return False


def run_executor() -> str:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    is_market_open = is_trading_time()

    log = []
    log.append(f"{'='*62}")
    log.append(f"⚡ 盘执行器 · {date_str}")

    # ── 休市日跳过 ──
    if not is_trading_day():
        log.append("   今日非交易日，跳过")
        log.append(f"{'='*62}")
        return "\n".join(log)

    log.append(f"   交易时段: {'🟢 开盘中' if is_market_open else '🔴 休市中'}")

    if not is_market_open:
        log.append("   当前非交易时段，无操作")
        log.append(f"{'='*62}")
        return "\n".join(log)

    # 检查待执行订单
    pending = get_pending_orders()
    if not pending:
        log.append("   无待执行订单")
        log.append(f"{'='*62}")
        return "\n".join(log)

    log.append(f"   待执行订单: {len(pending)} 个")
    log.append(f"{'='*62}")
    log.append("")

    t1_tracker = load_t1_tracker()
    executed_count = 0
    cancelled_count = 0

    for order in pending:
        code = order["code"]
        action = order["action"]
        shares = order["shares"]
        name = order["name"]

        # 获取当前市价
        price, real_name, _ = st.get_realtime_price(code)
        if price is None or price == 0:
            log.append(f"\n❌ {name}({code}): 无法获取实时价格，跳过")
            cancel_order(order["id"], "无法获取价格")
            cancelled_count += 1
            continue

        # 执行买入
        if action in ("buy", "buy_light"):
            result = st.buy(code, shares=shares)
            if "成功" in str(result):
                record_t1_buy(code, shares, t1_tracker)
                mark_executed(order["id"], price)
                executed_count += 1
                log.append(f"\n🟢 ✅ 成交: {name}({code}) 买入{shares}股 @ {price:.2f} | {result}")
            else:
                cancel_order(order["id"], f"买入失败: {result}")
                cancelled_count += 1
                log.append(f"\n❌ 失败: {name}({code}) {result}")

        # 执行卖出
        elif action in ("sell_all", "sell_half"):
            sell_shares = shares if action == "sell_half" else None
            result = st.sell(code, shares=sell_shares)
            if "成功" in str(result):
                mark_executed(order["id"], price)
                executed_count += 1
                log.append(f"\n🔴 ✅ 成交: {name}({code}) 卖出{'全部' if action=='sell_all' else str(shares)+'股'} @ {price:.2f} | {result}")
            else:
                cancel_order(order["id"], f"卖出失败: {result}")
                cancelled_count += 1
                log.append(f"\n❌ 失败: {name}({code}) {result}")

    # 汇总
    acc = st.get_account()
    positions = acc.get("positions", {})
    total_mv = acc["cash"]
    log.append(f"\n{'─'*62}")
    log.append(f"📊 执行结果: 成交{executed_count}单 | 取消{cancelled_count}单")
    log.append(f"   现金: {acc['cash']:.2f} | 持仓: {len(positions)}只")
    for code, pos in sorted(positions.items()):
        p, n, _ = st.get_realtime_price(code)
        name = pos.get("name", code)
        mv = (p or 0) * pos["shares"]
        total_mv += mv
        cost_val = pos["avg_cost"] * pos["shares"]
        profit_pct = ((p or 0) / pos["avg_cost"] - 1) * 100
        log.append(f"   {name}({code}): {pos['shares']}股 @ {pos['avg_cost']:.2f} = {mv:.2f} ({profit_pct:+.1f}%)")
    log.append(f"   总资产: {total_mv:.2f}")
    log.append(f"\n{'='*62}")

    return "\n".join(log)


def main():
    log = run_executor()
    log_file = LOG_DIR / f"executor_{date.today().isoformat()}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log + "\n")
    # 只print有实际交易操作的情况，无操作时静默
    if "成交" in log or "失败" in log or "❌" in log:
        print(log)
    else:
        # 完全静默：不发送到飞书
        pass


if __name__ == "__main__":
    main()
