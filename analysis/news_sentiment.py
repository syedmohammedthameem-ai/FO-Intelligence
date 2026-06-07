import re
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()

# Finance-specific word boosters for VADER
FINANCE_BOOSTER = {
    "rally": 2.0, "surge": 2.0, "soar": 2.0, "bull": 1.5, "breakout": 1.5,
    "crash": -2.5, "plunge": -2.5, "selloff": -2.0, "sell-off": -2.0,
    "bear": -1.5, "recession": -2.0, "default": -2.0, "rate hike": -1.5,
    "rate cut": 1.5, "stimulus": 1.5, "inflation": -1.0, "gdp growth": 1.5,
    "fii buying": 1.5, "fii selling": -1.5, "dii buying": 1.0, "dii selling": -1.0,
    "rbi hike": -1.5, "rbi cut": 1.5, "strong earnings": 2.0, "profit miss": -2.0,
    "upgrade": 1.5, "downgrade": -1.5, "ban": -1.5, "fraud": -2.5,
}

_analyzer.lexicon.update(FINANCE_BOOSTER)


def score_article(article: dict) -> dict:
    text = (article.get("title", "") + " " + article.get("description", "")).strip()
    scores = _analyzer.polarity_scores(text)
    compound = scores["compound"]

    if compound >= 0.2:
        label = "BULLISH"
        emoji = "↑"
    elif compound <= -0.2:
        label = "BEARISH"
        emoji = "↓"
    else:
        label = "NEUTRAL"
        emoji = "→"

    return {**article, "sentiment": label, "emoji": emoji, "score": round(compound, 3)}


def analyze_news_batch(articles: list) -> dict:
    """
    Score a batch of articles.
    Returns: scored list + aggregate sentiment summary.
    """
    if not articles:
        return {"articles": [], "aggregate": "NEUTRAL", "avg_score": 0.0, "bullish_pct": 0}

    scored = [score_article(a) for a in articles]
    avg = sum(a["score"] for a in scored) / len(scored)
    bullish = sum(1 for a in scored if a["sentiment"] == "BULLISH")
    bearish = sum(1 for a in scored if a["sentiment"] == "BEARISH")

    if avg >= 0.15:
        aggregate = "BULLISH"
    elif avg <= -0.15:
        aggregate = "BEARISH"
    else:
        aggregate = "NEUTRAL"

    return {
        "articles": scored,
        "aggregate": aggregate,
        "avg_score": round(avg, 3),
        "bullish_pct": round(bullish / len(scored) * 100, 0),
        "bearish_pct": round(bearish / len(scored) * 100, 0),
    }


def get_market_sentiment_from_news(india_news: list, global_news: list) -> dict:
    india_result = analyze_news_batch(india_news)
    global_result = analyze_news_batch(global_news)

    # Weighted: India news 60%, Global 40%
    combined_score = india_result["avg_score"] * 0.6 + global_result["avg_score"] * 0.4

    if combined_score >= 0.15:
        overall = "BULLISH"
    elif combined_score <= -0.15:
        overall = "BEARISH"
    else:
        overall = "NEUTRAL"

    return {
        "overall": overall,
        "combined_score": round(combined_score, 3),
        "india": india_result,
        "global": global_result,
    }
