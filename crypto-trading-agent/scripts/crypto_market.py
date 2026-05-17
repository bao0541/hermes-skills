#!/usr/bin/env python3
"""
Crypto Market Data Fetcher - Binance
Fetches: ticker, OHLCV, technical indicators
"""
import ccxt
import pandas as pd
import numpy as np
import json
import sys
from datetime import datetime

SYMBOLS = ["ETH/USDT", "BTC/USDT"]

def fetch_market_data(symbol="ETH/USDT"):
    """Fetch comprehensive market data for analysis"""
    exchange = ccxt.binance()

    # Current ticker
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker["last"]
    change_24h = ticker.get("percentage", 0)

    # Multi-timeframe OHLCV
    timeframes = {
        "15m": 96,   # 24 hours of 15m candles
        "1h": 72,     # 3 days of 1h candles
        "4h": 42,     # 7 days of 4h candles
        "1d": 30,     # 30 days
    }

    klines = {}
    for tf, limit in timeframes.items():
        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        klines[tf] = df

    # Technical Analysis
    ta = calculate_indicators(klines)

    # Volatility assessment
    vol_15m = volatility_assessment(klines["15m"])
    vol_1h = volatility_assessment(klines["1h"])

    result = {
        "symbol": symbol,
        "current_price": current_price,
        "change_24h_pct": round(change_24h, 2),
        "timestamp": datetime.now().isoformat(),
        "timeframes": {
            tf: {
                "latest_close": float(df["close"].iloc[-1]),
                "latest_volume": float(df["volume"].iloc[-1]),
                "high_24h": float(df["high"].max()) if tf in ["15m", "1h"] else None,
                "low_24h": float(df["low"].min()) if tf in ["15m", "1h"] else None,
            }
            for tf, df in klines.items()
        },
        "technical_indicators": ta,
        "volatility": {
            "15m": vol_15m,
            "1h": vol_1h,
            "daily_volatility_pct": round(vol_1h.get("daily_estimate", 0), 2),
            "status": classify_volatility(vol_1h),
        },
        "market_tone": analyze_market_tone(klines, ta),
    }

    return result

def calculate_indicators(klines):
    """Calculate technical indicators across timeframes"""
    results = {}

    for tf, df in klines.items():
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values

        r = {}

        # Moving Averages
        if len(close) >= 7:
            r["MA7"] = float(np.mean(close[-7:]))
        if len(close) >= 25:
            r["MA25"] = float(np.mean(close[-25:]))
        if len(close) >= 99:
            r["MA99"] = float(np.mean(close[-99:]))

        # Price position relative to MA
        current = float(close[-1])
        if "MA7" in r and "MA25" in r:
            r["price_vs_MA7"] = round((current / r["MA7"] - 1) * 100, 2)
            r["price_vs_MA25"] = round((current / r["MA25"] - 1) * 100, 2)
            # Trend direction
            if current > r["MA7"] > r["MA25"]:
                r["trend"] = "bullish"
            elif current < r["MA7"] < r["MA25"]:
                r["trend"] = "bearish"
            elif current > r["MA7"] and current < r["MA25"]:
                r["trend"] = "mixed_short_up"
            elif current < r["MA7"] and current > r["MA25"]:
                r["trend"] = "mixed_short_down"
            else:
                r["trend"] = "neutral"

        # RSI (14 periods)
        if len(close) >= 15:
            deltas = np.diff(close[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            r["RSI"] = round(rsi, 1)
            if rsi > 70:
                r["rsi_signal"] = "overbought"
            elif rsi < 30:
                r["rsi_signal"] = "oversold"
            else:
                r["rsi_signal"] = "neutral"

        # MACD
        if len(close) >= 26:
            ema12 = pd.Series(close).ewm(span=12).mean().values[-1]
            ema26 = pd.Series(close).ewm(span=26).mean().values[-1]
            macd_line = ema12 - ema26
            signal = pd.Series(close).ewm(span=9).mean().values[-1]
            # Quick signal line from MACD
            macd_values = pd.Series(close).ewm(span=12).mean() - pd.Series(close).ewm(span=26).mean()
            signal_line = macd_values.ewm(span=9).mean().values[-1]
            histogram = macd_line - signal_line
            r["MACD"] = {
                "macd_line": round(float(macd_line), 2),
                "signal_line": round(float(signal_line), 2),
                "histogram": round(float(histogram), 2),
            }
            if macd_line > signal_line and histogram > 0:
                r["macd_signal"] = "bullish"
            elif macd_line < signal_line and histogram < 0:
                r["macd_signal"] = "bearish"
            else:
                r["macd_signal"] = "neutral"

        # Bollinger Bands (20 periods)
        if len(close) >= 20:
            bb_period = 20
            recent = close[-bb_period:]
            bb_mean = np.mean(recent)
            bb_std = np.std(recent)
            upper = bb_mean + 2 * bb_std
            lower = bb_mean - 2 * bb_std
            r["bollinger"] = {
                "upper": round(float(upper), 2),
                "middle": round(float(bb_mean), 2),
                "lower": round(float(lower), 2),
                "bandwidth": round((upper - lower) / bb_mean * 100, 2),
            }
            if current > upper:
                r["bollinger_signal"] = "above_upper"
            elif current < lower:
                r["bollinger_signal"] = "below_lower"
            else:
                r["bollinger_signal"] = "within_bands"

        # Volume analysis
        if len(volume) >= 10:
            avg_vol = np.mean(volume[-10:-5])
            recent_vol = np.mean(volume[-5:])
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
            r["volume_ratio"] = round(float(vol_ratio), 2)
            if vol_ratio > 1.5:
                r["volume_signal"] = "high_volume"
            elif vol_ratio < 0.5:
                r["volume_signal"] = "low_volume"
            else:
                r["volume_signal"] = "normal"

        # ATR (14 periods) for volatility
        if len(close) >= 15:
            trs = []
            for i in range(1, 15):
                tr = max(high[-i] - low[-i],
                         abs(high[-i] - close[-i-1]),
                         abs(low[-i] - close[-i-1]))
                trs.append(tr)
            atr = np.mean(trs)
            r["ATR"] = round(float(atr), 2)
            r["ATR_pct"] = round(float(atr / current * 100), 2)

        # SuperTrend indicator (ATR period=10, multiplier=3 - standard setting)
        if len(close) >= 11:
            supertrend = calculate_supertrend(high, low, close, period=10, multiplier=3)
            r["supertrend"] = {
                "trend": supertrend["trend"],
                "value": round(float(supertrend["value"]), 2),
                "distance_pct": round(float((current / supertrend["value"] - 1) * 100), 2),
            }

        results[tf] = r

    return results

def calculate_supertrend(high, low, close, period=10, multiplier=3):
    """Calculate SuperTrend indicator.
    Returns current trend direction and the super trend line value.
    """
    length = len(close)
    # Calculate True Range
    tr = np.zeros(length)
    for i in range(1, length):
        tr[i] = max(high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1]))
    tr[0] = high[0] - low[0]

    # ATR using Wilder's smoothing (SMA then EMA-like)
    atr = np.zeros(length)
    atr[0] = np.mean(tr[:period]) if length >= period else tr[0]
    for i in range(1, min(length, 50)):
        if i < period:
            atr[i] = np.mean(tr[:i+1])
        else:
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    # Basic bands
    hl_avg = (high + low) / 2
    upper_band = hl_avg + multiplier * atr
    lower_band = hl_avg - multiplier * atr

    # SuperTrend logic
    supertrend = np.zeros(length)
    direction = np.ones(length)  # 1 = uptrend, -1 = downtrend

    for i in range(1, length):
        if close[i] > upper_band[i]:
            direction[i] = 1
        elif close[i] < lower_band[i]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]

        if direction[i] == 1:
            supertrend[i] = max(lower_band[i], supertrend[i-1] if i > 0 else lower_band[i])
        else:
            supertrend[i] = min(upper_band[i], supertrend[i-1] if i > 0 else upper_band[i])

    current_direction = direction[-1]
    return {
        "trend": "up" if current_direction == 1 else "down",
        "value": supertrend[-1],
        "direction_change": direction[-1] != direction[-2] if length >= 2 else False,
    }


def volatility_assessment(df):
    """Assess volatility from a dataframe"""
    if len(df) < 5:
        return {"status": "insufficient_data"}

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values

    # Price range volatility
    ranges = highs - lows
    avg_range = np.mean(ranges[-20:]) if len(ranges) >= 20 else np.mean(ranges)
    current_range = ranges[-1] if len(ranges) > 0 else 0

    current_price = closes[-1]
    avg_range_pct = avg_range / current_price * 100

    # Standard deviation of returns
    n = min(20, len(closes) - 1)
    if n >= 2:
        returns = np.diff(closes[-n-1:]) / closes[-n-1:-1] * 100
    else:
        returns = np.array([0.0])
    std_returns = np.std(returns) if len(returns) > 0 else 0

    # Direction
    if len(closes) >= 2:
        direction = "up" if closes[-1] > closes[0] else ("down" if closes[-1] < closes[0] else "flat")
    else:
        direction = "flat"

    return {
        "avg_candle_range_pct": round(float(avg_range_pct), 2),
        "current_candle_range_pct": round(float(current_range / current_price * 100), 2),
        "return_std_pct": round(float(std_returns), 2),
        "direction": direction,
        "daily_estimate": round(float(avg_range_pct * (24 if len(df) < 100 else 1)), 2),
    }

def classify_volatility(vol):
    """Classify volatility level"""
    daily_est = vol.get("daily_estimate", 0)
    if daily_est < 1.5:
        return "very_low"
    elif daily_est < 3:
        return "low"
    elif daily_est < 5:
        return "normal"
    elif daily_est < 8:
        return "elevated"
    elif daily_est < 12:
        return "high"
    else:
        return "extreme"

def analyze_market_tone(klines, indicators):
    """Overall market tone assessment"""
    scores = []

    # Check trend alignment across timeframes
    for tf in ["15m", "1h", "4h"]:
        ti = indicators.get(tf, {})
        trend = ti.get("trend", "neutral")
        if trend == "bullish":
            scores.append(1)
        elif trend == "bearish":
            scores.append(-1)
        else:
            scores.append(0)

    avg_score = np.mean(scores) if scores else 0
    if avg_score > 0.3:
        return "bullish"
    elif avg_score < -0.3:
        return "bearish"
    else:
        return "neutral"

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ETH/USDT"
    data = fetch_market_data(symbol)
    print(json.dumps(data, indent=2))
