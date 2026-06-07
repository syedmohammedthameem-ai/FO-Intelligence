import asyncio
import logging
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


async def _send(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping alert.")
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Telegram send error: {e}")


def send_alert(text: str):
    """Sync wrapper — fire and forget."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_send(text))
        else:
            loop.run_until_complete(_send(text))
    except RuntimeError:
        asyncio.run(_send(text))


def _append_ai(base: str, ai_suggestion: str) -> str:
    if not ai_suggestion:
        return base
    return f"{base}\n\n🤖 <b>AI Trade Idea:</b>\n{ai_suggestion}"


def alert_volume_spike(symbol: str, spike_ratio: float, price: float, change_pct: float, ai_suggestion: str = ""):
    msg = (
        f"⚡ <b>VOLUME SPIKE — {symbol}</b>\n"
        f"Volume: <b>{spike_ratio:.1f}x</b> above average\n"
        f"LTP: ₹{price:,.2f}  ({change_pct:+.2f}%)"
    )
    send_alert(_append_ai(msg, ai_suggestion))


def alert_iv_spike(symbol: str, iv: float, iv_rank: float):
    send_alert(
        f"📈 <b>IV SPIKE — {symbol}</b>\n"
        f"ATM IV: <b>{iv:.1f}%</b>  |  IV Rank: <b>{iv_rank:.0f}%</b>\n"
        f"High IV → Consider selling premium strategies."
    )


def alert_pcr_extreme(pcr: float, nifty_spot: float, ai_suggestion: str = ""):
    if pcr > 1.3:
        msg = (
            f"🔻 <b>PCR EXTREME HIGH — {pcr:.2f}</b>\n"
            f"NIFTY: {nifty_spot:,.0f}\n"
            f"Market deeply oversold on puts — watch for bounce."
        )
    else:
        msg = (
            f"🔺 <b>PCR EXTREME LOW — {pcr:.2f}</b>\n"
            f"NIFTY: {nifty_spot:,.0f}\n"
            f"Market overbought on calls — potential reversal zone."
        )
    send_alert(_append_ai(msg, ai_suggestion))


def alert_news_event(headline: str, sentiment: str, source: str, ai_suggestion: str = ""):
    emoji = "🟢" if "BULL" in sentiment else ("🔴" if "BEAR" in sentiment else "🟡")
    msg = (
        f"{emoji} <b>NEWS ALERT ({sentiment})</b>\n"
        f"{headline}\n"
        f"<i>Source: {source}</i>"
    )
    send_alert(_append_ai(msg, ai_suggestion))


def alert_oi_buildup(symbol: str, strike: int, option_type: str, oi_change: float, direction: str):
    send_alert(
        f"👁 <b>OI BUILDUP — {symbol} {strike} {option_type}</b>\n"
        f"OI Change: <b>{oi_change:+,.0f}</b> contracts\n"
        f"Signal: {direction}"
    )


def alert_usdinr_level(rate: float, level: float, direction: str, ai_suggestion: str = ""):
    msg = (
        f"💱 <b>USD/INR LEVEL BREAK</b>\n"
        f"Rate: ₹{rate:.4f}  |  Key Level: ₹{level:.2f}\n"
        f"Direction: <b>{direction}</b>\n"
        f"Impact: IT exporters {'↑' if direction == 'WEAKENING' else '↓'}  "
        f"Oil importers {'↑' if direction == 'STRENGTHENING' else '↓'}"
    )
    send_alert(_append_ai(msg, ai_suggestion))


def send_market_open_summary(nifty_spot: float, sgx_change_pct: float, sentiment: str):
    send_alert(
        f"🔔 <b>MARKET OPEN — {nifty_spot:,.0f}</b>\n"
        f"News Sentiment: <b>{sentiment}</b>\n"
        f"Global cue: {sgx_change_pct:+.2f}%\n"
        f"Full report in your email by 4:00 PM IST."
    )


def send_eod_summary(nifty_close: float, change_pct: float, pcr: float, strategy: str):
    emoji = "🟢" if change_pct >= 0 else "🔴"
    send_alert(
        f"{emoji} <b>MARKET CLOSE — NIFTY {nifty_close:,.0f} ({change_pct:+.2f}%)</b>\n"
        f"PCR: {pcr:.2f}  |  Suggested: <b>{strategy}</b>\n"
        f"📊 Full PDF report sent to your email."
    )
