"""
trades/reports/chart_builder.py

Generates 4 matplotlib charts for the portfolio report:
  1. Equity Curve       (line chart)
  2. Win/Loss Ratio     (pie chart)
  3. PnL by Symbol      (bar chart)
  4. Trades by Market   (donut chart)

Each function returns a BytesIO buffer containing PNG image
that can be embedded directly into PDF or saved to disk.
"""

import io
import logging
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend (no GUI needed)
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge

logger = logging.getLogger(__name__)

# ── Color Themes ────────────────────────────────────────────────

THEME_DARK = {
    'bg':         '#0a0d14',
    'surface':    '#111827',
    'text':       '#e2e8f0',
    'muted':      '#64748b',
    'accent':     '#00e5ff',
    'green':      '#00e676',
    'red':        '#ff1744',
    'yellow':     '#ffd600',
    'orange':     '#ff9800',
    'purple':     '#a855f7',
    'grid':       '#1e2d45',
}

THEME_LIGHT = {
    'bg':         '#ffffff',
    'surface':    '#f8fafc',
    'text':       '#1e293b',
    'muted':      '#64748b',
    'accent':     '#0ea5e9',
    'green':      '#16a34a',
    'red':        '#dc2626',
    'yellow':     '#eab308',
    'orange':     '#ea580c',
    'purple':     '#9333ea',
    'grid':       '#e2e8f0',
}


def get_theme(theme_name='dark'):
    """Return color theme dict."""
    return THEME_DARK if theme_name == 'dark' else THEME_LIGHT


# ─────────────────────────────────────────────────────
#  CHART 1: Equity Curve (Line Chart)
# ─────────────────────────────────────────────────────

def build_equity_curve(equity_data, theme='dark'):
    """
    Cumulative PnL curve showing portfolio growth.

    Args:
        equity_data: list of dicts from data_collector
                     [{'index': 1, 'cumulative_pnl': 2.3}, ...]
        theme: 'dark' or 'light'

    Returns:
        BytesIO buffer with PNG image
    """
    colors = get_theme(theme)

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=120)
    fig.patch.set_facecolor(colors['bg'])
    ax.set_facecolor(colors['surface'])

    # No data case
    if not equity_data:
        ax.text(0.5, 0.5, 'No closed trades yet',
                ha='center', va='center',
                color=colors['muted'], fontsize=14,
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return _save_to_buffer(fig)

    # Extract data
    x_vals = [d['index']          for d in equity_data]
    y_vals = [d['cumulative_pnl'] for d in equity_data]

    # Determine final color (green=profit, red=loss)
    final = y_vals[-1] if y_vals else 0
    line_color = colors['green'] if final >= 0 else colors['red']

    # ── Plot line ──
    ax.plot(x_vals, y_vals,
            color=line_color, linewidth=2.5,
            marker='o', markersize=4,
            markerfacecolor=line_color,
            markeredgecolor=colors['bg'],
            markeredgewidth=1.5,
            zorder=3)

    # ── Fill area under curve ──
    ax.fill_between(x_vals, y_vals, 0,
                    where=[y >= 0 for y in y_vals],
                    color=colors['green'], alpha=0.15,
                    interpolate=True)
    ax.fill_between(x_vals, y_vals, 0,
                    where=[y < 0 for y in y_vals],
                    color=colors['red'], alpha=0.15,
                    interpolate=True)

    # ── Zero line ──
    ax.axhline(y=0, color=colors['grid'], linewidth=1,
               linestyle='--', alpha=0.7, zorder=1)

    # ── Final value annotation ──
    ax.annotate(f'{final:+.2f}%',
                xy=(x_vals[-1], y_vals[-1]),
                xytext=(10, 5), textcoords='offset points',
                fontsize=11, fontweight='bold',
                color=line_color)

    # ── Styling ──
    ax.set_title('Equity Curve — Cumulative PnL',
                 color=colors['text'], fontsize=14, pad=15,
                 fontweight='bold')
    ax.set_xlabel('Trade #', color=colors['muted'], fontsize=10)
    ax.set_ylabel('Cumulative PnL (%)', color=colors['muted'], fontsize=10)

    ax.tick_params(colors=colors['muted'])
    ax.grid(True, color=colors['grid'], alpha=0.3, linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(colors['grid'])
    ax.spines['left'].set_color(colors['grid'])

    plt.tight_layout()
    return _save_to_buffer(fig)


# ─────────────────────────────────────────────────────
#  CHART 2: Win/Loss Pie Chart
# ─────────────────────────────────────────────────────

def build_win_loss_pie(win_loss_data, theme='dark'):
    """
    Pie chart showing TP wins vs SL losses vs Manual closes.

    Args:
        win_loss_data: dict {'tp_wins': 5, 'sl_losses': 3, 'manual_closes': 1}
        theme: 'dark' or 'light'

    Returns:
        BytesIO buffer with PNG image
    """
    colors = get_theme(theme)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    fig.patch.set_facecolor(colors['bg'])

    wins   = win_loss_data.get('tp_wins',       0)
    losses = win_loss_data.get('sl_losses',     0)
    manual = win_loss_data.get('manual_closes', 0)

    total = wins + losses + manual

    # No data case
    if total == 0:
        ax.text(0.5, 0.5, 'No closed trades yet',
                ha='center', va='center',
                color=colors['muted'], fontsize=14,
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return _save_to_buffer(fig)

    # ── Build slices ──
    sizes      = []
    labels     = []
    pie_colors = []

    if wins > 0:
        sizes.append(wins)
        labels.append(f'TP Wins ({wins})')
        pie_colors.append(colors['green'])

    if losses > 0:
        sizes.append(losses)
        labels.append(f'SL Losses ({losses})')
        pie_colors.append(colors['red'])

    if manual > 0:
        sizes.append(manual)
        labels.append(f'Manual ({manual})')
        pie_colors.append(colors['yellow'])

    # ── Plot pie ──
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=pie_colors,
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops=dict(width=0.5, edgecolor=colors['bg'], linewidth=2),
        textprops=dict(color=colors['text'], fontsize=10, fontweight='500'),
        pctdistance=0.75,
    )

    # Style percentage text
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(11)

    # ── Center label ──
    win_rate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0
    ax.text(0, 0.05, f'{win_rate}%',
            ha='center', va='center',
            color=colors['accent'], fontsize=24, fontweight='bold')
    ax.text(0, -0.15, 'Win Rate',
            ha='center', va='center',
            color=colors['muted'], fontsize=10)

    ax.set_title('Win / Loss Distribution',
                 color=colors['text'], fontsize=14, pad=15,
                 fontweight='bold')

    plt.tight_layout()
    return _save_to_buffer(fig)


# ─────────────────────────────────────────────────────
#  CHART 3: PnL by Symbol (Bar Chart)
# ─────────────────────────────────────────────────────

def build_pnl_by_symbol(pnl_data, theme='dark'):
    """
    Horizontal bar chart of cumulative PnL grouped by symbol.

    Args:
        pnl_data: list of dicts from data_collector
                  [{'symbol': 'BTCUSDT', 'pnl': 5.2, 'count': 3}, ...]
        theme: 'dark' or 'light'

    Returns:
        BytesIO buffer with PNG image
    """
    colors = get_theme(theme)

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    fig.patch.set_facecolor(colors['bg'])
    ax.set_facecolor(colors['surface'])

    # No data case
    if not pnl_data:
        ax.text(0.5, 0.5, 'No closed trades yet',
                ha='center', va='center',
                color=colors['muted'], fontsize=14,
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return _save_to_buffer(fig)

    # Limit to top 8 symbols by absolute PnL
    sorted_data = sorted(pnl_data, key=lambda x: abs(x['pnl']), reverse=True)[:8]
    sorted_data = sorted(sorted_data, key=lambda x: x['pnl'])  # back to ascending for chart

    symbols = [d['symbol'] for d in sorted_data]
    pnls    = [d['pnl']    for d in sorted_data]
    counts  = [d['count']  for d in sorted_data]

    # Color each bar by profit/loss
    bar_colors = [colors['green'] if p >= 0 else colors['red'] for p in pnls]

    # ── Plot bars ──
    bars = ax.barh(symbols, pnls, color=bar_colors,
                   edgecolor=colors['bg'], linewidth=1.5,
                   height=0.65)

    # ── Add value labels at end of each bar ──
    for i, (bar, pnl, cnt) in enumerate(zip(bars, pnls, counts)):
        x_pos = bar.get_width()
        # Offset label position
        offset = max(abs(p) for p in pnls) * 0.02
        if pnl >= 0:
            x_text = x_pos + offset
            ha     = 'left'
        else:
            x_text = x_pos - offset
            ha     = 'right'

        ax.text(x_text, bar.get_y() + bar.get_height()/2,
                f'{pnl:+.2f}% ({cnt})',
                va='center', ha=ha,
                color=colors['text'], fontsize=9, fontweight='600')

    # ── Zero line ──
    ax.axvline(x=0, color=colors['grid'], linewidth=1, linestyle='-', alpha=0.7)

    # ── Styling ──
    ax.set_title('PnL by Symbol',
                 color=colors['text'], fontsize=14, pad=15,
                 fontweight='bold')
    ax.set_xlabel('Cumulative PnL (%)', color=colors['muted'], fontsize=10)

    ax.tick_params(axis='y', colors=colors['text'], labelsize=10)
    ax.tick_params(axis='x', colors=colors['muted'], labelsize=9)
    ax.grid(True, axis='x', color=colors['grid'], alpha=0.3, linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(colors['grid'])
    ax.spines['left'].set_color(colors['grid'])

    # Add headroom for labels
    max_abs = max(abs(min(pnls)), abs(max(pnls))) * 1.25
    ax.set_xlim(-max_abs, max_abs)

    plt.tight_layout()
    return _save_to_buffer(fig)


# ─────────────────────────────────────────────────────
#  CHART 4: Trades by Market (Donut Chart)
# ─────────────────────────────────────────────────────

def build_market_distribution(market_data, theme='dark'):
    """
    Donut chart of trade distribution by market type.

    Args:
        market_data: dict {'Crypto': 5, 'Forex': 3, 'Gold': 2}
        theme: 'dark' or 'light'

    Returns:
        BytesIO buffer with PNG image
    """
    colors = get_theme(theme)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    fig.patch.set_facecolor(colors['bg'])

    if not market_data or sum(market_data.values()) == 0:
        ax.text(0.5, 0.5, 'No trades yet',
                ha='center', va='center',
                color=colors['muted'], fontsize=14,
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return _save_to_buffer(fig)

    # Market color mapping
    market_colors = {
        'Crypto':  colors['accent'],
        'Forex':   colors['green'],
        'Gold':    colors['yellow'],
        'Unknown': colors['muted'],
    }

    # Build slices
    labels    = []
    sizes     = []
    pie_cols  = []
    total     = sum(market_data.values())

    for market, count in market_data.items():
        labels.append(f'{market} ({count})')
        sizes.append(count)
        pie_cols.append(market_colors.get(market, colors['purple']))

    # ── Plot donut ──
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=pie_cols,
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops=dict(width=0.45, edgecolor=colors['bg'], linewidth=3),
        textprops=dict(color=colors['text'], fontsize=10, fontweight='500'),
        pctdistance=0.78,
    )

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)

    # ── Center text ──
    ax.text(0, 0.05, f'{total}',
            ha='center', va='center',
            color=colors['accent'], fontsize=28, fontweight='bold')
    ax.text(0, -0.18, 'Total Trades',
            ha='center', va='center',
            color=colors['muted'], fontsize=10)

    ax.set_title('Trade Distribution by Market',
                 color=colors['text'], fontsize=14, pad=15,
                 fontweight='bold')

    plt.tight_layout()
    return _save_to_buffer(fig)


# ─────────────────────────────────────────────────────
#  Helper — Save figure to BytesIO buffer
# ─────────────────────────────────────────────────────

def _save_to_buffer(fig):
    """Save matplotlib figure to BytesIO and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png',
                facecolor=fig.get_facecolor(),
                bbox_inches='tight',
                dpi=120)
    buf.seek(0)
    plt.close(fig)
    return buf


# ─────────────────────────────────────────────────────
#  Build All Charts at Once
# ─────────────────────────────────────────────────────

def build_all_charts(report_data, theme='dark'):
    """
    Build all 4 charts and return as dict of BytesIO buffers.

    Args:
        report_data: dict from collect_report_data()
        theme: 'dark' or 'light'

    Returns:
        dict: {'equity', 'pie', 'bar', 'donut'}
    """
    logger.info(f"[CHARTS] Building all 4 charts (theme: {theme})")

    return {
        'equity': build_equity_curve(   report_data['equity_curve'],   theme),
        'pie':    build_win_loss_pie(   report_data['win_loss_count'], theme),
        'bar':    build_pnl_by_symbol(  report_data['pnl_by_symbol'],  theme),
        'donut':  build_market_distribution(report_data['trades_by_market'], theme),
    }