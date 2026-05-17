#!/usr/bin/env python3
"""
Black Swan Emergency Checker
Run BEFORE each trading cycle. Checks market conditions and updates emergency status.
If in emergency mode, no new trades allowed.
"""
import json
import os
import sys
from datetime import datetime, timedelta

DATA_DIR = os.path.expanduser("~/.hermes/crypto-simulator/data")
STATUS_FILE = os.path.join(DATA_DIR, "black_swan_status.json")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from crypto_market import fetch_market_data

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE) as f:
            return json.load(f)
    return {"level": "none", "triggered_at": None, "triggered_by": None,
            "price_at_trigger": None, "cool_until": None,
            "open_positions_frozen": False,
            "description": "Current emergency status. Levels: none, yellow, orange, red"}

def save_status(s):
    with open(STATUS_FILE, "w") as f:
        json.dump(s, f, indent=2)

def check():
    status = load_status()
    now = datetime.now()

    # Check if cooldown has expired
    if status["cool_until"]:
        cool_until = datetime.fromisoformat(status["cool_until"])
        if now >= cool_until:
            status["level"] = "none"
            status["cool_until"] = None
            status["open_positions_frozen"] = False
            status["triggered_by"] = None
            save_status(status)
            return {"level": "none", "message": "Cooldown expired, trading resumes."}

    # If already in emergency, don't re-check, just report
    if status["level"] != "none":
        return status

    # Fetch market data
    try:
        market = fetch_market_data("ETH/USDT")
    except Exception as e:
        return {"level": "unknown", "error": str(e), "message": "Cannot fetch market data for emergency check"}

    price = market["current_price"]
    change_24h = abs(market.get("change_24h_pct", 0))
    volatility = market.get("volatility", {})
    vol_status = volatility.get("status", "normal")

    # Check 15m candle for sharp movements
    klines_15m = market.get("technical_indicators", {}).get("15m", {})
    candle_range_pct = abs(klines_15m.get("supertrend", {}).get("distance_pct", 0))
    bollinger = klines_15m.get("bollinger_signal", "within_bands")

    triggered = False
    level = "none"
    reason = ""

    # 🔴 Red: 24h drop > 20%
    if change_24h > 20:
        level = "red"
        reason = f"24h跌幅{change_24h:.1f}% > 20%，触发红色警报"
        triggered = True

    # 🟠 Orange: 24h drop > 10%
    elif change_24h > 10:
        level = "orange"
        reason = f"24h跌幅{change_24h:.1f}% > 10%，触发橙色警报"
        triggered = True

    # 🟡 Yellow: volatility extreme or price breaking bollinger bands sharply
    elif vol_status == "extreme":
        level = "yellow"
        reason = f"波动率等级 extreme，触发黄色预警"
        triggered = True
    elif bollinger in ("above_upper", "below_lower") and change_24h > 5:
        level = "yellow"
        reason = f"价格突破布林带+24h波动{change_24h:.1f}%，触发黄色预警"
        triggered = True

    if triggered:
        cool_hours = {"yellow": 6, "orange": 24, "red": 72}
        cool_until = now + timedelta(hours=cool_hours[level])
        status["level"] = level
        status["triggered_at"] = now.isoformat()
        status["triggered_by"] = reason
        status["price_at_trigger"] = price
        status["cool_until"] = cool_until.isoformat()
        status["open_positions_frozen"] = True
        save_status(status)

        return {
            "level": level,
            "message": f"⚠️ {reason}。24h跌幅{change_24h:.1f}%，当前${price:.0f}。冷静期至{cool_until.strftime('%m-%d %H:%M')}，期间禁止开新仓。"
        }

    return {"level": "none", "message": "市场正常，无预警。"}

if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
