# """
# trades/reports/data_collector.py

# Collects all trade data and calculates statistics
# for portfolio reports.

# Used by both PDF and Excel report generators.
# """

# import logging
# from datetime import datetime, timedelta
# from decimal import Decimal
# from collections import defaultdict
# from django.utils import timezone

# logger = logging.getLogger(__name__)


# # Symbol → Market type mapping
# SYMBOL_MARKET = {
#     'BTCUSDT': 'Crypto',  'ETHUSDT': 'Crypto',
#     'BNBUSDT': 'Crypto',  'SOLUSDT': 'Crypto',
#     'XRPUSDT': 'Crypto',  'DOGEUSDT': 'Crypto',
#     'ADAUSDT': 'Crypto',  'MATICUSDT': 'Crypto',
#     'LTCUSDT': 'Crypto',  'DOTUSDT': 'Crypto',
#     'EURUSD':  'Forex',   'GBPUSD':  'Forex',
#     'USDJPY':  'Forex',   'AUDUSD':  'Forex',
#     'USDCAD':  'Forex',   'USDCHF':  'Forex',
#     'NZDUSD':  'Forex',   'EURGBP':  'Forex',
#     'XAUUSD':  'Gold',    'GOLD':    'Gold',
#     'XAGUSD':  'Gold',    'SILVER':  'Gold',
# }


# def collect_report_data(user, date_range='30d', custom_start=None, custom_end=None):
#     """
#     Main function — collects all data needed for the report.

#     Args:
#         user: Django User object
#         date_range: '7d' / '30d' / '90d' / 'all' / 'custom'
#         custom_start: datetime (only if date_range='custom')
#         custom_end:   datetime (only if date_range='custom')

#     Returns:
#         dict with all report data
#     """
#     from trades.models import Trade, AgentConfig, BotLog

#     # Calculate date filter
#     end_date   = timezone.now()
#     start_date = _get_start_date(date_range, end_date, custom_start, custom_end)
#     if date_range == 'custom' and custom_end:
#         end_date = custom_end

#     logger.info(f"[REPORT] Collecting data for {user.username} from {start_date} to {end_date}")

#     # Filter trades by date range
#     all_trades = Trade.objects.filter(
#         user=user,
#         created_at__gte=start_date,
#         created_at__lte=end_date
#     ).order_by('created_at')

#     open_trades   = all_trades.filter(status='OPEN')
#     closed_trades = all_trades.exclude(status='OPEN')

#     # Build complete report data
#     return {
#         'user':           user,
#         'date_range':     date_range,
#         'start_date':     start_date,
#         'end_date':       end_date,
#         'generated_at':   timezone.now(),

#         # Summary stats
#         'summary':        _calculate_summary(all_trades),

#         # Trade lists
#         'open_trades':    _serialize_trades(open_trades),
#         'closed_trades':  _serialize_trades(closed_trades),

#         # Performance metrics
#         'best_trade':     _get_best_trade(closed_trades),
#         'worst_trade':    _get_worst_trade(closed_trades),
#         'avg_pnl':        _get_avg_pnl(closed_trades),

#         # Grouped data for charts
#         'pnl_by_symbol':  _pnl_by_symbol(closed_trades),
#         'trades_by_market': _trades_by_market(all_trades),
#         'equity_curve':   _build_equity_curve(closed_trades),
#         'win_loss_count': _win_loss_count(closed_trades),

#         # Bot data
#         'bot':            _collect_bot_data(user),
#     }


# # ─────────────────────────────────────────────────────
# #  Helpers — date range
# # ─────────────────────────────────────────────────────

# def _get_start_date(date_range, end_date, custom_start, custom_end):
#     """Calculate start date based on range option."""
#     if date_range == '7d':
#         return end_date - timedelta(days=7)
#     elif date_range == '30d':
#         return end_date - timedelta(days=30)
#     elif date_range == '90d':
#         return end_date - timedelta(days=90)
#     elif date_range == 'custom' and custom_start:
#         return custom_start
#     else:
#         # 'all' — go back 10 years
#         return end_date - timedelta(days=3650)


# # ─────────────────────────────────────────────────────
# #  Summary Statistics
# # ─────────────────────────────────────────────────────

# def _calculate_summary(trades_qs):
#     """Calculate top-level summary statistics."""
#     total = trades_qs.count()
#     open_count   = trades_qs.filter(status='OPEN').count()
#     closed_count = total - open_count

#     closed = trades_qs.exclude(status='OPEN')
#     wins   = closed.filter(status='CLOSED_TP').count()
#     losses = closed.filter(status='CLOSED_SL').count()
#     manual = closed.filter(status='CLOSED_MAN').count()

#     # Win rate calculation
#     if (wins + losses) > 0:
#         win_rate = round((wins / (wins + losses)) * 100, 1)
#     else:
#         win_rate = 0.0

#     # Total PnL
#     total_pnl = 0.0
#     for t in closed:
#         if t.pnl is not None:
#             total_pnl += float(t.pnl)
#     total_pnl = round(total_pnl, 2)

#     return {
#         'total_trades':   total,
#         'open_trades':    open_count,
#         'closed_trades':  closed_count,
#         'wins':           wins,
#         'losses':         losses,
#         'manual_closes':  manual,
#         'win_rate':       win_rate,
#         'total_pnl':      total_pnl,
#     }


# # ─────────────────────────────────────────────────────
# #  Trade Serialization
# # ─────────────────────────────────────────────────────

# def _serialize_trades(trades_qs):
#     """Convert Trade queryset to list of dicts."""
#     result = []
#     for t in trades_qs:
#         result.append({
#             'id':           t.id,
#             'symbol':       t.symbol,
#             'market':       SYMBOL_MARKET.get(t.symbol, 'Unknown'),
#             'entry_price':  float(t.entry_price),
#             'current_price': float(t.current_price) if t.current_price else None,
#             'take_profit':  float(t.take_profit),
#             'stop_loss':    float(t.stop_loss),
#             'tp_percent':   float(t.tp_percent),
#             'sl_percent':   float(t.sl_percent),
#             'status':       t.status,
#             'status_display': t.get_status_display(),
#             'pnl':          float(t.pnl) if t.pnl is not None else None,
#             'created_at':   t.created_at,
#             'closed_at':    t.closed_at,
#             'duration':     _calculate_duration(t),
#         })
#     return result


# def _calculate_duration(trade):
#     """Calculate how long trade was open (in hours)."""
#     if not trade.closed_at:
#         return None
#     delta   = trade.closed_at - trade.created_at
#     hours   = delta.total_seconds() / 3600
#     return round(hours, 2)


# # ─────────────────────────────────────────────────────
# #  Best / Worst / Average
# # ─────────────────────────────────────────────────────

# def _get_best_trade(trades_qs):
#     """Find trade with highest PnL %."""
#     best = trades_qs.exclude(pnl__isnull=True).order_by('-pnl').first()
#     if not best:
#         return None
#     return {
#         'symbol': best.symbol,
#         'pnl':    float(best.pnl),
#         'date':   best.closed_at or best.created_at,
#     }


# def _get_worst_trade(trades_qs):
#     """Find trade with lowest PnL %."""
#     worst = trades_qs.exclude(pnl__isnull=True).order_by('pnl').first()
#     if not worst:
#         return None
#     return {
#         'symbol': worst.symbol,
#         'pnl':    float(worst.pnl),
#         'date':   worst.closed_at or worst.created_at,
#     }


# def _get_avg_pnl(trades_qs):
#     """Calculate average PnL %."""
#     valid_pnls = [float(t.pnl) for t in trades_qs if t.pnl is not None]
#     if not valid_pnls:
#         return 0.0
#     return round(sum(valid_pnls) / len(valid_pnls), 2)


# # ─────────────────────────────────────────────────────
# #  Grouping for Charts
# # ─────────────────────────────────────────────────────

# def _pnl_by_symbol(trades_qs):
#     """Calculate cumulative PnL grouped by symbol."""
#     pnl_map = defaultdict(lambda: {'pnl': 0.0, 'count': 0})

#     for t in trades_qs:
#         if t.pnl is not None:
#             pnl_map[t.symbol]['pnl']   += float(t.pnl)
#             pnl_map[t.symbol]['count'] += 1

#     # Convert to sorted list
#     result = []
#     for symbol, data in pnl_map.items():
#         result.append({
#             'symbol': symbol,
#             'pnl':    round(data['pnl'], 2),
#             'count':  data['count'],
#         })

#     # Sort by PnL descending
#     result.sort(key=lambda x: x['pnl'], reverse=True)
#     return result


# def _trades_by_market(trades_qs):
#     """Count trades grouped by market type (Crypto/Forex/Gold)."""
#     market_count = defaultdict(int)

#     for t in trades_qs:
#         market = SYMBOL_MARKET.get(t.symbol, 'Unknown')
#         market_count[market] += 1

#     return dict(market_count)


# def _build_equity_curve(trades_qs):
#     """
#     Build cumulative PnL data for equity curve chart.

#     Returns:
#         list of dicts: [{'index': 1, 'cumulative_pnl': 2.3}, ...]
#     """
#     curve   = []
#     cum_pnl = 0.0

#     sorted_trades = sorted(
#         [t for t in trades_qs if t.pnl is not None],
#         key=lambda t: t.closed_at or t.created_at
#     )

#     for i, t in enumerate(sorted_trades, 1):
#         cum_pnl += float(t.pnl)
#         curve.append({
#             'index':          i,
#             'symbol':         t.symbol,
#             'pnl':            float(t.pnl),
#             'cumulative_pnl': round(cum_pnl, 2),
#             'date':           t.closed_at or t.created_at,
#         })

#     return curve


# def _win_loss_count(trades_qs):
#     """Count of TP wins, SL losses, and manual closes."""
#     return {
#         'tp_wins':        trades_qs.filter(status='CLOSED_TP').count(),
#         'sl_losses':      trades_qs.filter(status='CLOSED_SL').count(),
#         'manual_closes':  trades_qs.filter(status='CLOSED_MAN').count(),
#     }


# # ─────────────────────────────────────────────────────
# #  Bot Data
# # ─────────────────────────────────────────────────────

# def _collect_bot_data(user):
#     """Collect bot statistics and recent activity."""
#     from trades.models import AgentConfig, BotLog

#     try:
#         config = AgentConfig.objects.get(user=user)
#     except AgentConfig.DoesNotExist:
#         return {
#             'configured':     False,
#             'is_active':      False,
#             'total_trades':   0,
#             'wins':           0,
#             'losses':         0,
#             'win_rate':       0,
#             'recent_logs':    [],
#         }

#     # Recent bot activity
#     recent = BotLog.objects.filter(user=user).order_by('-timestamp')[:20]
#     logs = []
#     for log in recent:
#         logs.append({
#             'action':     log.action,
#             'symbol':     log.symbol,
#             'message':    log.message,
#             'confidence': log.confidence,
#             'timestamp':  log.timestamp,
#         })

#     return {
#         'configured':       True,
#         'is_active':        config.is_active,
#         'total_trades':     config.total_bot_trades,
#         'wins':             config.total_bot_wins,
#         'losses':           config.total_bot_losses,
#         'win_rate':         config.win_rate,
#         'selected_symbols': config.selected_symbols or [],
#         'max_open_trades':  config.max_open_trades,
#         'min_conf_crypto':  config.min_confidence_crypto,
#         'min_conf_forex':   config.min_confidence_forex,
#         'min_conf_gold':    config.min_confidence_gold,
#         'recent_logs':      logs,
#     }
"""
trades/reports/data_collector.py
Collects trade data and statistics for portfolio reports.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict
from django.utils import timezone

logger = logging.getLogger(__name__)


SYMBOL_MARKET = {
    'BTCUSDT': 'Crypto',  'ETHUSDT': 'Crypto',
    'BNBUSDT': 'Crypto',  'SOLUSDT': 'Crypto',
    'XRPUSDT': 'Crypto',  'DOGEUSDT': 'Crypto',
    'ADAUSDT': 'Crypto',  'MATICUSDT': 'Crypto',
    'EURUSD':  'Forex',   'GBPUSD':  'Forex',
    'USDJPY':  'Forex',   'AUDUSD':  'Forex',
    'USDCAD':  'Forex',   'USDCHF':  'Forex',
    'NZDUSD':  'Forex',   'EURGBP':  'Forex',
    'XAUUSD':  'Gold',    'GOLD':    'Gold',
    'XAGUSD':  'Gold',    'SILVER':  'Gold',
}


def collect_report_data(user, date_range='30d', custom_start=None, custom_end=None):
    """Main function — collects all data for the report."""
    from trades.models import Trade

    end_date   = timezone.now()
    start_date = _get_start_date(date_range, end_date, custom_start, custom_end)
    if date_range == 'custom' and custom_end:
        end_date = custom_end

    logger.info(f"[REPORT] Collecting data for {user.username}")

    all_trades = Trade.objects.filter(
        user=user,
        created_at__gte=start_date,
        created_at__lte=end_date,
    ).order_by('created_at')

    open_trades   = all_trades.filter(status='OPEN')
    closed_trades = all_trades.exclude(status='OPEN')

    return {
        'user':             user,
        'date_range':       date_range,
        'start_date':       start_date,
        'end_date':         end_date,
        'generated_at':     timezone.now(),
        'summary':          _calculate_summary(all_trades),
        'open_trades':      _serialize_trades(open_trades),
        'closed_trades':    _serialize_trades(closed_trades),
        'best_trade':       _get_best_trade(closed_trades),
        'worst_trade':      _get_worst_trade(closed_trades),
        'avg_pnl':          _get_avg_pnl(closed_trades),
        'pnl_by_symbol':    _pnl_by_symbol(closed_trades),
        'trades_by_market': _trades_by_market(all_trades),
        'equity_curve':     _build_equity_curve(closed_trades),
        'win_loss_count':   _win_loss_count(closed_trades),
        'bot':              _collect_bot_data(user),
    }


def _get_start_date(date_range, end_date, custom_start, custom_end):
    if date_range == '7d':
        return end_date - timedelta(days=7)
    elif date_range == '30d':
        return end_date - timedelta(days=30)
    elif date_range == '90d':
        return end_date - timedelta(days=90)
    elif date_range == 'custom' and custom_start:
        return custom_start
    return end_date - timedelta(days=3650)


def _calculate_summary(trades_qs):
    total = trades_qs.count()
    open_count   = trades_qs.filter(status='OPEN').count()
    closed_count = total - open_count
    closed = trades_qs.exclude(status='OPEN')
    wins   = closed.filter(status='CLOSED_TP').count()
    losses = closed.filter(status='CLOSED_SL').count()
    manual = closed.filter(status='CLOSED_MAN').count()
    win_rate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0
    total_pnl = 0.0
    for t in closed:
        if t.pnl is not None:
            total_pnl += float(t.pnl)
    return {
        'total_trades':   total,
        'open_trades':    open_count,
        'closed_trades':  closed_count,
        'wins':           wins,
        'losses':         losses,
        'manual_closes':  manual,
        'win_rate':       win_rate,
        'total_pnl':      round(total_pnl, 2),
    }


def _serialize_trades(trades_qs):
    result = []
    for t in trades_qs:
        result.append({
            'id':             t.id,
            'symbol':         t.symbol,
            'market':         SYMBOL_MARKET.get(t.symbol, 'Unknown'),
            'entry_price':    float(t.entry_price),
            'current_price':  float(t.current_price) if t.current_price else None,
            'take_profit':    float(t.take_profit),
            'stop_loss':      float(t.stop_loss),
            'tp_percent':     float(t.tp_percent),
            'sl_percent':     float(t.sl_percent),
            'status':         t.status,
            'status_display': t.get_status_display(),
            'pnl':            float(t.pnl) if t.pnl is not None else None,
            'created_at':     t.created_at,
            'closed_at':      t.closed_at,
            'duration':       _calculate_duration(t),
        })
    return result


def _calculate_duration(trade):
    if not trade.closed_at:
        return None
    delta = trade.closed_at - trade.created_at
    return round(delta.total_seconds() / 3600, 2)


def _get_best_trade(trades_qs):
    best = trades_qs.exclude(pnl__isnull=True).order_by('-pnl').first()
    if not best:
        return None
    return {'symbol': best.symbol, 'pnl': float(best.pnl),
            'date': best.closed_at or best.created_at}


def _get_worst_trade(trades_qs):
    worst = trades_qs.exclude(pnl__isnull=True).order_by('pnl').first()
    if not worst:
        return None
    return {'symbol': worst.symbol, 'pnl': float(worst.pnl),
            'date': worst.closed_at or worst.created_at}


def _get_avg_pnl(trades_qs):
    valid = [float(t.pnl) for t in trades_qs if t.pnl is not None]
    if not valid:
        return 0.0
    return round(sum(valid) / len(valid), 2)


def _pnl_by_symbol(trades_qs):
    pnl_map = defaultdict(lambda: {'pnl': 0.0, 'count': 0})
    for t in trades_qs:
        if t.pnl is not None:
            pnl_map[t.symbol]['pnl']   += float(t.pnl)
            pnl_map[t.symbol]['count'] += 1
    result = []
    for symbol, data in pnl_map.items():
        result.append({'symbol': symbol, 'pnl': round(data['pnl'], 2),
                       'count': data['count']})
    result.sort(key=lambda x: x['pnl'], reverse=True)
    return result


def _trades_by_market(trades_qs):
    market_count = defaultdict(int)
    for t in trades_qs:
        market = SYMBOL_MARKET.get(t.symbol, 'Unknown')
        market_count[market] += 1
    return dict(market_count)


def _build_equity_curve(trades_qs):
    curve   = []
    cum_pnl = 0.0
    sorted_trades = sorted(
        [t for t in trades_qs if t.pnl is not None],
        key=lambda t: t.closed_at or t.created_at,
    )
    for i, t in enumerate(sorted_trades, 1):
        cum_pnl += float(t.pnl)
        curve.append({
            'index':          i,
            'symbol':         t.symbol,
            'pnl':            float(t.pnl),
            'cumulative_pnl': round(cum_pnl, 2),
            'date':           t.closed_at or t.created_at,
        })
    return curve


def _win_loss_count(trades_qs):
    return {
        'tp_wins':       trades_qs.filter(status='CLOSED_TP').count(),
        'sl_losses':     trades_qs.filter(status='CLOSED_SL').count(),
        'manual_closes': trades_qs.filter(status='CLOSED_MAN').count(),
    }


def _collect_bot_data(user):
    from trades.models import AgentConfig, BotLog

    try:
        config = AgentConfig.objects.get(user=user)
    except AgentConfig.DoesNotExist:
        return {
            'configured':       False,
            'is_active':        False,
            'total_trades':     0,
            'wins':             0,
            'losses':           0,
            'win_rate':         0,
            'recent_logs':      [],
            'selected_symbols': [],
            'max_open_trades':  3,
            'min_conf_crypto':  65.0,
            'min_conf_forex':   62.0,
            'min_conf_gold':    63.0,
        }

    recent = BotLog.objects.filter(user=user).order_by('-timestamp')[:20]
    logs = []
    for log in recent:
        logs.append({
            'action':     log.action,
            'symbol':     log.symbol,
            'message':    log.message,
            'confidence': log.confidence,
            'timestamp':  log.timestamp,
        })

    return {
        'configured':       True,
        'is_active':        config.is_active,
        'total_trades':     config.total_bot_trades,
        'wins':             config.total_bot_wins,
        'losses':           config.total_bot_losses,
        'win_rate':         config.win_rate,
        'selected_symbols': config.selected_symbols or [],
        'max_open_trades':  config.max_open_trades,
        'min_conf_crypto':  config.min_confidence_crypto,
        'min_conf_forex':   config.min_confidence_forex,
        'min_conf_gold':    config.min_confidence_gold,
        'recent_logs':      logs,
    }