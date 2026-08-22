from django.contrib import admin
from .models import Trade

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'symbol', 'entry_price', 'take_profit', 'stop_loss', 'status', 'pnl', 'created_at']
    list_filter   = ['status', 'symbol']
    search_fields = ['user__username', 'symbol']
    readonly_fields = ['created_at', 'closed_at']
