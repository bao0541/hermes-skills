#!/usr/bin/env python3
"""
Crypto Trading Simulator - Virtual Account Management
Supports: long & short positions, balance, trades, history
"""
import json
import os
import sys
from datetime import datetime

DATA_DIR = os.path.expanduser("~/.hermes/crypto-simulator/data")
ACCOUNT_FILE = os.path.join(DATA_DIR, "account.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
os.makedirs(DATA_DIR, exist_ok=True)

def load_account():
    if os.path.exists(ACCOUNT_FILE):
        with open(ACCOUNT_FILE) as f:
            return json.load(f)
    return {"balance_usdt": 1000.0, "positions": {}, "initial_balance": 1000.0, "anti_martingale": {"multiplier": 1.0, "consecutive_wins": 0, "consecutive_losses": 0}}

def save_account(acc):
    with open(ACCOUNT_FILE, "w") as f:
        json.dump(acc, f, indent=2)

def load_trades():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE) as f:
            return json.load(f)
    return {"trades": []}

def save_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def do_status():
    acc = load_account()
    bal = acc["balance_usdt"]
    init = acc["initial_balance"]
    pnl = bal - init
    pnl_pct = (pnl / init) * 100 if init > 0 else 0

    result = {
        "mode": "SIMULATION",
        "balance_usdt": round(bal, 2),
        "initial_balance": init,
        "pnl_usdt": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "positions": {},
        "position_value_usdt": 0,
        "margin_locked_usdt": 0,
        "total_assets": round(bal, 2),
        "timestamp": datetime.now().isoformat()
    }

    pos_value = 0
    margin_locked = 0
    for symbol, pos in acc["positions"].items():
        direction = pos.get("direction", "long")
        qty = pos["quantity"]
        entry_price = pos["avg_price"]
        mkt_price = pos.get("current_price", entry_price)

        if direction == "long":
            unrealized_pnl = (mkt_price - entry_price) * qty
            val = mkt_price * qty
            cost = entry_price * qty
            margin_locked += cost
        else:  # short
            unrealized_pnl = (entry_price - mkt_price) * qty
            val = entry_price * qty  # notional value (what we owe)
            cost = entry_price * qty
            margin_locked += cost

        pos_value += val
        result["positions"][symbol] = {
            "direction": direction,
            "quantity": qty,
            "avg_price": entry_price,
            "current_market_price": mkt_price,
            "cost": round(cost, 2),
            "value": round(val, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round((unrealized_pnl / cost * 100) if cost > 0 else 0, 2),
        }

    result["position_value_usdt"] = round(pos_value, 2)
    result["margin_locked_usdt"] = round(margin_locked, 2)
    result["free_balance_usdt"] = round(bal - margin_locked, 2)
    result["total_assets"] = round(bal + sum(
        p["unrealized_pnl"] for p in result["positions"].values()
    ), 2)

    # Anti-martingale status
    am = acc.get("anti_martingale", {"multiplier": 1.0, "consecutive_wins": 0, "consecutive_losses": 0})
    result["anti_martingale"] = {
        "multiplier": am.get("multiplier", 1.0),
        "consecutive_wins": am.get("consecutive_wins", 0),
        "consecutive_losses": am.get("consecutive_losses", 0),
    }

    return result

def do_open(symbol, direction, quantity, price, reason=""):
    """Open a long or short position"""
    acc = load_account()
    symbol = symbol.upper()

    # Check if already have a position in this symbol (opposite direction not allowed)
    if symbol in acc["positions"]:
        existing = acc["positions"][symbol]
        if existing.get("direction") != direction:
            return {"success": False, "error": f"Already have a {existing['direction']} position in {symbol}. Close it first."}

    cost = quantity * price  # notional value

    if direction == "long":
        if cost > acc["balance_usdt"]:
            return {"success": False, "error": f"Insufficient balance. Need {cost:.2f} USDT, have {acc['balance_usdt']:.2f}"}
        acc["balance_usdt"] -= cost
    else:  # short
        # For shorts, add the proceeds to balance (you sell first)
        acc["balance_usdt"] += cost

    # Update or create position
    if symbol in acc["positions"]:
        pos = acc["positions"][symbol]
        total_qty = pos["quantity"] + quantity
        total_cost = pos["quantity"] * pos["avg_price"] + cost
        pos["quantity"] = total_qty
        pos["avg_price"] = total_cost / total_qty
    else:
        acc["positions"][symbol] = {
            "direction": direction,
            "quantity": quantity,
            "avg_price": price
        }

    save_account(acc)

    trades = load_trades()
    action_label = "open_long" if direction == "long" else "open_short"
    trade = {
        "id": f"{action_label[0].upper()}{len(trades['trades'])+1:04d}",
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": action_label,
        "direction": direction,
        "quantity": quantity,
        "price": price,
        "notional": round(cost, 2),
        "balance_after": round(acc["balance_usdt"], 2),
        "reason": reason
    }
    trades["trades"].append(trade)
    save_trades(trades)

    return {"success": True, "trade": trade}

def do_close(symbol, quantity=None, price=None, reason=""):
    """Close a position (long: sell, short: buy back)"""
    acc = load_account()
    symbol = symbol.upper()

    if symbol not in acc["positions"]:
        return {"success": False, "error": f"No position in {symbol}"}

    pos = acc["positions"][symbol]
    direction = pos.get("direction", "long")
    qty = quantity if quantity is not None and quantity <= pos["quantity"] else pos["quantity"]

    if quantity is not None and quantity > pos["quantity"]:
        return {"success": False, "error": f"Insufficient {symbol}. Have {pos['quantity']}, want to close {quantity}"}

    if price is None:
        price = pos.get("current_price", pos["avg_price"])

    notional = qty * price
    cost_basis = qty * pos["avg_price"]

    if direction == "long":
        # Sell to close - get proceeds back
        proceeds = notional
        realized_pnl = proceeds - cost_basis
        acc["balance_usdt"] += proceeds
    else:  # short
        # Buy back to close - pay the notional
        proceeds = cost_basis  # this was the amount we got when opening
        realized_pnl = cost_basis - notional  # entry_price - close_price * qty
        acc["balance_usdt"] -= notional

    pos["quantity"] -= qty
    if pos["quantity"] <= 0:
        # Position fully closed - update anti-martingale multiplier
        am = acc.setdefault("anti_martingale", {"multiplier": 1.0, "consecutive_wins": 0, "consecutive_losses": 0})
        if realized_pnl > 0:
            am["multiplier"] = min(round(am["multiplier"] * 1.5, 2), 3.0)  # cap at 3x
            am["consecutive_wins"] += 1
            am["consecutive_losses"] = 0
        else:
            am["multiplier"] = 1.0
            am["consecutive_losses"] += 1
            am["consecutive_wins"] = 0
        del acc["positions"][symbol]
    else:
        acc["positions"][symbol] = pos

    save_account(acc)

    trades = load_trades()
    action_label = "close_long" if direction == "long" else "close_short"
    trade = {
        "id": f"C{len(trades['trades'])+1:04d}",
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": action_label,
        "direction": direction,
        "quantity": qty,
        "price": price,
        "notional": round(notional, 2),
        "realized_pnl": round(realized_pnl, 2),
        "balance_after": round(acc["balance_usdt"], 2),
        "reason": reason
    }
    trades["trades"].append(trade)
    save_trades(trades)

    return {"success": True, "trade": trade}

def do_reset(initial_balance=1000.0):
    acc = {"balance_usdt": float(initial_balance), "positions": {}, "initial_balance": float(initial_balance),
           "anti_martingale": {"multiplier": 1.0, "consecutive_wins": 0, "consecutive_losses": 0}}
    save_account(acc)
    save_trades({"trades": []})
    return {"success": True, "initial_balance": float(initial_balance)}

def do_history(limit=20):
    trades = load_trades()
    return trades["trades"][-limit:]

def do_update_prices(prices):
    acc = load_account()
    for symbol, price in prices.items():
        if symbol in acc["positions"]:
            acc["positions"][symbol]["current_price"] = price
    save_account(acc)

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"

    if command == "status":
        result = do_status()
        print(json.dumps(result, indent=2))
    elif command == "open":
        symbol = sys.argv[2]
        direction = sys.argv[3].lower()
        qty = float(sys.argv[4])
        price = float(sys.argv[5])
        reason = sys.argv[6] if len(sys.argv) > 6 else ""
        if direction not in ("long", "short"):
            print(json.dumps({"success": False, "error": f"Invalid direction '{direction}'. Use 'long' or 'short'."}))
        else:
            result = do_open(symbol, direction, qty, price, reason)
            print(json.dumps(result, indent=2))
    elif command == "close":
        symbol = sys.argv[2]
        qty = float(sys.argv[3]) if len(sys.argv) > 3 else None
        price = float(sys.argv[4]) if len(sys.argv) > 4 else None
        reason = sys.argv[5] if len(sys.argv) > 5 else ""
        result = do_close(symbol, qty, price, reason)
        print(json.dumps(result, indent=2))
    elif command == "buy":
        # Legacy: open long
        symbol = sys.argv[2]
        qty = float(sys.argv[3])
        price = float(sys.argv[4])
        reason = sys.argv[5] if len(sys.argv) > 5 else ""
        result = do_open(symbol, "long", qty, price, reason)
        print(json.dumps(result, indent=2))
    elif command == "sell":
        # Legacy: close position
        symbol = sys.argv[2]
        qty = float(sys.argv[3]) if len(sys.argv) > 3 else None
        price = float(sys.argv[4]) if len(sys.argv) > 4 else None
        reason = sys.argv[5] if len(sys.argv) > 5 else ""
        result = do_close(symbol, qty, price, reason)
        print(json.dumps(result, indent=2))
    elif command == "reset":
        bal = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
        result = do_reset(bal)
        print(json.dumps(result, indent=2))
    elif command == "history":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        result = do_history(limit)
        print(json.dumps(result, indent=2))
    elif command == "update_prices":
        import ast
        prices = ast.literal_eval(sys.argv[2])
        result = do_update_prices(prices)
        print(json.dumps({"success": True}))
    else:
        print(f"Unknown command: {command}")
        print("Usage: crypto_account.py [status|open|close|buy|sell|reset|history|update_prices]")
