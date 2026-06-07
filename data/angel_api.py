import pyotp
import logging
from SmartApi import SmartConnect
from config import ANGEL_CLIENT_ID, ANGEL_API_KEY, ANGEL_TOTP_SECRET, ANGEL_PASSWORD

logger = logging.getLogger(__name__)

_smart_api = None


def get_angel_session() -> SmartConnect:
    global _smart_api
    if _smart_api:
        return _smart_api

    try:
        obj = SmartConnect(api_key=ANGEL_API_KEY)
        totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
        session = obj.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
        if session["status"]:
            _smart_api = obj
            logger.info("Angel One session established")
            return obj
        else:
            raise ConnectionError(f"Angel One login failed: {session}")
    except Exception as e:
        logger.error(f"Angel One session error: {e}")
        raise


def get_option_chain(symbol: str, expiry_date: str, strike_price: float, option_type: str = "CE") -> dict:
    """Fetch option chain data for a symbol."""
    api = get_angel_session()
    try:
        data = api.getOptionChain(symbol, expiry_date, strike_price, 10)
        return data.get("data", {})
    except Exception as e:
        logger.error(f"Option chain fetch error for {symbol}: {e}")
        return {}


def get_ltp(exchange: str, symbol: str, token: str) -> float:
    """Get last traded price."""
    api = get_angel_session()
    try:
        data = api.ltpData(exchange, symbol, token)
        return float(data["data"]["ltp"])
    except Exception as e:
        logger.error(f"LTP fetch error for {symbol}: {e}")
        return 0.0


def get_market_data(exchange: str, token: str, interval: str = "ONE_DAY", from_date: str = "", to_date: str = "") -> list:
    """Fetch OHLCV historical data."""
    api = get_angel_session()
    try:
        params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_date,
            "todate": to_date,
        }
        data = api.getCandleData(params)
        return data.get("data", [])
    except Exception as e:
        logger.error(f"Market data fetch error: {e}")
        return []


def reset_session():
    global _smart_api
    _smart_api = None
