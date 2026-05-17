#!/usr/bin/env python3
"""
Crypto Agent - Comprehensive analysis for AI decision making
Called by cron job every 30 minutes
Outputs structured JSON for AI analysis
"""
import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto_market import fetch_market_data
import crypto_account as account

def main(symbol="ETH/USDT"):
    # 1. Get market data
    market = fetch_market_data(symbol)

    # 2. Get account status
    acc = account.do_status()

    # 3. Update current prices in account
    coin = symbol.split("/")[0]
    account.do_update_prices({coin: market["current_price"]})

    # 4. Get recent trade history
    history = account.do_history(5)

    # 5. Also fetch BTC for comparison
    try:
        btc_market = fetch_market_data("BTC/USDT")
    except:
        btc_market = {"current_price": 0, "change_24h_pct": 0}

    # 6. Build analysis output
    output = {
        "summary": {
            "symbol": symbol,
            "price_usdt": market["current_price"],
            "change_24h_pct": market["change_24h_pct"],
            "volatility": market["volatility"],
            "market_tone": market["market_tone"],
            "btc_price": btc_market["current_price"],
            "btc_change_24h": btc_market["change_24h_pct"],
            "eth_btc_ratio": round(market["current_price"] / btc_market["current_price"], 6) if btc_market["current_price"] else 0,
        },
        "technical_analysis": {
            "15m": market["technical_indicators"]["15m"],
            "1h": market["technical_indicators"]["1h"],
            "4h": market["technical_indicators"]["4h"],
            "1d": market["technical_indicators"]["1d"],
        },
        "account": acc,
        "recent_trades": history,
        "timestamp": market["timestamp"],

        # For AI: key indicators summary
        "ai_summary": {
            "price": market["current_price"],
            "trend_1h": market["technical_indicators"]["1h"].get("trend", "unknown"),
            "trend_4h": market["technical_indicators"]["4h"].get("trend", "unknown"),
            "rsi_1h": market["technical_indicators"]["1h"].get("RSI", 50),
            "rsi_4h": market["technical_indicators"]["4h"].get("RSI", 50),
            "macd_1h": market["technical_indicators"]["1h"].get("macd_signal", "neutral"),
            "macd_4h": market["technical_indicators"]["4h"].get("macd_signal", "neutral"),
            "bb_position_1h": market["technical_indicators"]["1h"].get("bollinger_signal", "within_bands"),
            "supertrend_1h": market["technical_indicators"]["1h"].get("supertrend", {}).get("trend", "unknown"),
            "supertrend_4h": market["technical_indicators"]["4h"].get("supertrend", {}).get("trend", "unknown"),
            "ema200_1h": market["technical_indicators"]["1h"].get("EMA200", 0),
            "price_vs_ema200_1h": market["technical_indicators"]["1h"].get("price_vs_EMA200", 0),
            "atr_1h_dollars": market["technical_indicators"]["1h"].get("ATR", 0),
            "atr_1h_pct": market["technical_indicators"]["1h"].get("ATR_pct", 0),
            "supertrand_stop_distance": 0,  # calc below
            "position_multiplier": 0,  # anti-martingale tracker
            "volume_1h": market["technical_indicators"]["1h"].get("volume_signal", "normal"),
            "volatility_level": market["volatility"]["status"],
            "volatility_daily_pct": market["volatility"]["daily_volatility_pct"],
            "market_tone": market["market_tone"],
            "position": list(acc["positions"].keys()),
            "position_cost": sum(p.get("cost", 0) for p in acc["positions"].values()) if acc["positions"] else 0,
            "unrealized_pnl": 0,  # calc below
            "balance_usdt": acc["balance_usdt"],
            "total_assets": acc["total_assets"],
            "total_pnl_pct": acc["pnl_pct"],
        }
    }

    # Calculate unrealized PnL
    total_upnl = 0
    for sym, pos in acc.get("positions", {}).items():
        val = pos.get("value", 0)
        cost = pos.get("cost", 0)
        upnl = val - cost
        total_upnl += upnl
    output["ai_summary"]["unrealized_pnl"] = round(total_upnl, 2)
    output["ai_summary"]["unrealized_pnl_pct"] = round(
        (total_upnl / output["ai_summary"]["position_cost"] * 100) if output["ai_summary"]["position_cost"] > 0 else 0, 2
    )

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ETH/USDT"
    main(symbol)
