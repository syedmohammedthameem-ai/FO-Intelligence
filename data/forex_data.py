import yfinance as yf
import pandas as pd
import logging
from config import GOLD_YF, CRUDE_YF, USDINR_YF, GLOBAL_INDICES

logger = logging.getLogger(__name__)


def _safe_download(ticker: str, period: str = "5d") -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        df.columns = [c.lower() for c in df.columns]
        return df.dropna()
    except Exception as e:
        logger.warning(f"Failed to fetch {ticker}: {e}")
        return pd.DataFrame()


def get_usdinr() -> dict:
    df = _safe_download(USDINR_YF)
    if df.empty:
        return {}
    ltp = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2])
    change = round(ltp - prev, 4)
    change_pct = round(change / prev * 100, 3)
    weekly_high = float(df["high"].max())
    weekly_low = float(df["low"].min())

    signal = ""
    if change_pct > 0.3:
        signal = "RUPEE WEAKENING — bearish for import-heavy sectors (Oil, Gold importers). Positive for IT exporters."
    elif change_pct < -0.3:
        signal = "RUPEE STRENGTHENING — positive for importers, mild negative for IT exporters."
    else:
        signal = "RUPEE STABLE — neutral macro impact."

    return {
        "rate": ltp,
        "change": change,
        "change_pct": change_pct,
        "weekly_high": weekly_high,
        "weekly_low": weekly_low,
        "signal": signal,
    }


def get_gold() -> dict:
    df = _safe_download(GOLD_YF)
    if df.empty:
        return {}
    ltp = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2])
    change_pct = round((ltp / prev - 1) * 100, 2)

    signal = ""
    if change_pct > 0.5:
        signal = "GOLD RISING — risk-off sentiment. Watch for NIFTY weakness, buy GOLDBEES/SGOLD."
    elif change_pct < -0.5:
        signal = "GOLD FALLING — risk-on. Equities may rally. Consider NIFTY calls."
    else:
        signal = "GOLD NEUTRAL — no clear macro signal from gold today."

    return {
        "price_usd": round(ltp, 2),
        "change_pct": change_pct,
        "signal": signal,
    }


def get_crude() -> dict:
    df = _safe_download(CRUDE_YF)
    if df.empty:
        return {}
    ltp = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2])
    change_pct = round((ltp / prev - 1) * 100, 2)

    signal = ""
    if change_pct > 1:
        signal = "CRUDE RISING — inflationary pressure. Negative for ONGC/BPCL margins. Watch INR depreciation."
    elif change_pct < -1:
        signal = "CRUDE FALLING — positive for India (import savings). Bullish for aviation, paints, logistics."
    else:
        signal = "CRUDE STABLE."

    return {"price_usd": round(ltp, 2), "change_pct": change_pct, "signal": signal}


def get_global_indices() -> list:
    results = []
    for name, ticker in GLOBAL_INDICES.items():
        if ticker.startswith("SGX:"):
            continue  # SGX not on yfinance, skip
        df = _safe_download(ticker, period="2d")
        if df.empty or len(df) < 2:
            continue
        ltp = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        change_pct = round((ltp / prev - 1) * 100, 2)
        results.append({"index": name, "value": round(ltp, 2), "change_pct": change_pct})
    return results


def get_macro_summary() -> dict:
    return {
        "usdinr": get_usdinr(),
        "gold": get_gold(),
        "crude": get_crude(),
        "global_indices": get_global_indices(),
    }
