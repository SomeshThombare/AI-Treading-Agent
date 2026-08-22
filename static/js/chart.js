/**
 * static/js/chart.js
 *
 * Handles TradingView widget + TP/SL canvas overlay.
 *
 * Features:
 *   - Renders TradingView live chart
 *   - Draws colored TP/SL/Entry lines on canvas overlay
 *   - Switches symbol and interval dynamically
 *   - Syncs canvas size with chart
 */

// ── State ──
let curSymTV  = 'BINANCE:BTCUSDT';
let curSymRaw = 'BTCUSDT';
let curIv     = '1';

// Canvas context
let canvas    = null;
let ctx       = null;

// Latest data from API
let latestPrice  = null;
let latestTrades = [];


/**
 * Initialize chart and canvas overlay.
 * Call this once on page load.
 */
function initChart(defaultSymbol = 'BINANCE:BTCUSDT', defaultRaw = 'BTCUSDT') {
  curSymTV  = defaultSymbol;
  curSymRaw = defaultRaw;

  canvas = document.getElementById('tpsl-canvas');
  if (canvas) ctx = canvas.getContext('2d');

  buildWidget();
  window.addEventListener('resize', syncCanvas);
}


/**
 * Build or rebuild TradingView widget.
 * Called on symbol/interval change.
 */
function buildWidget() {
  const container = document.getElementById('tradingview_chart');
  if (!container) return;
  container.innerHTML = '';

  // eslint-disable-next-line no-new
  new TradingView.widget({
    width:        '100%',
    height:       480,
    symbol:       curSymTV,
    interval:     curIv,
    timezone:     'Asia/Kolkata',
    theme:        'dark',
    style:        '1',
    locale:       'en',
    toolbar_bg:   '#111827',
    container_id: 'tradingview_chart',
    allow_symbol_change: true,
    studies: [
      'MAExp@tv-basicstudies',  // EMA overlay
      'RSI@tv-basicstudies',    // RSI panel
    ],
  });

  // Sync canvas after widget loads
  setTimeout(syncCanvas, 700);
}


/**
 * Switch to a different symbol.
 * Updates chart and signal panel.
 */
function switchSymbol(tvSym, rawSym, btn) {
  curSymTV  = tvSym;
  curSymRaw = rawSym;

  // Update active button
  if (btn) {
    document.querySelectorAll('.sym-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }

  buildWidget();

  // Notify dashboard.js to refresh data for new symbol
  if (typeof onSymbolChanged === 'function') {
    onSymbolChanged(rawSym);
  }
}


/**
 * Switch to a different time interval.
 */
function switchInterval(iv, btn) {
  curIv = iv;
  document.querySelectorAll('.iv-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  buildWidget();
}


/**
 * Sync canvas size to match chart dimensions.
 * Called on load, resize, and symbol change.
 */
function syncCanvas() {
  if (!canvas) return;

  const tvEl = document.getElementById('tradingview_chart');
  if (!tvEl) return;

  const w = tvEl.offsetWidth  || 800;
  const h = tvEl.offsetHeight || 480;

  canvas.width  = w;
  canvas.height = h;

  drawLines();
}


/**
 * Draw TP/SL/Entry lines on canvas overlay.
 * Uses latest trade data and price from API.
 */
function drawLines() {
  if (!ctx || !canvas) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Filter trades for current symbol
  const trades = latestTrades.filter(t => t.symbol === curSymRaw);
  if (!trades.length || !latestPrice) return;

  const W = canvas.width;
  const H = canvas.height;

  // Build price range from all TP/SL/entry + current price
  const allPrices = [];
  trades.forEach(t => { allPrices.push(t.entry, t.tp, t.sl); });
  allPrices.push(latestPrice);

  const priceMax = Math.max(...allPrices) * 1.003;
  const priceMin = Math.min(...allPrices) * 0.997;
  const priceRng = priceMax - priceMin || 1;

  // Chart area offsets (TradingView toolbar/axis padding)
  const TOP = 44;
  const BOT = 34;
  const chartH = H - TOP - BOT;

  // Map price to Y pixel
  const toY = p => TOP + chartH - ((p - priceMin) / priceRng) * chartH;

  trades.forEach(t => {
    const yEntry = toY(t.entry);
    const yTP    = toY(t.tp);
    const ySL    = toY(t.sl);

    // ── Entry line (white dashed) ──
    _drawLine(ctx, yEntry, W, {
      color:     'rgba(255,255,255,0.5)',
      dash:      [6, 4],
      lineWidth: 1.5,
      label:     `⚡ Entry  $${_fmt(t.entry)}`,
      labelY:    yEntry - 5,
      labelX:    10,
      labelColor:'rgba(255,255,255,0.7)',
    });

    // ── Take Profit line (cyan) ──
    _drawLine(ctx, yTP, W, {
      color:     '#00e5ff',
      glow:      '#00e5ff',
      lineWidth: 2,
      label:     `✅ TP +${t.tp_pct}%  $${_fmt(t.tp)}`,
      labelY:    yTP - 5,
      labelX:    10,
      labelColor:'#00e5ff',
    });

    // ── Stop Loss line (orange) ──
    _drawLine(ctx, ySL, W, {
      color:     '#ff9800',
      glow:      '#ff9800',
      lineWidth: 2,
      label:     `🛑 SL -${t.sl_pct}%  $${_fmt(t.sl)}`,
      labelY:    ySL + 14,
      labelX:    10,
      labelColor:'#ff9800',
    });
  });

  // ── Current price line (green dashed) ──
  if (latestPrice) {
    const yCur = toY(latestPrice);
    _drawLine(ctx, yCur, W, {
      color:     'rgba(0,230,118,0.7)',
      dash:      [4, 6],
      lineWidth: 1.2,
      label:     `● $${latestPrice.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:4})}`,
      labelY:    yCur - 5,
      labelX:    W - 130,
      labelColor:'#00e676',
    });
  }
}


/**
 * Helper — draw a horizontal line with optional glow and label.
 */
function _drawLine(ctx, y, width, opts = {}) {
  ctx.save();

  if (opts.dash) ctx.setLineDash(opts.dash);
  if (opts.glow) {
    ctx.shadowColor = opts.glow;
    ctx.shadowBlur  = 6;
  }

  ctx.strokeStyle = opts.color || '#ffffff';
  ctx.lineWidth   = opts.lineWidth || 1;

  ctx.beginPath();
  ctx.moveTo(0, y);
  ctx.lineTo(width, y);
  ctx.stroke();

  if (opts.label) {
    ctx.shadowBlur  = 0;
    ctx.setLineDash([]);
    ctx.fillStyle   = opts.labelColor || opts.color;
    ctx.font        = 'bold 11px monospace';
    ctx.fillText(opts.label, opts.labelX || 10, opts.labelY || y - 5);
  }

  ctx.restore();
}


/**
 * Update canvas with latest trade and price data.
 * Called by dashboard.js every 5 seconds.
 */
function updateChartOverlay(trades, price, symbol) {
  latestTrades = (trades || []).map(t => ({ ...t, symbol }));
  latestPrice  = price;
  drawLines();
}


/**
 * Format price for display.
 */
function _fmt(price) {
  if (!price) return '—';
  if (price >= 1000) return price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  if (price >= 1)    return price.toFixed(4);
  return price.toFixed(6);
}