#!/usr/bin/env python3
"""
Crypto Trading Simulator - Virtual Account Management
Supports: balance, positions, buy, sell, history, reset
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
    return {"balance_usdt": 1000.0, "positions": {}, "initial_balance": 1000.0}

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
        "total_assets": round(bal, 2),
        "timestamp": datetime.now().isoformat()
    }

    # Calculate position values
    for symbol, pos in acc["positions"].items():
        qty = pos["quantity"]
        avg_price = pos["avg_price"]
        result["positions"][symbol] = {
            "quantity": qty,
            "avg_price": avg_price,
            "current_market_price": pos.get("current_price", avg_price),
            "cost": round(qty * avg_price, 2),
            "unrealized_pnl": 0  # Will be updated when market price is available
        }
        val = qty * pos.get("current_price", avg_price)
        result["position_value_usdt"] += val
        result["positions"][symbol]["value"] = round(val, 2)

    result["total_assets"] = round(bal + result["position_value_usdt"], 2)
    return result

def do_buy(symbol, quantity, price, reason=""):
    acc = load_account()
    cost = quantity * price
    if cost > acc["balance_usdt"]:
        return {"success": False, "error": f"Insufficient balance. Need {cost:.2f} USDT, have {acc['balance_usdt']:.2f}"}

    symbol = symbol.upper()

    # Update position
    if symbol in acc["positions"]:
        pos = acc["positions"][symbol]
        total_qty = pos["quantity"] + quantity
        total_cost = pos["quantity"] * pos["avg_price"] + cost
        pos["quantity"] = total_qty
        pos["avg_price"] = total_cost / total_qty
    else:
        acc["positions"][symbol] = {"quantity": quantity, "avg_price": price}

    acc["balance_usdt"] -= cost
    save_account(acc)

    # Record trade
    trades = load_trades()
    trade = {
        "id": f"B{len(trades['trades'])+1:04d}",
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": "buy",
        "quantity": quantity,
        "price": price,
        "cost": round(cost, 2),
        "balance_after": round(acc["balance_usdt"], 2),
        "reason": reason
    }
    trades["trades"].append(trade)
    save_trades(trades)

    return {"success": True, "trade": trade}

def do_sell(symbol, quantity=None, price=None, reason=""):
    acc = load_account()
    symbol = symbol.upper()

    if symbol not in acc["positions"]:
        return {"success": False, "error": f"No position in {symbol}"}

    pos = acc["positions"][symbol]
    qty = quantity if quantity is not None and quantity <= pos["quantity"] else pos["quantity"]

    if quantity is not None and quantity > pos["quantity"]:
        return {"success": False, "error": f"Insufficient {symbol}. Have {pos['quantity']}, want to sell {quantity}"}

    if price is None:
        price = pos.get("current_price", pos["avg_price"])

    proceeds = qty * price
    cost_basis = qty * pos["avg_price"]
    realized_pnl = proceeds - cost_basis

    pos["quantity"] -= qty
    if pos["quantity"] <= 0:
        del acc["positions"][symbol]
    else:
        acc["positions"][symbol] = pos

    acc["balance_usdt"] += proceeds
    save_account(acc)

    trades = load_trades()
    trade = {
        "id": f"S{len(trades['trades'])+1:04d}",
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": "sell",
        "quantity": qty,
        "price": price,
        "proceeds": round(proceeds, 2),
        "realized_pnl": round(realized_pnl, 2),
        "balance_after": round(acc["balance_usdt"], 2),
        "reason": reason
    }
    trades["trades"].append(trade)
    save_trades(trades)

    return {"success": True, "trade": trade}

def do_reset(initial_balance=1000.0):
    acc = {"balance_usdt": float(initial_balance), "positions": {}, "initial_balance": float(initial_balance)}
    save_account(acc)
    save_trades({"trades": []})
    return {"success": True, "initial_balance": float(initial_balance)}

def do_history(limit=20):
    trades = load_trades()
    return trades["trades"][-limit:]

def do_update_prices(prices):
    """Update current market prices for all positions"""
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
    elif command == "buy":
        symbol = sys.argv[2]
        qty = float(sys.argv[3])
        price = float(sys.argv[4])
        reason = sys.argv[5] if len(sys.argv) > 5 else ""
        result = do_buy(symbol, qty, price, reason)
        print(json.dumps(result, indent=2))
    elif command == "sell":
        symbol = sys.argv[2]
        qty = float(sys.argv[3]) if len(sys.argv) > 3 else None
        price = float(sys.argv[4]) if len(sys.argv) > 4 else None
        reason = sys.argv[5] if len(sys.argv) > 5 else ""
        result = do_sell(symbol, qty, price, reason)
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
        print("Usage: crypto_account.py [status|buy|sell|reset|history|update_prices]")
