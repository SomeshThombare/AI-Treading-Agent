"""
trades/forms.py
Form for creating a new paper trade.
"""

from django import forms
from .models import Trade


# Symbol choices - the markets the system supports
SYMBOL_CHOICES = [
    ('BTCUSDT', 'BTC/USDT — Bitcoin'),
    ('ETHUSDT', 'ETH/USDT — Ethereum'),
    ('BNBUSDT', 'BNB/USDT — BNB'),
    ('SOLUSDT', 'SOL/USDT — Solana'),
    ('XRPUSDT', 'XRP/USDT — Ripple'),
    ('EURUSD',  'EUR/USD — Euro/Dollar'),
    ('GBPUSD',  'GBP/USD — Pound/Dollar'),
    ('USDJPY',  'USD/JPY — Dollar/Yen'),
    ('XAUUSD',  'XAU/USD — Gold'),
    ('XAGUSD',  'XAG/USD — Silver'),
]

DIRECTION_CHOICES = [
    ('BUY',  'BUY (Long) — profit if price goes UP'),
    ('SELL', 'SELL (Short) — profit if price goes DOWN'),
]


class CreateTradeForm(forms.Form):
    """Form to create a new trade with direction, size, and TP/SL."""

    symbol = forms.ChoiceField(
        choices=SYMBOL_CHOICES,
        label='Trading Symbol',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

    direction = forms.ChoiceField(
        choices=DIRECTION_CHOICES,
        label='Trade Direction',
        initial='BUY',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

    quantity = forms.DecimalField(
        label='Quantity (units / lots)',
        min_value=0.000001,
        max_digits=15,
        decimal_places=6,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.000001',
            'placeholder': 'e.g. 0.5',
        }),
    )

    amount = forms.DecimalField(
        label='Amount Invested ($)',
        min_value=0.01,
        max_digits=15,
        decimal_places=2,
        initial=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.01',
            'placeholder': 'e.g. 5000',
        }),
    )

    tp_percent = forms.DecimalField(
        label='Take Profit (%)',
        min_value=0.1,
        max_value=100,
        decimal_places=2,
        initial=3.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.1',
            'placeholder': 'e.g. 4.5',
        }),
    )

    sl_percent = forms.DecimalField(
        label='Stop Loss (%)',
        min_value=0.1,
        max_value=100,
        decimal_places=2,
        initial=1.5,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.1',
            'placeholder': 'e.g. 2.0',
        }),
    )

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty <= 0:
            raise forms.ValidationError('Quantity must be greater than 0.')
        return qty

    def clean_amount(self):
        amt = self.cleaned_data.get('amount')
        if amt is not None and amt <= 0:
            raise forms.ValidationError('Amount must be greater than 0.')
        return amt