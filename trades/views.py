"""
trades/views.py
All views for the trading system: dashboard, create trade, close trade, price API.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal

from .models import Trade
from .forms import CreateTradeForm

from .price_service import get_live_price, get_prices_for_symbols
from .trade_monitor import close_trade, get_trend_signal, update_price_history


@login_required
def dashboard(request):
    """
    Main dashboard showing:
    - All open trades for the current user
    - All closed trades for the current user
    - Current prices for active symbols
    - Summary stats (total trades, win rate, etc.)
    """
    user = request.user

    # Get user's trades split by status
    open_trades   = Trade.objects.filter(user=user, status=Trade.STATUS_OPEN)
    closed_trades = Trade.objects.filter(user=user).exclude(status=Trade.STATUS_OPEN)

    # Fetch current prices for open trades
    open_symbols = list(open_trades.values_list('symbol', flat=True).distinct())
    current_prices = get_prices_for_symbols(open_symbols) if open_symbols else {}

    # Update current_price on open trades and get trend signals
    trade_data = []
    for trade in open_trades:
        price = current_prices.get(trade.symbol)
        if price:
            update_price_history(trade.symbol, price)
            trade.current_price = Decimal(str(price))
            trade.save(update_fields=['current_price'])

        trend = get_trend_signal(trade.symbol)
        trade_data.append({'trade': trade, 'trend': trend})

    # Calculate summary stats
    total_closed = closed_trades.count()
    wins  = closed_trades.filter(status=Trade.STATUS_CLOSED_TP).count()
    losses = closed_trades.filter(status=Trade.STATUS_CLOSED_SL).count()
    win_rate = round((wins / total_closed * 100), 1) if total_closed > 0 else 0

    # Total PnL across all closed trades
    total_pnl = sum(
        t.pnl for t in closed_trades if t.pnl is not None
    )

    context = {
        'trade_data':    trade_data,       # List of {trade, trend}
        'open_trades':   open_trades,
        'closed_trades': closed_trades,
        'current_prices': current_prices,
        'total_open':    open_trades.count(),
        'total_closed':  total_closed,
        'wins':          wins,
        'losses':        losses,
        'win_rate':      win_rate,
        'total_pnl':     round(total_pnl, 2),
    }
    return render(request, 'trades/dashboard.html', context)


"""
REPLACE your existing create_trade function in trades/views.py with this one.
Everything else in views.py stays the same.
"""

@login_required
def create_trade(request):
    """
    Create a new paper trade.
    Now supports direction (BUY/SELL), quantity, and amount.

    TP/SL calculation depends on direction:
      BUY  → TP above entry, SL below entry
      SELL → TP below entry, SL above entry
    """
    if request.method == 'POST':
        form = CreateTradeForm(request.POST)
        if form.is_valid():
            symbol     = form.cleaned_data['symbol']
            direction  = form.cleaned_data['direction']
            quantity   = form.cleaned_data['quantity']
            amount     = form.cleaned_data['amount']
            tp_percent = form.cleaned_data['tp_percent']
            sl_percent = form.cleaned_data['sl_percent']

            # Fetch current price as entry price
            entry_price = get_live_price(symbol)
            if entry_price is None:
                messages.error(request, f'Could not fetch price for {symbol}. Please try again.')
                return render(request, 'trades/create_trade.html', {'form': form})

            entry = Decimal(str(entry_price))

            # Calculate TP and SL based on direction
            if direction == Trade.DIRECTION_SELL:
                # SELL: profit when price falls
                #   TP is BELOW entry, SL is ABOVE entry
                take_profit = entry * (1 - tp_percent / Decimal('100'))
                stop_loss   = entry * (1 + sl_percent / Decimal('100'))
            else:
                # BUY: profit when price rises
                #   TP is ABOVE entry, SL is BELOW entry
                take_profit = entry * (1 + tp_percent / Decimal('100'))
                stop_loss   = entry * (1 - sl_percent / Decimal('100'))

            # Create and save the trade
            trade = Trade.objects.create(
                user          = request.user,
                symbol        = symbol,
                direction     = direction,
                quantity      = quantity,
                amount        = amount,
                entry_price   = entry,
                take_profit   = round(take_profit, 6),
                stop_loss     = round(stop_loss, 6),
                tp_percent    = tp_percent,
                sl_percent    = sl_percent,
                current_price = entry,
                status        = Trade.STATUS_OPEN,
            )

            messages.success(
                request,
                f'✅ {direction} Trade created! {symbol} @ ${entry_price:,.4f} | '
                f'Qty: {quantity} | TP: ${float(take_profit):,.4f} | '
                f'SL: ${float(stop_loss):,.4f}'
            )
            return redirect('dashboard')
        else:
            messages.error(request, 'Please fix the errors in the form.')
    else:
        form = CreateTradeForm()

    return render(request, 'trades/create_trade.html', {'form': form})

@login_required
def close_trade_manual(request, trade_id):
    """
    Manually close a trade (user clicks 'Close' button on dashboard).
    Only the owner can close their own trades.
    """
    trade = get_object_or_404(Trade, id=trade_id, user=request.user)

    if not trade.is_open:
        messages.warning(request, 'This trade is already closed.')
        return redirect('dashboard')

    # Get current price for PnL calculation
    current_price = get_live_price(trade.symbol)
    if current_price:
        close_price = Decimal(str(current_price))
    else:
        close_price = trade.entry_price  # Fallback to entry if price unavailable

    close_trade(trade, Trade.STATUS_CLOSED_MAN, close_price)
    messages.info(request, f'Trade #{trade.id} ({trade.symbol}) manually closed. PnL: {trade.pnl_display}')
    return redirect('dashboard')


@login_required
def trade_detail(request, trade_id):
    """Show details for a single trade."""
    trade = get_object_or_404(Trade, id=trade_id, user=request.user)
    current_price = None

    if trade.is_open:
        price = get_live_price(trade.symbol)
        if price:
            current_price = price

    context = {
        'trade': trade,
        'current_price': current_price,
        'trend': get_trend_signal(trade.symbol),
    }
    return render(request, 'trades/trade_detail.html', context)


@login_required
def price_api(request, symbol):
    """
    JSON endpoint returning live price, trend, and open trade TP/SL lines.
    Also triggers auto-close so trades close even without the background agent.
    """
    from .trade_monitor import check_and_close_trades

    sym = symbol.upper()
    price = get_live_price(sym)

    if not price:
        return JsonResponse({"status": "error", "message": "Price unavailable"}, status=503)

    update_price_history(sym, price)

    # Auto-close check on every price fetch — no agent required
    try:
        check_and_close_trades()
    except Exception:
        pass

    # Return open trade TP/SL data so JS can draw chart lines
    open_qs = Trade.objects.filter(
        user=request.user, symbol=sym, status=Trade.STATUS_OPEN
    ).values("id", "entry_price", "take_profit", "stop_loss", "tp_percent", "sl_percent")

    trades_data = [
        {
            "id":     t["id"],
            "entry":  float(t["entry_price"]),
            "tp":     float(t["take_profit"]),
            "sl":     float(t["stop_loss"]),
            "tp_pct": float(t["tp_percent"]),
            "sl_pct": float(t["sl_percent"]),
        }
        for t in open_qs
    ]

    return JsonResponse({
        "status": "ok",
        "symbol": sym,
        "price":  price,
        "trend":  get_trend_signal(sym),
        "trades": trades_data,
    })


@login_required
def ai_suggest(request, symbol):
    """
    AI suggestion endpoint.
    Returns LSTM-predicted TP/SL values for a symbol.

    Called by create_trade.js when user selects a symbol.
    URL: /trades/ai-suggest/BTCUSDT/

    Returns JSON:
    {
      "symbol":      "BTCUSDT",
      "direction":   "UP",
      "confidence":  73.5,
      "tp_percent":  4.5,
      "sl_percent":  2.0,
      "model_ready": true,
      "message":     "AI suggests TP=4.5%, SL=2.0%"
    }
    """
    try:
        from .ml.predictor import get_ai_suggestion
        result = get_ai_suggestion(symbol.upper())
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'symbol':      symbol.upper(),
            'direction':   'NEUTRAL',
            'confidence':  0.0,
            'tp_percent':  3.0,
            'sl_percent':  1.5,
            'model_ready': False,
            'message':     f'AI unavailable: {str(e)}',
        })
    
@login_required
def bot_dashboard(request):
    from .models import AgentConfig, BotLog
    config, created = AgentConfig.objects.get_or_create(
        user=request.user,
        defaults={'selected_symbols': ['BTCUSDT', 'EURUSD', 'XAUUSD']}
    )
    all_symbols = [
        {'symbol': 'BTCUSDT',  'name': 'Bitcoin',  'market': 'Crypto'},
        {'symbol': 'ETHUSDT',  'name': 'Ethereum', 'market': 'Crypto'},
        {'symbol': 'BNBUSDT',  'name': 'BNB',      'market': 'Crypto'},
        {'symbol': 'SOLUSDT',  'name': 'Solana',   'market': 'Crypto'},
        {'symbol': 'XRPUSDT',  'name': 'Ripple',   'market': 'Crypto'},
        {'symbol': 'EURUSD',   'name': 'EUR/USD',  'market': 'Forex'},
        {'symbol': 'GBPUSD',   'name': 'GBP/USD',  'market': 'Forex'},
        {'symbol': 'USDJPY',   'name': 'USD/JPY',  'market': 'Forex'},
        {'symbol': 'XAUUSD',   'name': 'Gold',     'market': 'Gold'},
        {'symbol': 'XAGUSD',   'name': 'Silver',   'market': 'Gold'},
    ]
    selected = config.selected_symbols or []
    for s in all_symbols:
        s['selected'] = s['symbol'] in selected
    logs = BotLog.objects.filter(user=request.user).order_by('-timestamp')[:50]
    context = {
        'config':      config,
        'all_symbols': all_symbols,
        'logs':        logs,
    }
    return render(request, 'trades/bot_dashboard.html', context)



@login_required
def bot_toggle(request):
    from .models import AgentConfig
    config, _ = AgentConfig.objects.get_or_create(
        user=request.user,
        defaults={'selected_symbols': ['BTCUSDT', 'EURUSD', 'XAUUSD']}
    )
    # Toggle regardless of method
    config.is_active = not config.is_active
    config.save(update_fields=['is_active'])
    status = 'started ✅' if config.is_active else 'stopped ⏹'
    messages.success(request, f'Bot {status} successfully.')
    return redirect('bot_dashboard')


"""
REPLACE your bot_settings function in trades/views.py with this one.
Adds saving of bot_fixed_quantity and bot_fixed_amount.
"""

@login_required
def bot_settings(request):
    from .models import AgentConfig
    if request.method == 'POST':
        config, _ = AgentConfig.objects.get_or_create(user=request.user)
        config.selected_symbols      = request.POST.getlist('symbols')
        config.min_confidence_crypto = float(request.POST.get('conf_crypto', 65))
        config.min_confidence_forex  = float(request.POST.get('conf_forex',  62))
        config.min_confidence_gold   = float(request.POST.get('conf_gold',   63))
        config.max_open_trades       = int(request.POST.get('max_trades', 3))
        config.cooldown_minutes      = int(request.POST.get('cooldown',   30))
        config.daily_loss_limit      = int(request.POST.get('daily_limit', 3))

        # ── NEW: bot fixed sizing ──
        config.bot_fixed_quantity = request.POST.get('bot_quantity', 1)
        config.bot_fixed_amount   = request.POST.get('bot_amount', 100)

        config.save()
        messages.success(request, 'Bot settings saved successfully.')
    return redirect('bot_dashboard')
"""
ADD THESE FUNCTIONS to your trades/views.py at the bottom.

These views handle:
  /trades/report/           → Show config page
  /trades/report/generate/  → Generate and download PDF/Excel
"""

import logging
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


@login_required
def report_config(request):
    """
    Report configuration page.
    User selects date range, format, theme, sections.
    """
    from .models import Trade

    # Get quick stats for preview
    user_trades = Trade.objects.filter(user=request.user)
    total       = user_trades.count()
    open_count  = user_trades.filter(status='OPEN').count()
    closed      = user_trades.exclude(status='OPEN').count()

    # Calculate quick PnL preview
    closed_qs = user_trades.exclude(status='OPEN').exclude(pnl__isnull=True)
    total_pnl = sum(float(t.pnl) for t in closed_qs) if closed_qs else 0.0

    context = {
        'total_trades':  total,
        'open_trades':   open_count,
        'closed_trades': closed,
        'total_pnl':     round(total_pnl, 2),
    }
    return render(request, 'trades/report_config.html', context)


@login_required
def report_generate(request):
    """
    Generate and return PDF or Excel report.

    POST params:
      date_range : '7d' | '30d' | '90d' | 'all' | 'custom'
      custom_start, custom_end : ISO date strings (if custom)
      format     : 'pdf' | 'excel'
      theme      : 'dark' | 'light'
    """
    if request.method != 'POST':
        return redirect('report_config')

    # Get parameters
    date_range = request.POST.get('date_range', '30d')
    fmt        = request.POST.get('format', 'pdf')
    theme      = request.POST.get('theme', 'light')

    custom_start = None
    custom_end   = None

    if date_range == 'custom':
        try:
            cs = request.POST.get('custom_start')
            ce = request.POST.get('custom_end')
            if cs:
                custom_start = timezone.make_aware(
                    datetime.strptime(cs, '%Y-%m-%d')
                )
            if ce:
                custom_end = timezone.make_aware(
                    datetime.strptime(ce, '%Y-%m-%d')
                )
        except Exception as e:
            messages.error(request, f'Invalid date format: {e}')
            return redirect('report_config')

    # Collect data
    try:
        from .reports.data_collector import collect_report_data
        report_data = collect_report_data(
            user=request.user,
            date_range=date_range,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        logger.info(f"[REPORT] Data collected for {request.user.username}")

    except Exception as e:
        logger.exception("Data collection failed")
        messages.error(request, f'Failed to collect data: {e}')
        return redirect('report_config')

    # Check if any data exists
    if report_data['summary']['total_trades'] == 0:
        messages.warning(
            request,
            'No trades found in selected date range. Try a wider range.'
        )
        return redirect('report_config')

    # Generate report based on format
    timestamp = timezone.now().strftime('%Y%m%d_%H%M')
    username  = request.user.username

    try:
        if fmt == 'pdf':
            return _generate_pdf(report_data, theme, username, timestamp)
        elif fmt == 'excel':
            return _generate_excel(report_data, username, timestamp)
        else:
            messages.error(request, 'Invalid format selected.')
            return redirect('report_config')

    except Exception as e:
        logger.exception("Report generation failed")
        messages.error(request, f'Report generation failed: {e}')
        return redirect('report_config')


def _generate_pdf(report_data, theme, username, timestamp):
    """Generate and return PDF response."""
    from .reports.pdf_generator import generate_pdf_report

    pdf_buffer = generate_pdf_report(report_data, theme=theme)

    response = HttpResponse(
        pdf_buffer.getvalue(),
        content_type='application/pdf'
    )
    filename = f'portfolio_report_{username}_{timestamp}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    logger.info(f"[REPORT] PDF generated for {username}")
    return response


def _generate_excel(report_data, username, timestamp):
    """Generate and return Excel response."""
    from .reports.excel_generator import generate_excel_report

    excel_buffer = generate_excel_report(report_data)

    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'portfolio_report_{username}_{timestamp}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    logger.info(f"[REPORT] Excel generated for {username}")
    return response

"""
ADD THESE to trades/views.py - REPLACE old chat views.
"""

import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
#  Chat Page (UI)
# ─────────────────────────────────────────────────────

@login_required
def chat_page(request):
    """Main chat interface — handles new chat properly."""
    from .models import Conversation

    conv_id = request.GET.get('c')
    is_new  = request.GET.get('new')  # Any value means start fresh

    active_conv = None

    # Priority 1: Specific conversation requested
    if conv_id:
        active_conv = Conversation.objects.filter(
            id=conv_id, user=request.user
        ).first()

    # Priority 2: Auto-load latest IF not requesting new AND no conv_id
    elif not is_new:
        active_conv = Conversation.objects.filter(
            user=request.user
        ).first()

    # If is_new is set, active_conv stays None → shows welcome screen

    # Load messages of active conversation (only if exists)
    history = []
    if active_conv:
        history = list(active_conv.messages.all().order_by('timestamp'))

    context = {
        'history':     history,
        'active_conv': active_conv,
    }
    return render(request, 'trades/chatbot.html', context)

# ─────────────────────────────────────────────────────
#  Send Message
# ─────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def chat_send(request):
    """Process message — creates conversation if needed."""
    from .models import ChatMessage, Conversation
    from .chatbot.ai_engine import get_response
    from .chatbot.image_analyzer import prepare_image, validate_image

    try:
        message_text = request.POST.get('message', '').strip()
        conv_id      = request.POST.get('conversation_id')
        uploaded_image = request.FILES.get('image')

        # Validate input
        if not message_text and not uploaded_image:
            return JsonResponse({
                'status': 'error',
                'message': 'Empty message',
            }, status=400)

        # Get or create conversation
        conversation = None
        if conv_id:
            conversation = Conversation.objects.filter(
                id=conv_id, user=request.user
            ).first()

        is_new_conv = False
        if not conversation:
            # Create new conversation with auto-title from first message
            title = (message_text[:50] + '…') if len(message_text) > 50 else message_text
            if not title:
                title = '📷 Image analysis'
            conversation = Conversation.objects.create(
                user=request.user,
                title=title or 'New Chat',
            )
            is_new_conv = True

        # Prepare image if uploaded
        pil_image   = None
        image_field = None
        if uploaded_image:
            is_valid, error_msg = validate_image(uploaded_image)
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            pil_image   = prepare_image(uploaded_image)
            image_field = uploaded_image
            if not message_text:
                message_text = '🖼️ Analyze this chart'

        # Save user message
        user_msg = ChatMessage.objects.create(
            user         = request.user,
            conversation = conversation,
            role         = ChatMessage.ROLE_USER,
            message      = message_text,
            image        = image_field,
        )

        # Get history for AI context (last 6 from this conversation only)
        history_msgs = ChatMessage.objects.filter(
            conversation=conversation
        ).order_by('-timestamp')[:6]

        chat_history = []
        for msg in reversed(history_msgs):
            chat_history.append({'role': msg.role, 'message': msg.message})

        # Get AI response
        response = get_response(
            query=message_text,
            image=pil_image,
            chat_history=chat_history,
        )

        # Save bot message
        bot_msg = ChatMessage.objects.create(
            user         = request.user,
            conversation = conversation,
            role         = ChatMessage.ROLE_BOT,
            message      = response['answer'],
            metadata     = {
                'source':           response.get('source'),
                'response_time_ms': response.get('response_time_ms', 0),
            },
        )

        # Update conversation timestamp
        conversation.save()

        return JsonResponse({
            'status': 'success',
            'is_new_conversation': is_new_conv,
            'conversation': {
                'id':    conversation.id,
                'title': conversation.title,
            },
            'user_message': {
                'id':        user_msg.id,
                'role':      'user',
                'message':   user_msg.message,
                'image_url': user_msg.image.url if user_msg.image else None,
                'timestamp': user_msg.timestamp.strftime('%H:%M'),
            },
            'bot_message': {
                'id':        bot_msg.id,
                'role':      'bot',
                'message':   bot_msg.message,
                'source':    response.get('source'),
                'timestamp': bot_msg.timestamp.strftime('%H:%M'),
            },
        })

    except Exception as e:
        logger.exception("Chat send failed")
        return JsonResponse({
            'status':  'error',
            'message': f'Error: {str(e)[:100]}',
        }, status=500)


# ─────────────────────────────────────────────────────
#  Conversations List (for sidebar)
# ─────────────────────────────────────────────────────

@login_required
def conversations_list(request):
    """Return all conversations grouped by date."""
    from .models import Conversation
    from collections import defaultdict
    import datetime

    try:
        search_q = request.GET.get('q', '').strip()

        qs = Conversation.objects.filter(user=request.user)

        if search_q:
            qs = qs.filter(title__icontains=search_q)

        qs = qs[:100]

        # Group by date
        today = datetime.date.today()
        grouped = defaultdict(list)

        for conv in qs:
            conv_date = conv.updated_at.date()

            if conv_date == today:
                label = 'Today'
            elif conv_date == today - datetime.timedelta(days=1):
                label = 'Yesterday'
            elif conv_date >= today - datetime.timedelta(days=7):
                label = 'Last 7 days'
            elif conv_date >= today - datetime.timedelta(days=30):
                label = 'Last 30 days'
            else:
                label = conv_date.strftime('%B %Y')

            grouped[label].append({
                'id':       conv.id,
                'title':    conv.title,
                'preview':  conv.preview,
                'count':    conv.message_count,
                'time':     conv.updated_at.strftime('%H:%M'),
                'date':     conv.updated_at.strftime('%b %d'),
            })

        # Convert to list preserving order
        result = []
        order = ['Today', 'Yesterday', 'Last 7 days', 'Last 30 days']
        for label in order:
            if label in grouped:
                result.append({'label': label, 'items': grouped[label]})

        # Add older month groups
        for label in grouped:
            if label not in order:
                result.append({'label': label, 'items': grouped[label]})

        total = Conversation.objects.filter(user=request.user).count()

        return JsonResponse({
            'status':         'success',
            'total':          total,
            'groups':         result,
        })

    except Exception as e:
        logger.exception("Conversations list failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────
#  Create New Conversation (returns empty chat)
# ─────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def conversation_new(request):
    """Create a new empty conversation."""
    # We DON'T create here. Just redirect to fresh page.
    # Conversation will be auto-created on first message.
    return JsonResponse({'status': 'success', 'redirect': '/trades/chat/'})


# ─────────────────────────────────────────────────────
#  Delete Conversation
# ─────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def conversation_delete(request, conv_id):
    """Delete a specific conversation and all its messages."""
    from .models import Conversation

    try:
        conv = Conversation.objects.filter(
            id=conv_id, user=request.user
        ).first()

        if not conv:
            return JsonResponse({
                'status': 'error',
                'message': 'Conversation not found'
            }, status=404)

        conv.delete()  # cascades to messages

        return JsonResponse({
            'status': 'success',
            'message': 'Conversation deleted'
        })

    except Exception as e:
        logger.exception("Conversation delete failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────
#  Get Conversation Messages (for switching)
# ─────────────────────────────────────────────────────

@login_required
def conversation_messages(request, conv_id):
    """Get all messages of a specific conversation as JSON."""
    from .models import Conversation

    try:
        conv = Conversation.objects.filter(
            id=conv_id, user=request.user
        ).first()

        if not conv:
            return JsonResponse({
                'status': 'error',
                'message': 'Not found'
            }, status=404)

        messages_list = []
        for msg in conv.messages.all().order_by('timestamp'):
            messages_list.append({
                'id':        msg.id,
                'role':      msg.role,
                'message':   msg.message,
                'image_url': msg.image.url if msg.image else None,
                'source':    msg.metadata.get('source') if msg.metadata else None,
                'timestamp': msg.timestamp.strftime('%H:%M'),
            })

        return JsonResponse({
            'status':       'success',
            'conversation': {
                'id':    conv.id,
                'title': conv.title,
            },
            'messages':     messages_list,
        })

    except Exception as e:
        logger.exception("Conversation load failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────
#  Status (unchanged)
# ─────────────────────────────────────────────────────

@login_required
def chat_status(request):
    from .chatbot.ai_engine import check_status
    return JsonResponse(check_status())