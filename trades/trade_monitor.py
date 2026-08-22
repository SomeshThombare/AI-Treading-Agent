"""
trades/trade_monitor.py
The core "AI" logic of the trading agent.

This module:
  1. Fetches open trades from the database
  2. Gets current prices for each symbol
  3. Checks if TP or SL has been hit
  4. Closes trades automatically when conditions are met
  5. Optionally detects simple trend signals

Rule-based logic (no ML needed):
  - IF price >= take_profit  → close trade as PROFIT
  - IF price <= stop_loss    → close trade as LOSS
  - Simple moving average trend detection (bonus)
"""

import logging
from decimal import Decimal
from django.utils import timezone

# Imported at top level so ALL functions (check, process, close) can use Trade
from .models import Trade
from .price_service import get_prices_for_symbols

logger = logging.getLogger(__name__)


def check_and_close_trades():
    """
    Main monitoring function.
    Call this in a loop (from management command) to continuously monitor trades.

    Returns: dict with summary of what happened this cycle.
    """

    summary = {
        'checked': 0,
        'closed_tp': 0,
        'closed_sl': 0,
        'errors': 0,
    }

    # Get all open trades from database
    open_trades = Trade.objects.filter(status=Trade.STATUS_OPEN)

    if not open_trades.exists():
        logger.info("No open trades to monitor.")
        return summary

    # Get unique symbols to minimize price API calls
    symbols = list(open_trades.values_list('symbol', flat=True).distinct())
    logger.info(f"Monitoring {open_trades.count()} open trades for symbols: {symbols}")

    # Fetch current prices for all symbols at once
    current_prices = get_prices_for_symbols(symbols)

    # Check each trade
    for trade in open_trades:
        summary['checked'] += 1
        try:
            _process_trade(trade, current_prices)
        except Exception as e:
            logger.error(f"Error processing trade #{trade.id}: {e}")
            summary['errors'] += 1

    # Refresh to count closed trades
    closed_tp = Trade.objects.filter(status=Trade.STATUS_CLOSED_TP).count()
    closed_sl = Trade.objects.filter(status=Trade.STATUS_CLOSED_SL).count()

    return summary


def _process_trade(trade, current_prices: dict):
    """
    Check a single trade against current prices and close if conditions are met.

    Args:
        trade: Trade model instance
        current_prices: dict of {symbol: price}
    """
    symbol = trade.symbol
    price = current_prices.get(symbol)

    if price is None:
        logger.warning(f"No price available for {symbol}, skipping trade #{trade.id}")
        return

    current_price = Decimal(str(price))

    # Update current price in database (for dashboard display)
    trade.current_price = current_price
    trade.save(update_fields=['current_price'])

    logger.debug(
        f"Trade #{trade.id} | {symbol} | "
        f"Entry: {trade.entry_price} | Current: {current_price} | "
        f"TP: {trade.take_profit} | SL: {trade.stop_loss}"
    )

    # ---- RULE 1: Take Profit Hit ----
    if current_price >= trade.take_profit:
        close_trade(trade, Trade.STATUS_CLOSED_TP, current_price)
        logger.info(f"✅ TAKE PROFIT hit! Trade #{trade.id} | {symbol} @ {current_price}")

    # ---- RULE 2: Stop Loss Hit ----
    elif current_price <= trade.stop_loss:
        close_trade(trade, Trade.STATUS_CLOSED_SL, current_price)
        logger.info(f"❌ STOP LOSS hit! Trade #{trade.id} | {symbol} @ {current_price}")


def close_trade(trade, current_price, status_code):
    """Close a trade and update stats."""
    from django.utils import timezone
    from decimal import Decimal
    
    trade.current_price = Decimal(str(current_price))
    trade.status        = status_code
    trade.closed_at     = timezone.now()
    
    # Calculate PnL %
    # entry = float(trade.entry_price)
    # close = float(current_price)
    # pnl   = ((close - entry) / entry) * 100
    # trade.pnl = round(Decimal(str(pnl)), 4)
    # trade.save()
    
    entry = float(trade.entry_price)
    close = float(current_price)

    # Store PnL in DOLLARS (price difference)
    pnl_dollars = close - entry
    trade.pnl = round(Decimal(str(pnl_dollars)), 4)
    
    
    # ── ADD THIS: Update bot stats if it was bot-opened ──
    try:
        from .auto_agent import update_bot_stats_on_close
        update_bot_stats_on_close(trade.user, trade.symbol, status_code)
    except Exception as e:
        import logging
        logging.error(f"Failed to update bot stats: {e}")

# ---------------------------------------------------------------------------
# BONUS: Simple Trend Detection using Moving Average
# This is basic AI/signal logic — not required to run the system.
# ---------------------------------------------------------------------------

# Store price history for moving average calculation
_price_history = {}
MOVING_AVERAGE_PERIOD = 10  # Use last 10 prices


def update_price_history(symbol: str, price: float):
    """Add a new price to the history buffer for this symbol."""
    if symbol not in _price_history:
        _price_history[symbol] = []

    _price_history[symbol].append(price)

    # Keep only the last N prices
    if len(_price_history[symbol]) > MOVING_AVERAGE_PERIOD * 2:
        _price_history[symbol] = _price_history[symbol][-MOVING_AVERAGE_PERIOD * 2:]


def get_trend_signal(symbol: str) -> str:
    """
    Simple trend detection using two moving averages.
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'

    Logic:
      - Calculate short MA (last 5 prices)
      - Calculate long MA (last 10 prices)
      - If short MA > long MA → price is trending UP → BULLISH
      - If short MA < long MA → price is trending DOWN → BEARISH

    NOTE: This is a very basic signal. In real trading, you would use
    more sophisticated indicators (RSI, MACD, Bollinger Bands, etc.)
    """
    history = _price_history.get(symbol, [])

    SHORT_PERIOD = 5
    LONG_PERIOD = MOVING_AVERAGE_PERIOD

    if len(history) < LONG_PERIOD:
        return 'NEUTRAL'  # Not enough data yet

    short_ma = sum(history[-SHORT_PERIOD:]) / SHORT_PERIOD
    long_ma  = sum(history[-LONG_PERIOD:])  / LONG_PERIOD

    if short_ma > long_ma * 1.001:   # Short MA is 0.1% above long MA
        return 'BULLISH'
    elif short_ma < long_ma * 0.999:  # Short MA is 0.1% below long MA
        return 'BEARISH'
    else:
        return 'NEUTRAL'