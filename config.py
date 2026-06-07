import os
from dotenv import load_dotenv

load_dotenv()

# Claude AI (optional — enables AI narrative in alerts and EOD report)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Broker
ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
ANGEL_API_KEY = os.getenv("ANGEL_API_KEY")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")
ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD")

# News
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Email
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT", GMAIL_USER)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Capital limits
FNO_BUDGET = int(os.getenv("FNO_BUDGET", 100000))
SHORT_TERM_BUDGET = int(os.getenv("SHORT_TERM_BUDGET", 175000))
LONG_TERM_BUDGET = int(os.getenv("LONG_TERM_BUDGET", 175000))

# Market schedule (IST)
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
EOD_REPORT_TIME = "16:00"  # 4 PM — after close, before EOD data

# NSE F&O universe (top liquid stocks)
FNO_STOCKS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "AXISBANK", "KOTAKBANK", "LT", "ITC",
    "BAJFINANCE", "MARUTI", "TATAMOTORS", "WIPRO", "HCLTECH",
    "SUNPHARMA", "DRREDDY", "DIVISLAB", "CIPLA", "ADANIENT",
    "ADANIPORTS", "TATASTEEL", "JSWSTEEL", "HINDUNILVR", "NESTLEIND",
    "BRITANNIA", "ASIANPAINT", "ULTRACEMCO", "SHREECEM", "GRASIM",
    "TITAN", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "M&M",
    "ONGC", "BPCL", "IOC", "POWERGRID", "NTPC",
    "COALINDIA", "VEDL", "HINDALCO", "TECHM", "MPHASIS",
]

# NIFTY index tickers
NIFTY_SYMBOL = "NIFTY"
NIFTY_YF = "^NSEI"
BANKNIFTY_YF = "^NSEBANK"

# Global indices for macro context
GLOBAL_INDICES = {
    "Dow Jones": "^DJI",
    "Nasdaq": "^IXIC",
    "S&P 500": "^GSPC",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "FTSE 100": "^FTSE",
    "SGX Nifty": "SGX:SIN",
}

# Commodities
GOLD_YF = "GC=F"       # Gold futures
CRUDE_YF = "CL=F"      # Crude oil
USDINR_YF = "INR=X"    # USD/INR

# Scanning thresholds
VOLUME_SPIKE_MULTIPLIER = 2.0   # Volume > 2x 20-day avg
ATR_PERIOD = 14
VOLUME_MA_PERIOD = 20
IV_HIGH_PERCENTILE = 70          # Alert if IV > 70th percentile
IV_LOW_PERCENTILE = 30           # Alert if IV < 30th percentile (sell premium opportunity)
