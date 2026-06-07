import time
import logging
import pytz
import yfinance as yf
from datetime import datetime

IST = pytz.timezone("Asia/Kolkata")
from data.nse_data import get_nifty_option_chain, parse_option_chain, get_pcr
from data.stock_scanner import _fetch_history, compute_volume_spike
from data.forex_data import get_usdinr
from data.news_fetcher import fetch_india_market_news, fetch_global_news
from analysis.ai_narrator import generate_intraday_suggestion
from alerts.telegram_bot import (
    alert_volume_spike, alert_pcr_extreme, alert_news_event,
    alert_usdinr_level, alert_iv_spike,
)
from config import FNO_STOCKS, NIFTY_YF

logger = logging.getLogger(__name__)

_last_pcr_alert = 0.0
_alerted_volume = set()
_alerted_news = set()
_last_usdinr_alert = 0.0
_last_news_check = None


def _is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def check_pcr_alert():
    global _last_pcr_alert
    try:
        raw = get_nifty_option_chain()
        df = parse_option_chain(raw)
        if df.empty:
            return
        pcr = get_pcr(df)
        nifty_df = yf.download(NIFTY_YF, period="1d", interval="1m", progress=False)
        spot = float(nifty_df["Close"].iloc[-1]) if not nifty_df.empty else 0

        if (pcr > 1.4 or pcr < 0.65) and _last_pcr_alert != round(pcr, 1):
            ai = generate_intraday_suggestion("pcr_extreme", {"pcr": pcr, "spot": spot})
            alert_pcr_extreme(pcr, spot, ai_suggestion=ai)
            _last_pcr_alert = round(pcr, 1)

    except Exception as e:
        logger.error(f"PCR check error: {e}")


def check_volume_spikes():
    try:
        for symbol in FNO_STOCKS[:20]:  # check top 20 to stay within rate limits
            if symbol in _alerted_volume:
                continue
            df = _fetch_history(symbol, period="30d", interval="1d")
            if df.empty:
                continue
            vol_data = compute_volume_spike(df)
            spike = vol_data["spike_ratio"]
            if spike >= 3.0:  # 3x spike → immediate alert
                close = float(df["close"].iloc[-1])
                prev = float(df["close"].iloc[-2])
                change_pct = round((close / prev - 1) * 100, 2)

                # Compute RSI for richer AI context
                rsi = None
                try:
                    delta = df["close"].diff()
                    gain = delta.clip(lower=0).rolling(14).mean()
                    loss = (-delta.clip(upper=0)).rolling(14).mean()
                    rs = gain / (loss + 1e-9)
                    rsi = round(float((100 - 100 / (1 + rs)).iloc[-1]), 1)
                except Exception:
                    pass

                ai = generate_intraday_suggestion("volume_spike", {
                    "symbol": symbol, "spike_ratio": spike,
                    "price": close, "change_pct": change_pct, "rsi": rsi,
                })
                alert_volume_spike(symbol, spike, close, change_pct, ai_suggestion=ai)
                _alerted_volume.add(symbol)
    except Exception as e:
        logger.error(f"Volume spike check error: {e}")


def check_news_alerts():
    global _last_news_check
    try:
        now = datetime.now(IST)
        if _last_news_check and (now - _last_news_check).seconds < 1800:
            return  # only check news every 30 mins
        _last_news_check = now

        articles = fetch_india_market_news() + fetch_global_news()
        for a in articles:
            url = a.get("url", "")
            if url in _alerted_news:
                continue
            from analysis.news_sentiment import score_article
            scored = score_article(a)
            if abs(scored["score"]) >= 0.5:  # only strong sentiment news
                ai = generate_intraday_suggestion("news_event", {
                    "headline": scored["title"][:120],
                    "sentiment": scored["sentiment"],
                })
                alert_news_event(
                    scored["title"][:100],
                    scored["sentiment"],
                    scored["source"],
                    ai_suggestion=ai,
                )
                _alerted_news.add(url)
    except Exception as e:
        logger.error(f"News alert check error: {e}")


def check_usdinr_alert():
    global _last_usdinr_alert
    try:
        data = get_usdinr()
        if not data:
            return
        rate = data.get("rate", 0)
        change_pct = data.get("change_pct", 0)

        key_levels = [83.0, 83.5, 84.0, 84.5, 85.0, 85.5, 86.0]
        for level in key_levels:
            if abs(rate - level) < 0.05 and abs(_last_usdinr_alert - level) > 0.1:
                direction = "WEAKENING" if change_pct > 0 else "STRENGTHENING"
                ai = generate_intraday_suggestion("usdinr_break", {
                    "rate": rate, "level": level, "direction": direction,
                })
                alert_usdinr_level(rate, level, direction, ai_suggestion=ai)
                _last_usdinr_alert = level
                break
    except Exception as e:
        logger.error(f"USD/INR check error: {e}")


def run_realtime_monitor(interval_seconds: int = 300):
    """
    Main real-time monitor loop. Runs every 5 minutes during market hours.
    Checks: PCR extremes, volume spikes, news, USD/INR key levels.
    """
    logger.info("Real-time monitor started.")
    while True:
        if _is_market_open():
            logger.info("Market open — running checks...")
            check_pcr_alert()
            check_volume_spikes()
            check_news_alerts()
            check_usdinr_alert()
        else:
            logger.info("Market closed — monitor idle.")
        time.sleep(interval_seconds)
