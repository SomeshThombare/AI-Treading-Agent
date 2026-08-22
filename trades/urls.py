"""trades/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    # Existing
    path('dashboard/',              views.dashboard,          name='dashboard'),
    path('create/',                 views.create_trade,       name='create_trade'),
    path('close/<int:trade_id>/',   views.close_trade_manual, name='close_trade'),
    path('detail/<int:trade_id>/',  views.trade_detail,       name='trade_detail'),
    path('price/<str:symbol>/',     views.price_api,          name='price_api'),
    path('ai-suggest/<str:symbol>/',views.ai_suggest,         name='ai_suggest'),

    # Bot
    path('bot/',          views.bot_dashboard, name='bot_dashboard'),
    path('bot/toggle/',   views.bot_toggle,    name='bot_toggle'),
    path('bot/settings/', views.bot_settings,  name='bot_settings'),

    # Report  ← THESE ARE MISSING IN YOUR FILE
    path('report/',          views.report_config,   name='report_config'),
    path('report/generate/', views.report_generate, name='report_generate'),

   # ── Chatbot URLs ──
    path('chat/',                       views.chat_page,            name='chat_page'),
    path('chat/send/',                  views.chat_send,            name='chat_send'),
    path('chat/status/',                views.chat_status,          name='chat_status'),
    path('chat/conversations/',         views.conversations_list,   name='conversations_list'),
    path('chat/conversation/new/',      views.conversation_new,     name='conversation_new'),
    path('chat/conversation/<int:conv_id>/messages/', views.conversation_messages, name='conversation_messages'),
    path('chat/conversation/<int:conv_id>/delete/',   views.conversation_delete,   name='conversation_delete'),
]