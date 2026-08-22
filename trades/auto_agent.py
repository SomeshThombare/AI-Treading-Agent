"""
trades/auto_agent.py
Core Auto Trading Agent Logic.
Bot now opens BUY/SELL based on AI direction and uses fixed quantity/amount.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

# Scan priority — Gold first (highest accuracy), then Forex, then Crypto
SYMBOL_PRIORITY = [
    'XAUUSD',
    'EURUSD', 'GBPUSD', 'USDJPY',
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT',
    'SOLUSDT', 'XRPUSDT', 'DOGEUSDT',
]

# Market type per symbol
SYMBOL_MARKET = {
    'BTCUSDT': 'CRYPTO', 'ETHUSDT': 'CRYPTO',
    'BNBUSDT': 'CRYPTO', 'SOLUSDT': 'CRYPTO',
    'XRPUSDT': 'CRYPTO', 'DOGEUSDT': 'CRYPTO',
    'EURUSD':  'FOREX',  'GBPUSD':  'FOREX',
    'USDJPY':  'FOREX',  'AUDUSD':  'FOREX',
    'XAUUSD':  'GOLD',   'XAGUSD':  'GOLD',
}


def run_agent_cycle(user):
    """
    Run one complete scan cycle for a user's bot.
    Called every 15 minutes by run_auto_agent command.
    """
    from trades.models import AgentConfig, Trade

    logger.info(f"[BOT] Starting cycle for {user.username}")

    # Load config
    try:
        config = AgentConfig.objects.get(user=user)
    except AgentConfig.DoesNotExist:
        logger.warning(f"[BOT] No AgentConfig for {user.username}")
        return

    # Check bot is active
    if not config.is_active:
        return

    # Reset daily counter if new day
    _reset_daily_counter_if_needed(config)

    # Check daily loss limit
    if config.daily_loss_count >= config.daily_loss_limit:
        _log(user, 'PAUSE', '',
             f'Daily loss limit reached ({config.daily_loss_count} losses). '
             f'Bot paused until tomorrow.')
        logger.info(f"[BOT] {user.username}: Daily loss limit reached")
        return

    # Check max open trades
    open_count = Trade.objects.filter(
        user=user,
        status=Trade.STATUS_OPEN
    ).count()

    if open_count >= config.max_open_trades:
        logger.info(f"[BOT] {user.username}: Max trades reached ({open_count})")
        return

    # Get symbols to scan in priority order
    selected = config.selected_symbols or []
    symbols_to_scan = [s for s in SYMBOL_PRIORITY if s in selected]

    if not symbols_to_scan:
        logger.info(f"[BOT] {user.username}: No symbols selected")
        return

    logger.info(f"[BOT] {user.username}: Scanning {symbols_to_scan}")
    _log(user, 'SCAN', '',
         f'Scanning {len(symbols_to_scan)} symbols: {", ".join(symbols_to_scan)}')

    # Scan each symbol
    for symbol in symbols_to_scan:
        # Re-check open count after each trade opened
        open_count = Trade.objects.filter(
            user=user,
            status=Trade.STATUS_OPEN
        ).count()
        if open_count >= config.max_open_trades:
            break

        _scan_symbol(user, config, symbol)


def _scan_symbol(user, config, symbol):
    """
    Check one symbol and open trade if all conditions pass.
    """
    from trades.models import Trade
    from trades.ml.predictor import get_ai_suggestion
    from trades.price_service import get_live_price

    market_type = SYMBOL_MARKET.get(symbol, 'CRYPTO')

    # Skip forex/gold on weekends
    if market_type in ('FOREX', 'GOLD') and _is_weekend():
        _log(user, 'SKIP', symbol, 'Market closed on weekend')
        return

    # Check cooldown after recent loss
    if _is_in_cooldown(user, symbol, config.cooldown_minutes):
        _log(user, 'SKIP', symbol, 'In cooldown period after recent loss')
        return

    # Check if already have open trade for this symbol
    already_open = Trade.objects.filter(
        user=user,
        symbol=symbol,
        status=Trade.STATUS_OPEN
    ).exists()

    if already_open:
        _log(user, 'SKIP', symbol, f'Already have open trade for {symbol}')
        return

    # Diversification: max 1 trade per market type
    market_symbols = [s for s, m in SYMBOL_MARKET.items() if m == market_type]
    same_market_open = Trade.objects.filter(
        user=user,
        status=Trade.STATUS_OPEN,
        symbol__in=market_symbols
    ).count()

    if same_market_open >= 1:
        _log(user, 'SKIP', symbol,
             f'Already have a {market_type} trade open (diversification rule)')
        return

    # Get AI prediction
    try:
        suggestion = get_ai_suggestion(symbol)
    except Exception as e:
        _log(user, 'ERROR', symbol, f'AI prediction failed: {str(e)}')
        return

    if not suggestion.get('model_ready'):
        _log(user, 'SKIP', symbol,
             f'AI model not trained yet. Run: python manage.py train_models --symbol {symbol}')
        return

    direction  = suggestion['direction']    # 'UP' / 'DOWN' / 'NEUTRAL'
    confidence = suggestion['confidence']
    tp_percent = suggestion['tp_percent']
    sl_percent = suggestion['sl_percent']

    # Skip NEUTRAL — bot only trades on a clear UP or DOWN signal
    if direction not in ('UP', 'DOWN'):
        _log(user, 'SKIP', symbol,
             f'AI signal is NEUTRAL — no clear direction',
             direction=direction, confidence=confidence)
        return

    # Get min confidence for this market type
    min_conf = _get_min_confidence(config, market_type)

    # Check confidence threshold
    if confidence < min_conf:
        _log(user, 'SKIP', symbol,
             f'Confidence {confidence}% is below threshold {min_conf}%',
             direction=direction, confidence=confidence)
        return

    # Get live price
    price = get_live_price(symbol)
    if not price:
        _log(user, 'ERROR', symbol, f'Could not fetch live price for {symbol}')
        return

    # All checks passed — open the trade!
    _open_trade(user, config, symbol, price,
                direction, confidence, tp_percent, sl_percent)


def _open_trade(user, config, symbol, price,
                direction, confidence, tp_percent, sl_percent):
    """
    Create a new trade in the database automatically.
    UP   -> BUY  trade (TP above entry, SL below)
    DOWN -> SELL trade (TP below entry, SL above)
    Uses fixed quantity & amount from bot strategy settings.
    """
    from trades.models import Trade

    entry  = Decimal(str(price))
    tp_pct = Decimal(str(tp_percent))
    sl_pct = Decimal(str(sl_percent))

    # Map AI direction -> trade direction
    if direction == 'DOWN':
        trade_direction = Trade.DIRECTION_SELL
        # SELL: TP below entry, SL above entry
        take_profit = entry * (1 - tp_pct / Decimal('100'))
        stop_loss   = entry * (1 + sl_pct / Decimal('100'))
    else:
        trade_direction = Trade.DIRECTION_BUY
        # BUY: TP above entry, SL below entry
        take_profit = entry * (1 + tp_pct / Decimal('100'))
        stop_loss   = entry * (1 - sl_pct / Decimal('100'))

    # Fixed sizing from bot strategy settings
    bot_quantity = config.bot_fixed_quantity
    bot_amount   = config.bot_fixed_amount

    trade = Trade.objects.create(
        user          = user,
        symbol        = symbol,
        direction     = trade_direction,
        quantity      = bot_quantity,
        amount        = bot_amount,
        entry_price   = entry,
        take_profit   = round(take_profit, 6),
        stop_loss     = round(stop_loss,   6),
        tp_percent    = tp_pct,
        sl_percent    = sl_pct,
        current_price = entry,
        status        = Trade.STATUS_OPEN,
    )

    # Update bot stats
    config.total_bot_trades += 1
    config.save(update_fields=['total_bot_trades'])

    _log(user, 'OPEN', symbol,
         f'Opened {trade_direction} trade #{trade.id} | '
         f'AI: {direction} ({confidence}% confidence) | '
         f'Qty: {bot_quantity} | Amount: ${bot_amount} | '
         f'Entry: ${price:.4f} | TP: {tp_percent}% | SL: {sl_percent}%',
         direction=direction, confidence=confidence)

    logger.info(
        f"[BOT] {user.username}: Opened {symbol} {trade_direction} trade #{trade.id} "
        f"| AI={direction} conf={confidence}%"
    )


def update_bot_stats_on_close(user, symbol, trade_status):
    """
    Called when a bot trade closes.
    Updates win/loss counters.
    """
    from trades.models import AgentConfig

    try:
        config = AgentConfig.objects.get(user=user)
    except AgentConfig.DoesNotExist:
        return

    if trade_status == 'CLOSED_TP':
        config.total_bot_wins += 1
        _log(user, 'CLOSE', symbol,
             f'Trade closed — TAKE PROFIT hit ✅ (WIN)')
    elif trade_status == 'CLOSED_SL':
        config.total_bot_losses += 1
        config.daily_loss_count += 1
        _log(user, 'CLOSE', symbol,
             f'Trade closed — STOP LOSS hit ❌ (LOSS) | '
             f'Cooldown started for {config.cooldown_minutes} min | CLOSED_SL')

    config.save(update_fields=[
        'total_bot_wins', 'total_bot_losses', 'daily_loss_count'
    ])


# ── Helper Functions ──────────────────────────────────────────────

def _log(user, action, symbol, message, direction='', confidence=None):
    """Write entry to bot activity log."""
    from trades.models import BotLog
    try:
        BotLog.objects.create(
            user       = user,
            action     = action,
            symbol     = symbol,
            message    = message,
            direction  = direction,
            confidence = confidence,
        )
    except Exception as e:
        logger.error(f"[BOT] Log write failed: {e}")


def _is_weekend():
    """Returns True if today is Saturday or Sunday."""
    return datetime.now().weekday() >= 5


def _is_in_cooldown(user, symbol, cooldown_minutes):
    """
    Check if symbol is in cooldown after recent Stop Loss.
    Looks for recent CLOSED_SL log entry for this symbol.
    """
    from trades.models import BotLog
    cutoff = timezone.now() - timedelta(minutes=cooldown_minutes)

    return BotLog.objects.filter(
        user              = user,
        symbol            = symbol,
        action            = 'CLOSE',
        message__contains = 'CLOSED_SL',
        timestamp__gte    = cutoff
    ).exists()


def _get_min_confidence(config, market_type):
    """Get minimum confidence threshold for this market type."""
    if market_type == 'CRYPTO':
        return config.min_confidence_crypto
    elif market_type == 'FOREX':
        return config.min_confidence_forex
    elif market_type == 'GOLD':
        return config.min_confidence_gold
    return 65.0


def _reset_daily_counter_if_needed(config):
    """Reset daily loss count if new day."""
    today = date.today()
    if config.last_reset_date != today:
        config.daily_loss_count = 0
        config.last_reset_date  = today
        config.save(update_fields=['daily_loss_count', 'last_reset_date'])