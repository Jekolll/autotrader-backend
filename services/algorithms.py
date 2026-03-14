# services/algorithms.py
# ── 4 Algoritma teknikal dalam satu file ──────────────────────
# Setiap algo return: {"signal": "BUY"|"SELL"|"HOLD", "score": float, "reason": str}

import numpy as np
from dataclasses import dataclass
from typing import Literal

Signal = Literal["BUY", "SELL", "HOLD"]


# ── helpers ───────────────────────────────────────────────────

def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    if len(arr) < period:
        return np.full(len(arr), np.nan)
    out = np.empty(len(arr)); out[:] = np.nan
    k = 2 / (period + 1)
    out[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out

def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1: return 50.0
    d = np.diff(closes)
    g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = np.mean(g[:period]); al = np.mean(l[:period])
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + g[i]) / period
        al = (al * (period - 1) + l[i]) / period
    return round(100 - 100 / (1 + ag / al), 2) if al else 100.0

def _atr(highs, lows, closes, period=14) -> float:
    tr = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
          for i in range(1, len(highs))]
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr)) if tr else 0.0


# ── Algoritma 1: RSI + MACD (Momentum) ───────────────────────

def algo_rsi_macd(closes: np.ndarray) -> dict:
    rsi_val = _rsi(closes)

    # MACD
    ef = _ema(closes, 12); es = _ema(closes, 26)
    line = ef - es
    valid = line[~np.isnan(line)]
    if len(valid) < 9:
        return {"signal": "HOLD", "score": 0.0, "reason": "Data MACD kurang"}
    sig  = _ema(valid, 9)
    hist = float(valid[-1] - sig[-1])
    macd = float(valid[-1])
    sval = float(sig[-1])

    score = 0.0; reasons = []

    # RSI scoring
    if rsi_val <= 30:   score += 1.0;  reasons.append(f"RSI oversold ({rsi_val})")
    elif rsi_val >= 70: score -= 1.0;  reasons.append(f"RSI overbought ({rsi_val})")
    elif rsi_val < 45:  score += 0.3;  reasons.append(f"RSI lemah ({rsi_val})")
    elif rsi_val > 55:  score -= 0.3;  reasons.append(f"RSI kuat ({rsi_val})")

    # MACD scoring
    if macd > sval and hist > 0:   score += 1.0; reasons.append("MACD bullish crossover")
    elif macd < sval and hist < 0: score -= 1.0; reasons.append("MACD bearish crossover")
    elif hist > 0:                 score += 0.4; reasons.append("MACD histogram +")
    elif hist < 0:                 score -= 0.4; reasons.append("MACD histogram -")

    norm  = score / 2.0
    signal = "BUY" if norm >= 0.4 else "SELL" if norm <= -0.4 else "HOLD"
    return {"signal": signal, "score": round(norm, 3), "reason": " | ".join(reasons) or "RSI+MACD netral"}


# ── Algoritma 2: EMA Crossover (Trend Following) ─────────────

def algo_ema_crossover(closes: np.ndarray) -> dict:
    e21  = _ema(closes, 21)
    e50  = _ema(closes, 50)
    e200 = _ema(closes, 200)

    if np.isnan(e21[-1]) or np.isnan(e50[-1]) or np.isnan(e200[-1]):
        return {"signal": "HOLD", "score": 0.0, "reason": "Data EMA kurang"}

    # Cek crossover di 2 candle terakhir
    cross_up   = e21[-2] <= e50[-2] and e21[-1] > e50[-1]
    cross_down = e21[-2] >= e50[-2] and e21[-1] < e50[-1]
    above_200  = closes[-1] > e200[-1]

    score = 0.0; reasons = []

    if cross_up:
        score += 1.0; reasons.append("EMA21 cross up EMA50")
    elif e21[-1] > e50[-1]:
        score += 0.5; reasons.append("EMA21 di atas EMA50")

    if cross_down:
        score -= 1.0; reasons.append("EMA21 cross down EMA50")
    elif e21[-1] < e50[-1]:
        score -= 0.5; reasons.append("EMA21 di bawah EMA50")

    if above_200:  score += 0.3; reasons.append("Harga di atas EMA200")
    else:          score -= 0.3; reasons.append("Harga di bawah EMA200")

    norm   = max(-1.0, min(1.0, score / 1.3))
    signal = "BUY" if norm >= 0.4 else "SELL" if norm <= -0.4 else "HOLD"
    return {"signal": signal, "score": round(norm, 3), "reason": " | ".join(reasons)}


# ── Algoritma 3: Bollinger Bands (Volatility) ─────────────────

def algo_bollinger(closes: np.ndarray) -> dict:
    if len(closes) < 20:
        return {"signal": "HOLD", "score": 0.0, "reason": "Data BB kurang"}

    w      = closes[-20:]
    mid    = float(np.mean(w))
    std    = float(np.std(w))
    upper  = mid + 2 * std
    lower  = mid - 2 * std
    price  = closes[-1]
    prev   = closes[-2]

    score = 0.0; reasons = []

    # Bandwidth — ukur volatilitas
    bw = (upper - lower) / mid

    if price <= lower:
        score += 1.0; reasons.append(f"Harga sentuh BB bawah ({price:.5f})")
    elif price >= upper:
        score -= 1.0; reasons.append(f"Harga sentuh BB atas ({price:.5f})")
    elif price < mid:
        score += 0.3; reasons.append("Harga di bawah BB tengah")
    elif price > mid:
        score -= 0.3; reasons.append("Harga di atas BB tengah")

    # Konfirmasi: apakah harga mulai berbalik dari band?
    if prev <= lower and price > lower: score += 0.5; reasons.append("Bounce dari BB bawah")
    if prev >= upper and price < upper: score -= 0.5; reasons.append("Bounce dari BB atas")

    norm   = max(-1.0, min(1.0, score / 1.5))
    signal = "BUY" if norm >= 0.4 else "SELL" if norm <= -0.4 else "HOLD"
    return {"signal": signal, "score": round(norm, 3), "reason": " | ".join(reasons) or "BB netral"}


# ── Algoritma 4: Support & Resistance ─────────────────────────

def algo_support_resistance(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> dict:
    if len(closes) < 50:
        return {"signal": "HOLD", "score": 0.0, "reason": "Data S&R kurang"}

    price   = closes[-1]
    lookback = closes[-50:]
    h50      = highs[-50:]
    l50      = lows[-50:]

    # Identifikasi level S&R dari pivot highs/lows
    resistance = float(np.percentile(h50, 85))
    support    = float(np.percentile(l50, 15))
    zone       = (resistance - support) * 0.1   # 10% dari range = "zone"

    score = 0.0; reasons = []

    near_support    = abs(price - support)    <= zone
    near_resistance = abs(price - resistance) <= zone
    broke_resistance = price > resistance
    broke_support    = price < support

    if near_support:
        score += 0.8; reasons.append(f"Dekat support {support:.5f}")
    if near_resistance:
        score -= 0.8; reasons.append(f"Dekat resistance {resistance:.5f}")
    if broke_resistance:
        score += 1.0; reasons.append(f"Breakout resistance {resistance:.5f}")
    if broke_support:
        score -= 1.0; reasons.append(f"Breakdown support {support:.5f}")

    norm   = max(-1.0, min(1.0, score))
    signal = "BUY" if norm >= 0.4 else "SELL" if norm <= -0.4 else "HOLD"
    return {"signal": signal, "score": round(norm, 3), "reason": " | ".join(reasons) or "S&R netral"}


# ── Gabungkan semua algoritma ─────────────────────────────────

@dataclass
class FinalSignal:
    symbol:      str
    action:      Signal
    confidence:  float
    entry_price: float
    stop_loss:   float
    take_profit: float
    reasons:     dict   # per-algo breakdown


def combine(
    symbol:  str,
    closes:  np.ndarray,
    highs:   np.ndarray,
    lows:    np.ndarray,
    price:   float,
    point:   float = 0.00001,
    rr:      float = 2.0,
) -> FinalSignal:
    """
    Jalankan 4 algo, weighted average → keputusan final.
    Algo punya bobot sama (0.25 masing-masing).
    """
    results = {
        "RSI+MACD":   algo_rsi_macd(closes),
        "EMA Cross":  algo_ema_crossover(closes),
        "Bollinger":  algo_bollinger(closes),
        "S&R":        algo_support_resistance(highs, lows, closes),
    }

    # weighted average score
    total  = sum(r["score"] for r in results.values()) / len(results)
    conf   = round(min(abs(total), 1.0), 2)

    # ATR untuk SL/TP
    atr_val = _atr(highs, lows, closes)
    sl_dist = max(atr_val * 1.5, point * 100)
    tp_dist = sl_dist * rr

    if total >= 0.25:
        action = "BUY"
        sl = round(price - sl_dist, 5)
        tp = round(price + tp_dist, 5)
    elif total <= -0.25:
        action = "SELL"
        sl = round(price + sl_dist, 5)
        tp = round(price - tp_dist, 5)
    else:
        action = "HOLD"
        sl = tp = 0.0

    return FinalSignal(
        symbol      = symbol,
        action      = action,
        confidence  = conf,
        entry_price = price,
        stop_loss   = sl,
        take_profit = tp,
        reasons     = {k: v["reason"] for k, v in results.items()},
    )
