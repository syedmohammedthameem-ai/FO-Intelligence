import requests
import finnhub
import logging
from datetime import datetime, timedelta
from config import NEWS_API_KEY, FINNHUB_API_KEY

logger = logging.getLogger(__name__)


def fetch_newsapi(query: str, days_back: int = 1) -> list:
    """Fetch articles from NewsAPI.org."""
    if not NEWS_API_KEY:
        return []
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        return [
            {
                "title": a["title"],
                "source": a["source"]["name"],
                "url": a["url"],
                "published": a["publishedAt"],
                "description": a.get("description", ""),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
    except Exception as e:
        logger.warning(f"NewsAPI error: {e}")
        return []


def fetch_finnhub_news(category: str = "general") -> list:
    """Fetch market news from Finnhub (free tier)."""
    if not FINNHUB_API_KEY:
        return []
    try:
        client = finnhub.Client(api_key=FINNHUB_API_KEY)
        news = client.general_news(category, min_id=0)
        return [
            {
                "title": n["headline"],
                "source": n["source"],
                "url": n["url"],
                "published": datetime.fromtimestamp(n["datetime"]).isoformat(),
                "description": n.get("summary", ""),
            }
            for n in news[:15]
        ]
    except Exception as e:
        logger.warning(f"Finnhub news error: {e}")
        return []


def fetch_india_market_news() -> list:
    """Aggregate Indian market news from multiple free sources."""
    queries = [
        "NIFTY stock market India",
        "NSE BSE India market",
        "RBI interest rate India",
        "FII DII India market",
    ]
    articles = []
    for q in queries:
        articles.extend(fetch_newsapi(q, days_back=1))
    # Deduplicate by URL
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique[:20]


def fetch_global_news() -> list:
    """Fetch global macro news (Fed, inflation, geopolitics)."""
    queries = ["Federal Reserve interest rate", "global inflation economy 2024", "US stock market"]
    articles = []
    for q in queries:
        articles.extend(fetch_newsapi(q, days_back=1))
    finnhub_articles = fetch_finnhub_news("general")
    articles.extend(finnhub_articles)
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique[:15]


def fetch_stock_news(symbol: str) -> list:
    """Fetch news for a specific stock symbol."""
    return fetch_newsapi(f"{symbol} NSE India stock", days_back=2)
