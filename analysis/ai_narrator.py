import logging
import os

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import Anthropic
            key = os.getenv("ANTHROPIC_API_KEY", "")
            if not key:
                return None
            _client = Anthropic(api_key=key)
        except ImportError:
            logger.warning("anthropic package not installed — AI narrative disabled.")
            return None
    return _client


def generate_intraday_suggestion(trigger_type: str, data: dict) -> str:
    """
    Generate a concise, actionable trade suggestion for a real-time intraday alert.
    Returns empty string if ANTHROPIC_API_KEY is not set (graceful degradation).

    trigger_type: 'volume_spike' | 'pcr_extreme' | 'news_event' | 'usdinr_break'
    """
    client = _get_client()
    if not client:
        return ""

    symbol = data.get("symbol", "")
    prompts = {
        "volume_spike": (
            f"You are a sharp F&O trader giving a real-time intraday alert.\n"
            f"Stock: {symbol} | LTP: ₹{data.get('price')} | Change: {data.get('change_pct')}%\n"
            f"Volume Spike: {data.get('spike_ratio')}x above 20-day average | RSI: {data.get('rsi', 'N/A')}\n\n"
            f"Give a 3-line trade call:\n"
            f"1. Direction and one-line reasoning from volume/price action\n"
            f"2. Specific entry zone + stop loss level\n"
            f"3. Target for 2-3 days\n"
            f"Be direct and specific. Max 65 words."
        ),
        "pcr_extreme": (
            f"You are a sharp NIFTY F&O trader giving a real-time alert.\n"
            f"NIFTY Spot: {data.get('spot', 0):,.0f} | PCR: {data.get('pcr')} | Max Pain: {data.get('max_pain', 'N/A')}\n\n"
            f"Give a 3-line NIFTY options call:\n"
            f"1. What the PCR signals about market bias\n"
            f"2. Specific strategy name + strike levels + expiry (weekly/monthly)\n"
            f"3. Entry zone and stop loss\n"
            f"Max 65 words."
        ),
        "news_event": (
            f"Breaking market news — give a sharp 2-line trade reaction:\n"
            f"Headline: {data.get('headline')}\n"
            f"Sentiment: {data.get('sentiment')}\n\n"
            f"Line 1: Which sectors or stocks are most impacted and how.\n"
            f"Line 2: One specific trade to act on this news with entry and stop.\n"
            f"Max 45 words."
        ),
        "usdinr_break": (
            f"USD/INR key level break alert:\n"
            f"Rate: ₹{data.get('rate')} | Level Broken: ₹{data.get('level')} | Direction: {data.get('direction')}\n\n"
            f"Line 1: Which stocks benefit or get hurt (IT exporters / oil importers / banks).\n"
            f"Line 2: One specific trade entry with stock name, entry price zone, and stop loss.\n"
            f"Max 45 words."
        ),
    }

    prompt = prompts.get(trigger_type, "")
    if not prompt:
        return ""

    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"AI intraday narrator error ({trigger_type}): {e}")
        return ""


def generate_eod_narrative(data: dict) -> str:
    """
    Generate a comprehensive AI market brief for the EOD PDF report.
    Uses adaptive thinking for deeper analysis.
    Returns empty string if ANTHROPIC_API_KEY is not set.
    """
    client = _get_client()
    if not client:
        return ""

    nifty = data.get("nifty", {})
    news = data.get("news_sentiment", {})
    macro = data.get("macro", {})
    short_term = data.get("short_term", [])
    long_term = data.get("long_term", [])
    tech = nifty.get("technicals", {})

    st_list = ", ".join([f"{t['symbol']} ({t['direction']})" for t in short_term[:5]]) or "None"
    lt_list = ", ".join([t["symbol"] for t in long_term[:3]]) or "None"

    prompt = (
        "You are a professional F&O market analyst. Write a concise daily market brief based on real data.\n\n"
        f"NIFTY: {nifty.get('spot', 0):,.0f} | Trend: {nifty.get('trend', 'N/A')} | "
        f"RSI: {tech.get('rsi', 0):.1f} | Change: {tech.get('change_pct', 0):+.2f}%\n"
        f"EMA20: {tech.get('ema20', 0):,.0f} | EMA50: {tech.get('ema50', 0):,.0f} | "
        f"EMA200: {tech.get('ema200', 0):,.0f}\n"
        f"PCR: {nifty.get('pcr', 0):.3f} | IV Rank: {nifty.get('iv_rank', 0):.1f}% | "
        f"Max Pain: {nifty.get('max_pain', 0):,.0f}\n"
        f"OI Support: {nifty.get('oi_support', [])} | OI Resistance: {nifty.get('oi_resistance', [])}\n"
        f"Suggested Strategy: {nifty.get('suggested_strategy', {}).get('name', 'N/A')}\n"
        f"USD/INR: {macro.get('usdinr', {}).get('rate', 0):.4f} | "
        f"Gold: ${macro.get('gold', {}).get('price_usd', 0):.2f} | "
        f"Crude: ${macro.get('crude', {}).get('price_usd', 0):.2f}\n"
        f"Market Sentiment: {news.get('overall', 'NEUTRAL')} (score: {news.get('combined_score', 0):+.3f})\n"
        f"Short-term setups flagged: {st_list}\n"
        f"Long-term candidates: {lt_list}\n\n"
        "Write exactly 4 labelled paragraphs:\n\n"
        "**Market Summary:** What today's data tells us. Key levels to watch tomorrow.\n"
        "**NIFTY F&O View:** Specific options trade for tomorrow — strategy name, exact strikes, "
        "weekly or monthly expiry, entry zone, stop loss.\n"
        "**Top Stock Plays:** Why the flagged short-term picks make sense given today's volume/momentum data.\n"
        "**Key Risk:** One specific macro or technical factor that could invalidate these setups.\n\n"
        "Rules: Each paragraph 2-3 sentences. Specific numbers, not vague statements. Total ~200 words."
    )

    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=700,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n\n".join(text_blocks).strip()
    except Exception as e:
        logger.error(f"AI EOD narrative error: {e}")
        return ""
