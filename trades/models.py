"""
trades/models.py
Defines the Trade model - the core data structure of the system.
Each trade stores entry price, TP/SL prices, direction, size, and status.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Trade(models.Model):
    """
    Represents a single paper trade.
    Stores entry/TP/SL prices, direction (BUY/SELL), quantity, amount, and status.
    """

    # ── Status choices ──
    STATUS_OPEN        = 'OPEN'
    STATUS_CLOSED_TP   = 'CLOSED_TP'   # Closed because Take Profit was hit
    STATUS_CLOSED_SL   = 'CLOSED_SL'   # Closed because Stop Loss was hit
    STATUS_CLOSED_MAN  = 'CLOSED_MAN'  # Manually closed by user

    STATUS_CHOICES = [
        (STATUS_OPEN,       'Open'),
        (STATUS_CLOSED_TP,  'Closed (Take Profit)'),
        (STATUS_CLOSED_SL,  'Closed (Stop Loss)'),
        (STATUS_CLOSED_MAN, 'Closed (Manual)'),
    ]

    # ── Direction choices ──
    DIRECTION_BUY  = 'BUY'
    DIRECTION_SELL = 'SELL'
    DIRECTION_CHOICES = [
        (DIRECTION_BUY,  'Buy (Long)'),
        (DIRECTION_SELL, 'Sell (Short)'),
    ]

    # ── Fields ──
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades')
    symbol        = models.CharField(max_length=20)

    direction     = models.CharField(max_length=4, choices=DIRECTION_CHOICES,
                                     default=DIRECTION_BUY)
    quantity      = models.DecimalField(max_digits=15, decimal_places=6, default=1)
    amount        = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    entry_price   = models.DecimalField(max_digits=20, decimal_places=6)
    take_profit   = models.DecimalField(max_digits=20, decimal_places=6)
    stop_loss     = models.DecimalField(max_digits=20, decimal_places=6)
    tp_percent    = models.DecimalField(max_digits=5, decimal_places=2)
    sl_percent    = models.DecimalField(max_digits=5, decimal_places=2)
    current_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                     default=STATUS_OPEN)
    pnl           = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    created_at    = models.DateTimeField(default=timezone.now)
    closed_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.symbol} | {self.direction} | {self.status}"

    @property
    def is_open(self):
        """Quick check if trade is still active."""
        return self.status == self.STATUS_OPEN

    @property
    def pnl_dollar(self):
        """Direction-aware PnL in dollars."""
        if not self.current_price or not self.entry_price:
            return 0
        entry   = float(self.entry_price)
        current = float(self.current_price)
        qty     = float(self.quantity)

        if self.direction == self.DIRECTION_SELL:
            return (entry - current) * qty
        return (current - entry) * qty

    @property
    def pnl_percent(self):
        """PnL as percentage."""
        if not self.pnl:
            return 0
        return float(self.pnl)

    @property
    def pnl_display(self):
        """Return PnL with + or - sign for display."""
        if self.pnl is None:
            return 'N/A'
        sign = '+' if self.pnl >= 0 else ''
        return f"{sign}{self.pnl:.2f}"

    @property
    def status_badge_class(self):
        """CSS class for status badge color."""
        return {
            self.STATUS_OPEN:       'badge-open',
            self.STATUS_CLOSED_TP:  'badge-tp',
            self.STATUS_CLOSED_SL:  'badge-sl',
            self.STATUS_CLOSED_MAN: 'badge-manual',
        }.get(self.status, 'badge-open')


class AgentConfig(models.Model):
    """
    Stores bot settings for each user.
    Each user has exactly one config.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='agent_config'
    )

    # Bot on/off switch
    is_active = models.BooleanField(default=False)

    # Confidence thresholds per market
    min_confidence_crypto = models.FloatField(default=65.0)
    min_confidence_forex  = models.FloatField(default=62.0)
    min_confidence_gold   = models.FloatField(default=63.0)

    # Risk settings
    max_open_trades     = models.IntegerField(default=3)
    cooldown_minutes    = models.IntegerField(default=30)
    daily_loss_limit    = models.IntegerField(default=3)

    # Symbols user selected for bot to trade
    selected_symbols = models.JSONField(
        default=list,
        help_text='List of symbols bot is allowed to trade'
    )

    # Bot fixed sizing (set by user in Strategy Settings)
    bot_fixed_quantity = models.DecimalField(max_digits=15, decimal_places=6, default=1)
    bot_fixed_amount   = models.DecimalField(max_digits=15, decimal_places=2, default=100)

    # Stats tracking
    total_bot_trades  = models.IntegerField(default=0)
    total_bot_wins    = models.IntegerField(default=0)
    total_bot_losses  = models.IntegerField(default=0)
    daily_loss_count  = models.IntegerField(default=0)
    last_reset_date   = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = 'ACTIVE' if self.is_active else 'STOPPED'
        return f"{self.user.username} Bot [{status}]"

    @property
    def win_rate(self):
        total = self.total_bot_wins + self.total_bot_losses
        if total == 0:
            return 0
        return round((self.total_bot_wins / total) * 100, 1)


class BotLog(models.Model):
    """
    Stores bot activity log entries.
    Shows user what the bot did and why.
    """
    ACTION_SCAN    = 'SCAN'
    ACTION_OPEN    = 'OPEN'
    ACTION_SKIP    = 'SKIP'
    ACTION_CLOSE   = 'CLOSE'
    ACTION_PAUSE   = 'PAUSE'
    ACTION_ERROR   = 'ERROR'

    ACTION_CHOICES = [
        (ACTION_SCAN,  'Scanned Symbol'),
        (ACTION_OPEN,  'Opened Trade'),
        (ACTION_SKIP,  'Skipped Signal'),
        (ACTION_CLOSE, 'Trade Closed'),
        (ACTION_PAUSE, 'Bot Paused'),
        (ACTION_ERROR, 'Error Occurred'),
    ]

    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bot_logs')
    action    = models.CharField(max_length=10, choices=ACTION_CHOICES)
    symbol    = models.CharField(max_length=20, blank=True)
    message   = models.TextField()
    direction = models.CharField(max_length=10, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} | {self.action} | {self.symbol} | {self.timestamp}"


# ─────────────────────────────────────────────────────
#  CHATBOT MODELS
# ─────────────────────────────────────────────────────

class Conversation(models.Model):
    """A chat conversation/session that groups multiple messages."""
    user       = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='conversations'
    )
    title      = models.CharField(max_length=100, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username}: {self.title}"

    @property
    def message_count(self):
        return self.messages.count()

    @property
    def preview(self):
        first_msg = self.messages.filter(role='user').first()
        return first_msg.message[:60] if first_msg else 'Empty chat'


class ChatMessage(models.Model):
    """A single chat message (user or bot)."""
    ROLE_USER = 'user'
    ROLE_BOT  = 'bot'
    ROLE_CHOICES = [(ROLE_USER, 'User'), (ROLE_BOT, 'Bot')]

    user         = models.ForeignKey(User, on_delete=models.CASCADE,
                                     related_name='chat_messages')
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages', null=True, blank=True
    )
    role         = models.CharField(max_length=10, choices=ROLE_CHOICES)
    message      = models.TextField()
    image        = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    metadata     = models.JSONField(default=dict, blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user.username} [{self.role}]: {self.message[:50]}"


# ─────────────────────────────────────────────────────--
#  ACCOUNT BALANCE MODEL
# ─────────────────────────────────────────────────────

class UserBalance(models.Model):
    """Virtual paper-trading account balance per user."""
    user             = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='balance'
    )
    starting_balance = models.DecimalField(max_digits=15, decimal_places=2,
                                           default=10000)
    current_balance  = models.DecimalField(max_digits=15, decimal_places=2,
                                           default=10000)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: ${self.current_balance}"

    @property
    def total_pnl(self):
        """Net profit/loss since start."""
        return float(self.current_balance) - float(self.starting_balance)

    @property
    def pnl_percent(self):
        """PnL as percentage of starting balance."""
        if self.starting_balance == 0:
            return 0
        return (self.total_pnl / float(self.starting_balance)) * 100