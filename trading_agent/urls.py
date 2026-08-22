"""
Main URL configuration for AI Trading Agent.
Routes traffic to the right app.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect root URL to dashboard or login
    path('', RedirectView.as_view(url='/trades/dashboard/', permanent=False)),

    # Authentication routes (register, login, logout)
    path('accounts/', include('accounts.urls')),

    # Trade routes (dashboard, create, close, etc.)
    path('trades/', include('trades.urls')),
]

# chatbot
from django.conf import settings
from django.conf.urls.static import static

# Serve uploaded images during development
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )