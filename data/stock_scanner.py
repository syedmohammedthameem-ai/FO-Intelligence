import yfinance as yf
import pandas as pd
import numpy as np
import logging
from config import FNO_STOCKS, VOLUME_SPIKE_MULTIPLIER, VOLUME_MA_PERIOD, ATR_PERIOD

logger = logging.getLogger(__name__)


def _fetch_history(symbol: str, period: str = "60d", interval: str = "1d") -> pd.DataFrame:
    ticker = f"{symbol}.NS"
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        df.columns = [c.lower() for c in df.columns]
        return df.dropna()
    except Exception as e:
        logger.warning(f"yfinance error for {symbol}: {e}")
        return pd.DataFrame()


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def compute_volume_spike(df: pd.DataFrame) -> dict:
    avg_vol = df["volume"].rolling(VOLUME_MA_PERIOD).mean().iloc[-1]
    latest_vol = df["volume"].iloc[-1]
    spike_ratio = latest_vol / avg_vol if avg_vol > 0 else 0
    return {"avg_volume": avg_vol, "latest_volume": latest_vol, "spike_ratio": round(spike_ratio, 2)}


def compute_momentum_score(df: pd.DataFrame) -> float:
    """
    Score 0-100 combining:
    - 5d / 20d price momentum
    - Volume spike
    - ATR expansion (volatility increasing)
    - RSI proximity to 50 (trending, not exhausted)
    """
    if len(df) < 25:
        return 0.0

    close = df["close"]
    mom_5 = (close.iloc[-1] / close.iloc[-6] - 1) * 100
    mom_20 = (close.iloc[-1] / close.iloc[-21] - 1) * 100
    vol_data = compute_volume_spike(df)
    vol_score = min(vol_data["spike_ratio"] / VOLUME_SPIKE_MULTIPLIER, 2.0) * 25

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi_val = float(rsi.iloc[-1]) if not rsi.empty else 50

    # RSI between 45-65 gets max score (trending, not overbought/oversold)
    rsi_score = max(0, 25 - abs(rsi_val - 55))

    mom_score = min(max(mom_5 * 2 + mom_20, 0), 25)
    atr_score = min(compute_atr(df) / float(close.iloc[-1]) * 1000, 25)

    return round(min(vol_score + rsi_score + mom_score + atr_score, 100), 1)


def scan_fno_stocks() -> pd.DataFrame:
    """
    Scan all NSE F&O stocks and return ranked list by opportunity score.
    Filters: volume spike > 2x, returns top candidates.
    """
    results = []
    for symbol in FNO_STOCKS:
        df = _fetch_history(symbol)
        if df.empty or len(df) < 25:
            continue

        vol_data = compute_volume_spike(df)
        score = compute_momentum_score(df)
        close = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2])
        change_pct = round((close / prev_close - 1) * 100, 2)
        atr = compute_atr(df)

        results.append({
            "symbol": symbol,
            "ltp": round(close, 2),
            "change_pct": change_pct,
            "volume_spike": vol_data["spike_ratio"],
            "avg_volume": int(vol_data["avg_volume"]),
            "latest_volume": int(vol_data["latest_volume"]),
            "atr": round(atr, 2),
            "atr_pct": round(atr / close * 100, 2),
            "momentum_score": score,
        })

    df_result = pd.DataFrame(results)
    if df_result.empty:
        return df_result

    # Filter: volume spike > threshold, sort by score
    df_result = df_result[df_result["volume_spike"] >= VOLUME_SPIKE_MULTIPLIER]
    df_result = df_result.sort_values("momentum_score", ascending=False).reset_index(drop=True)
    return df_result


def get_short_term_setups(df_scanned: pd.DataFrame, budget: int) -> list:
    """
    Generate aggressive short-term trade setups (1-5 days) from scanned stocks.
    Returns list of trade dicts with entry, SL, target, lot_size.
    """
    setups = []
    for _, row in df_scanned.head(5).iterrows():
        hist = _fetch_history(row["symbol"])
        if hist.empty:
            continue

        close = row["ltp"]
        atr = row["atr"]
        direction = "BUY" if row["change_pct"] > 0 else "SELL"

        if direction == "BUY":
            entry = round(close * 1.002, 2)       # slight buffer above current
            sl = round(close - 1.5 * atr, 2)
            target1 = round(close + 2 * atr, 2)
            target2 = round(close + 3.5 * atr, 2)
        else:
            entry = round(close * 0.998, 2)
            sl = round(close + 1.5 * atr, 2)
            target1 = round(close - 2 * atr, 2)
            target2 = round(close - 3.5 * atr, 2)

        qty = max(1, int(budget / close))
        risk = abs(entry - sl) * qty

        setups.append({
            "symbol": row["symbol"],
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "target1": target1,
            "target2": target2,
            "qty": qty,
            "risk_amount": round(risk, 0),
            "risk_reward": round(abs(target1 - entry) / abs(entry - sl), 2),
            "hold_days": "1-5 days",
            "score": row["momentum_score"],
            "volume_spike": row["volume_spike"],
            "reasoning": f"Volume {row['volume_spike']}x spike with {row['change_pct']}% move. ATR expansion suggests momentum continuation.",
        })

    return setups


def get_long_term_candidates(budget: int) -> list:
    """
    Long-term candidates (weeks–months): stable uptrend, fundamentally sound.
    Uses 20/50 EMA cross + volume confirmation as filter.
    """
    candidates = []
    for symbol in FNO_STOCKS:
        df = _fetch_history(symbol, period="200d")
        if df.empty or len(df) < 60:
            continue

        close = df["close"]
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()

        # Must be in uptrend: price > EMA20 > EMA50
        if not (close.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1]):
            continue

        # EMA recently crossed (within 10 days)
        recent_cross = (ema20.iloc[-10:] > ema50.iloc[-10:]).all() and \
                       not (ema20.iloc[-20:-10] > ema50.iloc[-20:-10]).all()

        vol_data = compute_volume_spike(df)
        atr = compute_atr(df)
        ltp = float(close.iloc[-1])
        change_pct = round((ltp / float(close.iloc[-2]) - 1) * 100, 2)

        score = 0
        if recent_cross:
            score += 40
        if vol_data["spike_ratio"] > 1.5:
            score += 20
        if ltp > float(ema20.iloc[-1]):
            score += 20
        if change_pct > 0:
            score += 20

        if score >= 40:
            sl = round(float(ema50.iloc[-1]) * 0.98, 2)
            target = round(ltp + 4 * atr, 2)
            qty = max(1, int(budget / ltp))
            candidates.append({
                "symbol": symbol,
                "direction": "BUY",
                "entry": round(ltp * 1.001, 2),
                "sl": sl,
                "target": target,
                "qty": qty,
                "hold": "4-12 weeks",
                "score": score,
                "ema20": round(float(ema20.iloc[-1]), 2),
                "ema50": round(float(ema50.iloc[-1]), 2),
                "reasoning": f"Price above EMA20 > EMA50 structure. {'Fresh EMA cross detected.' if recent_cross else ''} Volume {vol_data['spike_ratio']}x avg.",
            })

    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:5]
