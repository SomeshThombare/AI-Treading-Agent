"""
trades/price_service.py
Combined price service — MT5 + Binance.
Updated to support XM Broker symbol names (GOLD, SILVER).
"""

import logging
import requests
import random

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
#  Symbol Classification
# ─────────────────────────────────────────────────────

BINANCE_SYMBOLS = {
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT',
    'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'MATICUSDT',
    'LTCUSDT', 'DOTUSDT', 'AVAXUSDT', 'LINKUSDT',
    'UNIUSDT', 'SHIBUSDT', 'ATOMUSDT', 'NEARUSDT',
}

MT5_SYMBOLS = {
    # Forex Major Pairs
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD',
    'USDCAD', 'USDCHF', 'NZDUSD', 'EURGBP',
    'EURJPY', 'GBPJPY', 'AUDJPY', 'EURAUD',
    # Commodities — standard names
    'XAUUSD', 'XAGUSD', 'XTIUSD', 'XBRUSD',
    # Commodities — XM Broker names
    'GOLD', 'SILVER', 'OIL',
}

# XM Broker alternate symbol names
# When standard name fails, try these alternatives
ALTERNATE_NAMES = {
    'XAUUSD': ['XAUUSD', 'GOLD'],
    'XAGUSD': ['SILVER', 'XAGUSD'],
    'GOLD':   ['GOLD', 'XAUUSD'],
    'SILVER': ['SILVER', 'XAGUSD'],
    'XTIUSD': ['XTIUSD', 'OIL', 'OILUSD'],
    'XBRUSD': ['XBRUSD', 'BRENT'],
}

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"
TIMEOUT     = 5

MOCK_PRICES = {
    'BTCUSDT':  (60000, 70000),
    'ETHUSDT':  (3000,  4000),
    'BNBUSDT':  (400,   600),
    'SOLUSDT':  (150,   200),
    'XRPUSDT':  (0.5,   0.7),
    'DOGEUSDT': (0.10,  0.20),
    'EURUSD':   (1.05,  1.15),
    'GBPUSD':   (1.20,  1.35),
    'USDJPY':   (145,   155),
    'AUDUSD':   (0.63,  0.70),
    'USDCAD':   (1.33,  1.40),
    'USDCHF':   (0.88,  0.95),
    'XAUUSD':   (2200,  2500),
    'GOLD':     (2200,  2500),
    'XAGUSD':   (25,    32),
    'SILVER':   (25,    32),
    'XTIUSD':   (70,    90),
}

_last_mock     = {}
_price_history = {}
HISTORY_LIMIT  = 50


# ─────────────────────────────────────────────────────
#  Main Function
# ─────────────────────────────────────────────────────

def get_live_price(symbol: str) -> float | None:
    """
    Get live price for any symbol.
    Auto-detects correct API based on symbol type.
    """
    symbol = symbol.upper()

    if symbol in BINANCE_SYMBOLS:
        price = _get_binance_price(symbol)
    elif symbol in MT5_SYMBOLS:
        price = _get_mt5_price(symbol)
    else:
        logger.warning(f"Unknown symbol {symbol} — trying Binance first")
        price = _get_binance_price(symbol)
        if not price:
            price = _get_mt5_price(symbol)

    if price is None:
        logger.warning(f"Both APIs failed for {symbol} — using mock price")
        price = _get_mock_price(symbol)

    if price:
        _update_history(symbol, price)

    return price


def get_prices_for_symbols(symbols: list) -> dict:
    """Fetch prices for multiple symbols at once."""
    prices = {}
    for symbol in set(symbols):
        price = get_live_price(symbol)
        if price is not None:
            prices[symbol] = price
    return prices


# ─────────────────────────────────────────────────────
#  Binance API — Crypto
# ─────────────────────────────────────────────────────

def _get_binance_price(symbol: str) -> float | None:
    """Fetch live crypto price from Binance public API."""
    try:
        response = requests.get(
            BINANCE_URL,
            params={'symbol': symbol},
            timeout=TIMEOUT
        )
        if response.status_code == 200:
            price = float(response.json()['price'])
            logger.debug(f"[BINANCE] {symbol} = ${price:,.4f}")
            return round(price, 6)
        elif response.status_code == 400:
            logger.warning(f"[BINANCE] Invalid symbol: {symbol}")
            return None
        else:
            logger.warning(f"[BINANCE] Error {response.status_code} for {symbol}")
            return None
    except requests.exceptions.ConnectionError:
        logger.warning(f"[BINANCE] No internet for {symbol}")
        return None
    except requests.exceptions.Timeout:
        logger.warning(f"[BINANCE] Timeout for {symbol}")
        return None
    except Exception as e:
        logger.error(f"[BINANCE] Error for {symbol}: {e}")
        return None


# ─────────────────────────────────────────────────────
#  MT5 API — Forex + Gold + Commodities
# ─────────────────────────────────────────────────────

def _get_mt5_price(symbol: str) -> float | None:
    """
    Fetch live price from MT5 terminal.
    Automatically tries XM broker alternate names.

    XM Broker uses:
      GOLD   instead of XAUUSD
      SILVER instead of XAGUSD
    """
    try:
        import MetaTrader5 as mt5

        if not mt5.initialize():
            logger.warning(f"[MT5] Cannot connect: {mt5.last_error()}")
            return None

        # Get list of names to try for this symbol
        names_to_try = ALTERNATE_NAMES.get(symbol, [symbol])

        for name in names_to_try:
            # Enable symbol in Market Watch
            mt5.symbol_select(name, True)

            tick = mt5.symbol_info_tick(name)
            if tick is not None:
                price = float(tick.ask)
                logger.debug(f"[MT5] {symbol} ({name}) = {price}")
                mt5.shutdown()
                return round(price, 6)

        logger.warning(f"[MT5] Symbol {symbol} not found on broker")
        mt5.shutdown()
        return None

    except ImportError:
        logger.warning("[MT5] MetaTrader5 not installed")
        return None
    except Exception as e:
        logger.error(f"[MT5] Error for {symbol}: {e}")
        return None


# ─────────────────────────────────────────────────────
#  Mock Price — fallback
# ─────────────────────────────────────────────────────

def _get_mock_price(symbol: str) -> float | None:
    """Generate realistic mock price when APIs unavailable."""
    price_range = MOCK_PRICES.get(symbol)

    if not price_range:
        logger.warning(f"[MOCK] No range for {symbol}")
        return round(random.uniform(1, 1000), 4)

    low, high = price_range

    if symbol not in _last_mock:
        _last_mock[symbol] = random.uniform(low, high)

    last      = _last_mock[symbol]
    change    = random.uniform(-0.015, 0.015)
    new_price = max(low, min(high, last * (1 + change)))
    _last_mock[symbol] = new_price
    return round(new_price, 6)


# ─────────────────────────────────────────────────────
#  Price History — trend detection
# ─────────────────────────────────────────────────────

def _update_history(symbol: str, price: float):
    """Store price in history buffer."""
    if symbol not in _price_history:
        _price_history[symbol] = []
    _price_history[symbol].append(price)
    if len(_price_history[symbol]) > HISTORY_LIMIT:
        _price_history[symbol] = _price_history[symbol][-HISTORY_LIMIT:]


def get_price_history(symbol: str) -> list:
    """Return stored price history for a symbol."""
    return _price_history.get(symbol.upper(), [])


def get_trend_signal(symbol: str) -> str:
    """
    Simple dual moving average trend detection.
    Returns: BULLISH / BEARISH / NEUTRAL
    """
    symbol  = symbol.upper()
    history = get_price_history(symbol)

    SHORT = 5
    LONG  = 20

    if len(history) < LONG:
        return 'NEUTRAL'

    short_ma = sum(history[-SHORT:]) / SHORT
    long_ma  = sum(history[-LONG:])  / LONG

    if short_ma > long_ma * 1.001:
        return 'BULLISH'
    elif short_ma < long_ma * 0.999:
        return 'BEARISH'
    return 'NEUTRAL'


def update_price_history(symbol: str, price: float):
    """Public wrapper to update price history."""
    _update_history(symbol.upper(), price)


# ─────────────────────────────────────────────────────
#  Symbol Type Helper
# ─────────────────────────────────────────────────────

def get_symbol_type(symbol: str) -> str:
    """
    Returns market type for a symbol.
    CRYPTO / FOREX / COMMODITY / UNKNOWN
    """
    symbol = symbol.upper()
    if symbol in BINANCE_SYMBOLS:
        return 'CRYPTO'
    elif symbol in {'XAUUSD', 'XAGUSD', 'XTIUSD', 'XBRUSD',
                    'GOLD', 'SILVER', 'OIL'}:
        return 'COMMODITY'
    elif symbol in MT5_SYMBOLS:
        return 'FOREX'
    return 'UNKNOWN'