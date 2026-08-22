"""
trades/reports/pdf_generator.py

Generates complete PDF portfolio report using ReportLab.

Sections in the PDF:
  1. Cover Page (branding, user, date range)
  2. Executive Summary (key stats)
  3. Equity Curve chart
  4. Win/Loss Pie chart + PnL by Symbol bar chart
  5. Market Distribution donut chart
  6. Closed Trades Table
  7. Open Trades Table
  8. Bot Performance section (if applicable)

Returns BytesIO buffer with PDF that can be sent to user.
"""

import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas as pdfcanvas

from .chart_builder import build_all_charts, get_theme

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

def export(report_data):
    return generate_pdf_report(report_data)
# ─────────────────────────────────────────────────────
#  Color Themes for PDF
# ─────────────────────────────────────────────────────

PDF_DARK = {
    'primary':    HexColor('#0a0d14'),
    'surface':    HexColor('#111827'),
    'border':     HexColor('#1e2d45'),
    'text':       HexColor('#e2e8f0'),
    'muted':      HexColor('#64748b'),
    'accent':     HexColor('#00e5ff'),
    'green':      HexColor('#00e676'),
    'red':        HexColor('#ff1744'),
    'yellow':     HexColor('#ffd600'),
    'header_bg':  HexColor('#1F3864'),
    'row_alt':    HexColor('#0d1320'),
    'page_bg':    HexColor('#ffffff'),
}

PDF_LIGHT = {
    'primary':    HexColor('#1e293b'),
    'surface':    HexColor('#f8fafc'),
    'border':     HexColor('#cbd5e1'),
    'text':       HexColor('#1e293b'),
    'muted':      HexColor('#64748b'),
    'accent':     HexColor('#0ea5e9'),
    'green':      HexColor('#16a34a'),
    'red':        HexColor('#dc2626'),
    'yellow':     HexColor('#ca8a04'),
    'header_bg':  HexColor('#1e293b'),
    'row_alt':    HexColor('#f1f5f9'),
    'page_bg':    HexColor('#ffffff'),
}


def get_pdf_colors(theme='dark'):
    return PDF_DARK if theme == 'dark' else PDF_LIGHT


# ─────────────────────────────────────────────────────
#  Main Generator Function
# ─────────────────────────────────────────────────────

def generate_pdf_report(report_data, theme='light'):
    """
    Generate complete PDF report.

    Args:
        report_data: dict from collect_report_data()
        theme:       'dark' or 'light'

    Returns:
        BytesIO buffer with PDF bytes
    """
    logger.info(f"[PDF] Generating report (theme: {theme})")

    colors = get_pdf_colors(theme)

    # Build all charts in matching theme
    chart_theme = 'dark' if theme == 'dark' else 'light'
    charts = build_all_charts(report_data, theme=chart_theme)

    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title='Portfolio Report',
        author='AI Trading Agent',
    )

    # Get styles
    styles = _create_styles(colors)

    # Build content
    story = []

    # ── 1. Cover Page ──
    story.extend(_build_cover_page(report_data, styles, colors))
    story.append(PageBreak())

    # ── 2. Executive Summary ──
    story.extend(_build_executive_summary(report_data, styles, colors))
    story.append(Spacer(1, 0.5*cm))

    # ── 3. Equity Curve ──
    story.extend(_build_chart_section(
        'Equity Curve', charts['equity'], styles, colors
    ))
    story.append(Spacer(1, 0.3*cm))

    # ── 4. Win/Loss Pie + Bar Chart ──
    story.append(PageBreak())
    story.extend(_build_chart_section(
        'Win / Loss Distribution', charts['pie'], styles, colors
    ))
    story.append(Spacer(1, 0.3*cm))
    story.extend(_build_chart_section(
        'PnL by Symbol', charts['bar'], styles, colors
    ))

    # ── 5. Market Distribution Donut ──
    story.append(PageBreak())
    story.extend(_build_chart_section(
        'Trade Distribution by Market', charts['donut'], styles, colors
    ))
    story.append(Spacer(1, 0.5*cm))

    # ── 6. Closed Trades Table ──
    story.append(PageBreak())
    story.extend(_build_closed_trades_section(report_data, styles, colors))

    # ── 7. Open Trades Table ──
    if report_data['open_trades']:
        story.append(Spacer(1, 0.5*cm))
        story.extend(_build_open_trades_section(report_data, styles, colors))

    # ── 8. Bot Performance ──
    if report_data['bot']['configured']:
        story.append(PageBreak())
        story.extend(_build_bot_section(report_data, styles, colors))

    # Build PDF
    doc.build(
        story,
        onFirstPage=lambda c, d: _draw_page_decoration(c, d, colors, is_cover=True),
        onLaterPages=lambda c, d: _draw_page_decoration(c, d, colors, is_cover=False),
    )

    buffer.seek(0)
    logger.info(f"[PDF] Generated successfully — {len(buffer.getvalue())} bytes")
    return buffer


# ─────────────────────────────────────────────────────
#  Style Creation
# ─────────────────────────────────────────────────────

def _create_styles(colors):
    """Create all paragraph styles used in the PDF."""
    base = getSampleStyleSheet()

    return {
        'title': ParagraphStyle(
            'Title', parent=base['Title'],
            fontSize=28, leading=34,
            textColor=colors['header_bg'],
            alignment=TA_CENTER,
            spaceAfter=8,
            fontName='Helvetica-Bold',
        ),
        'subtitle': ParagraphStyle(
            'Subtitle', parent=base['Normal'],
            fontSize=13, leading=18,
            textColor=colors['muted'],
            alignment=TA_CENTER,
            spaceAfter=24,
            fontName='Helvetica',
        ),
        'h1': ParagraphStyle(
            'H1', parent=base['Heading1'],
            fontSize=18, leading=22,
            textColor=colors['header_bg'],
            spaceBefore=12, spaceAfter=10,
            fontName='Helvetica-Bold',
        ),
        'h2': ParagraphStyle(
            'H2', parent=base['Heading2'],
            fontSize=14, leading=18,
            textColor=colors['accent'],
            spaceBefore=10, spaceAfter=8,
            fontName='Helvetica-Bold',
        ),
        'body': ParagraphStyle(
            'Body', parent=base['Normal'],
            fontSize=10, leading=14,
            textColor=colors['text'],
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            fontName='Helvetica',
        ),
        'small': ParagraphStyle(
            'Small', parent=base['Normal'],
            fontSize=8, leading=11,
            textColor=colors['muted'],
            fontName='Helvetica',
        ),
        'cover_label': ParagraphStyle(
            'CoverLabel', parent=base['Normal'],
            fontSize=10, leading=13,
            textColor=colors['muted'],
            alignment=TA_CENTER,
            spaceAfter=4,
            fontName='Helvetica',
        ),
        'cover_value': ParagraphStyle(
            'CoverValue', parent=base['Normal'],
            fontSize=14, leading=18,
            textColor=colors['text'],
            alignment=TA_CENTER,
            spaceAfter=14,
            fontName='Helvetica-Bold',
        ),
    }


# ─────────────────────────────────────────────────────
#  Cover Page
# ─────────────────────────────────────────────────────

def _build_cover_page(data, styles, colors):
    """First page — branding + summary stats."""
    story = []

    story.append(Spacer(1, 4*cm))

    # ── Logo / Brand ──
    story.append(Paragraph(
        '<font color="#00e5ff">⬡</font> <font color="%s">AI TRADE</font>' % colors['header_bg'],
        ParagraphStyle('Logo',
            fontSize=42, leading=50,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=12)
    ))

    # ── Title ──
    story.append(Paragraph('PORTFOLIO REPORT', styles['title']))

    # ── User and date range ──
    user        = data['user']
    start       = data['start_date'].strftime('%b %d, %Y')
    end         = data['end_date'].strftime('%b %d, %Y')

    story.append(Paragraph(
        f'<b>{user.username}</b><br/>{start} — {end}',
        styles['subtitle']
    ))

    story.append(Spacer(1, 1.5*cm))

    # ── Quick Stats Table ──
    s = data['summary']
    pnl = s['total_pnl']
    pnl_color = colors['green'] if pnl >= 0 else colors['red']

    stats_data = [
        [
            _stat_cell(s['total_trades'], 'Total Trades', colors['accent'], colors),
            _stat_cell(f"{s['win_rate']}%", 'Win Rate',
                       colors['green'] if s['win_rate'] >= 50 else colors['red'], colors),
            _stat_cell(f"{'+' if pnl >= 0 else ''}{pnl}%", 'Total PnL', pnl_color, colors),
            _stat_cell(s['open_trades'], 'Open Now', colors['yellow'], colors),
        ]
    ]
    stats_table = Table(stats_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
    stats_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(stats_table)

    story.append(Spacer(1, 3*cm))

    # ── Footer ──
    gen_at = data['generated_at'].strftime('%B %d, %Y · %H:%M')
    story.append(Paragraph(
        f'<font color="{colors["muted"]}">Generated on {gen_at}</font><br/>'
        f'<font color="{colors["muted"]}">AI Trading Agent · LSTM-Powered Paper Trading</font>',
        ParagraphStyle('Footer',
            fontSize=9, alignment=TA_CENTER,
            leading=14, fontName='Helvetica')
    ))

    return story


def _stat_cell(value, label, value_color, colors):
    """Build a single stat cell for the cover page."""
    cell_style = ParagraphStyle(
        'StatCell', alignment=TA_CENTER,
        fontSize=22, leading=26,
        textColor=value_color,
        fontName='Helvetica-Bold')
    label_style = ParagraphStyle(
        'StatLabel', alignment=TA_CENTER,
        fontSize=8, leading=11,
        textColor=colors['muted'],
        fontName='Helvetica')

    return [
        Paragraph(str(value), cell_style),
        Spacer(1, 2*mm),
        Paragraph(label.upper(), label_style),
    ]


# ─────────────────────────────────────────────────────
#  Executive Summary
# ─────────────────────────────────────────────────────

def _build_executive_summary(data, styles, colors):
    """Section showing key statistics in detail."""
    story = []
    s = data['summary']

    story.append(Paragraph('Executive Summary', styles['h1']))
    story.append(_horizontal_rule(colors))

    # Build stats grid
    pnl = s['total_pnl']
    pnl_color = '#00e676' if pnl >= 0 else '#ff1744'

    summary_text = f"""
    During the reporting period, a total of <b>{s['total_trades']}</b> trades were executed.
    Of these, <b>{s['closed_trades']}</b> have been closed and <b>{s['open_trades']}</b> remain open.
    The overall win rate stands at <b><font color="{pnl_color}">{s['win_rate']}%</font></b> with
    a cumulative profit/loss of <b><font color="{pnl_color}">
    {'+' if pnl >= 0 else ''}{pnl}%</font></b> across all closed positions.
    """
    story.append(Paragraph(summary_text, styles['body']))
    story.append(Spacer(1, 0.4*cm))

    # Key metrics table
    metrics_data = [
        ['Metric', 'Value'],
        ['Total Trades',        str(s['total_trades'])],
        ['Closed Trades',       str(s['closed_trades'])],
        ['Open Trades',         str(s['open_trades'])],
        ['Take Profit Wins',    str(s['wins'])],
        ['Stop Loss Losses',    str(s['losses'])],
        ['Manual Closes',       str(s['manual_closes'])],
        ['Win Rate',            f"{s['win_rate']}%"],
        ['Total PnL',           f"{'+' if pnl >= 0 else ''}{pnl}%"],
        ['Average PnL',         f"{data['avg_pnl']}%"],
    ]

    # Add best/worst trades
    if data['best_trade']:
        metrics_data.append([
            'Best Trade',
            f"{data['best_trade']['symbol']} (+{data['best_trade']['pnl']:.2f}%)"
        ])
    if data['worst_trade']:
        metrics_data.append([
            'Worst Trade',
            f"{data['worst_trade']['symbol']} ({data['worst_trade']['pnl']:.2f}%)"
        ])

    table = Table(metrics_data, colWidths=[7*cm, 7*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0),  colors['header_bg']),
        ('TEXTCOLOR',    (0,0), (-1,0),  white),
        ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 9.5),
        ('ALIGN',        (0,0), (-1,-1), 'LEFT'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, colors['row_alt']]),
        ('GRID',         (0,0), (-1,-1), 0.5, colors['border']),
        ('TOPPADDING',   (0,0), (-1,-1), 7),
        ('BOTTOMPADDING',(0,0), (-1,-1), 7),
        ('LEFTPADDING',  (0,0), (-1,-1), 12),
    ]))
    story.append(table)

    return story


# ─────────────────────────────────────────────────────
#  Chart Section
# ─────────────────────────────────────────────────────

def _build_chart_section(title, chart_buffer, styles, colors):
    """Render a chart with title."""
    story = []
    story.append(Paragraph(title, styles['h2']))

    # Reset buffer position then load as image
    chart_buffer.seek(0)
    img = RLImage(chart_buffer, width=16*cm, height=8*cm)
    story.append(img)

    return story


# ─────────────────────────────────────────────────────
#  Trade Tables
# ─────────────────────────────────────────────────────

def _build_closed_trades_section(data, styles, colors):
    """Table of all closed trades."""
    story = []
    story.append(Paragraph('Closed Trades', styles['h1']))
    story.append(_horizontal_rule(colors))
    story.append(Spacer(1, 0.2*cm))

    closed = data['closed_trades']

    if not closed:
        story.append(Paragraph(
            '<i>No closed trades in this period.</i>',
            styles['body']
        ))
        return story

    # Header + rows (limit 30 for PDF readability)
    rows = [['Date', 'Symbol', 'Entry', 'Exit', 'TP/SL', 'Result', 'PnL']]

    for t in closed[:30]:
        date    = t['closed_at'].strftime('%b %d') if t['closed_at'] else '—'
        entry   = f"${t['entry_price']:.4f}"
        exit_p  = f"${t['current_price']:.4f}" if t['current_price'] else '—'
        tp_sl   = f"+{t['tp_percent']}/-{t['sl_percent']}%"

        # Status with emoji
        if t['status'] == 'CLOSED_TP':
            result = '✓ TP'
        elif t['status'] == 'CLOSED_SL':
            result = '✗ SL'
        else:
            result = '◯ MAN'

        # PnL with color (using HTML in paragraph)
        if t['pnl'] is not None:
            pnl_val   = t['pnl']
            pnl_color = '#00b855' if pnl_val >= 0 else '#dc2626'
            pnl_text  = f"<font color='{pnl_color}'><b>{'+' if pnl_val >= 0 else ''}{pnl_val:.2f}%</b></font>"
        else:
            pnl_text  = '—'

        pnl_para = Paragraph(pnl_text, styles['small'])

        rows.append([date, t['symbol'], entry, exit_p, tp_sl, result, pnl_para])

    table = Table(rows, colWidths=[2*cm, 2.4*cm, 2.4*cm, 2.4*cm, 2.4*cm, 2*cm, 2*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),  (-1,0),  colors['header_bg']),
        ('TEXTCOLOR',    (0,0),  (-1,0),  white),
        ('FONTNAME',     (0,0),  (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0,0),  (-1,-1), 8.5),
        ('ALIGN',        (0,0),  (-1,-1), 'CENTER'),
        ('VALIGN',       (0,0),  (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, colors['row_alt']]),
        ('GRID',         (0,0),  (-1,-1), 0.4, colors['border']),
        ('TOPPADDING',   (0,0),  (-1,-1), 5),
        ('BOTTOMPADDING',(0,0),  (-1,-1), 5),
    ]))
    story.append(table)

    if len(closed) > 30:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            f'<i>Showing first 30 of {len(closed)} closed trades. '
            f'See Excel report for complete list.</i>',
            styles['small']
        ))

    return story


def _build_open_trades_section(data, styles, colors):
    """Table of currently open trades."""
    story = []
    story.append(Paragraph('Open Trades (Current Positions)', styles['h1']))
    story.append(_horizontal_rule(colors))
    story.append(Spacer(1, 0.2*cm))

    rows = [['Symbol', 'Market', 'Entry', 'Current', 'TP', 'SL', 'Opened']]

    for t in data['open_trades']:
        rows.append([
            t['symbol'],
            t['market'],
            f"${t['entry_price']:.4f}",
            f"${t['current_price']:.4f}" if t['current_price'] else '—',
            f"+{t['tp_percent']}%",
            f"-{t['sl_percent']}%",
            t['created_at'].strftime('%b %d, %H:%M'),
        ])

    table = Table(rows, colWidths=[2.4*cm, 2*cm, 2.4*cm, 2.4*cm, 2*cm, 2*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), colors['header_bg']),
        ('TEXTCOLOR',    (0,0), (-1,0), white),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 9),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, colors['row_alt']]),
        ('GRID',         (0,0), (-1,-1), 0.4, colors['border']),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
    ]))
    story.append(table)
    return story


# ─────────────────────────────────────────────────────
#  Bot Section
# ─────────────────────────────────────────────────────

def _build_bot_section(data, styles, colors):
    """Section about auto-trading bot performance."""
    story = []
    bot = data['bot']

    story.append(Paragraph('🤖 Auto Trading Bot Performance', styles['h1']))
    story.append(_horizontal_rule(colors))
    story.append(Spacer(1, 0.2*cm))

    # Status
    status_color = colors['green'] if bot['is_active'] else colors['muted']
    status_text  = 'ACTIVE' if bot['is_active'] else 'INACTIVE'

    intro = f"""
    The autonomous trading bot is currently
    <b><font color="{status_color.hexval()}">{status_text}</font></b>.
    It scans selected markets every 15 minutes and opens trades automatically
    when LSTM model confidence exceeds the configured threshold.
    """
    story.append(Paragraph(intro, styles['body']))
    story.append(Spacer(1, 0.3*cm))

    # Bot stats table
    bot_stats = [
        ['Metric', 'Value'],
        ['Bot Status',         status_text],
        ['Total Bot Trades',   str(bot['total_trades'])],
        ['Bot Wins',           str(bot['wins'])],
        ['Bot Losses',         str(bot['losses'])],
        ['Bot Win Rate',       f"{bot['win_rate']}%"],
        ['Selected Symbols',   ', '.join(bot['selected_symbols'][:6]) or 'None'],
        ['Max Open Trades',    str(bot['max_open_trades'])],
        ['Crypto Threshold',   f"{bot['min_conf_crypto']}%"],
        ['Forex Threshold',    f"{bot['min_conf_forex']}%"],
        ['Gold Threshold',     f"{bot['min_conf_gold']}%"],
    ]

    table = Table(bot_stats, colWidths=[6*cm, 8*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), colors['header_bg']),
        ('TEXTCOLOR',    (0,0), (-1,0), white),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 9.5),
        ('ALIGN',        (0,0), (-1,-1), 'LEFT'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, colors['row_alt']]),
        ('GRID',         (0,0), (-1,-1), 0.5, colors['border']),
        ('TOPPADDING',   (0,0), (-1,-1), 7),
        ('BOTTOMPADDING',(0,0), (-1,-1), 7),
        ('LEFTPADDING',  (0,0), (-1,-1), 12),
    ]))
    story.append(table)

    # Recent activity
    if bot['recent_logs']:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph('Recent Bot Activity', styles['h2']))

        log_rows = [['Time', 'Action', 'Symbol', 'Message']]
        for log in bot['recent_logs'][:10]:
            log_rows.append([
                log['timestamp'].strftime('%b %d %H:%M'),
                log['action'],
                log['symbol'] or '—',
                log['message'][:50] + ('...' if len(log['message']) > 50 else ''),
            ])

        log_table = Table(log_rows, colWidths=[2.8*cm, 2*cm, 2.4*cm, 8*cm])
        log_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), colors['header_bg']),
            ('TEXTCOLOR',    (0,0), (-1,0), white),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 8),
            ('ALIGN',        (0,0), (-1,-1), 'LEFT'),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, colors['row_alt']]),
            ('GRID',         (0,0), (-1,-1), 0.4, colors['border']),
            ('TOPPADDING',   (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',(0,0), (-1,-1), 5),
            ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ]))
        story.append(log_table)

    return story


# ─────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────

def _horizontal_rule(colors):
    """Decorative line under section headings."""
    table = Table([['']], colWidths=[16*cm], rowHeights=[1])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors['accent']),
    ]))
    return table


def _draw_page_decoration(canvas, doc, colors, is_cover=False):
    """Draw header and footer on every page."""
    canvas.saveState()

    if not is_cover:
        # Header line
        canvas.setStrokeColor(colors['accent'])
        canvas.setLineWidth(2)
        canvas.line(2*cm, A4[1] - 1.4*cm, A4[0] - 2*cm, A4[1] - 1.4*cm)

        # Header text
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors['muted'])
        canvas.drawString(2*cm, A4[1] - 1.1*cm, 'AI TRADING AGENT — Portfolio Report')
        canvas.drawRightString(
            A4[0] - 2*cm, A4[1] - 1.1*cm,
            datetime.now().strftime('%B %Y')
        )

    # Footer line
    canvas.setStrokeColor(colors['border'])
    canvas.setLineWidth(0.5)
    canvas.line(2*cm, 1.5*cm, A4[0] - 2*cm, 1.5*cm)

    # Footer text
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors['muted'])
    canvas.drawString(2*cm, 1*cm, 'AI Trading Agent · LSTM-Powered Paper Trading System')
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, f'Page {doc.page}')

    canvas.restoreState()