/**
 * static/js/dashboard.js
 *
 * Dashboard logic:
 *   - Refreshes live prices every 5 seconds
 *   - Updates Buy/Sell signal panel
 *   - Shows TP/SL distance info
 *   - Detects auto-closed trades and reloads page
 *   - Updates signal column in trades table
 *   - Draws equity curve on canvas
 */

// ── Data from Django template (set in dashboard.html) ──
// window.OPEN_TRADES  = [ {id, symbol, entry, tp, sl, tp_pct, sl_pct} ]
// window.CLOSED_PNL   = [ 1.23, -0.45, ... ]

const REFRESH_INTERVAL = 5000;  // 5 seconds


/**
 * Initialize dashboard.
 * Call on page load.
 */
function initDashboard() {
  drawEquityCurve();
  refreshData();
  setInterval(refreshData, REFRESH_INTERVAL);
  setInterval(checkForClosedTrades, 3000);
}


/**
 * Main refresh cycle.
 * Fetches prices for current chart symbol + all open trades.
 */
async function refreshData() {
  const sym = typeof curSymRaw !== 'undefined' ? curSymRaw : 'BTCUSDT';

  // ── Fetch price for chart symbol (also triggers auto-close on server) ──
  try {
    const data = await fetchPrice(sym);
    if (data) {
      updateSignalPanel(data);
      if (typeof updateChartOverlay === 'function') {
        updateChartOverlay(data.trades || [], data.price, sym);
      }
    }
  } catch (e) { /* silent */ }

  // ── Update current price cells for all open trades ──
  const cache = {};
  const trades = window.OPEN_TRADES || [];

  for (const t of trades) {
    if (!cache[t.symbol]) {
      try {
        const d = await fetchPrice(t.symbol);
        if (d) cache[t.symbol] = d.price;
      } catch (e) { /* silent */ }
    }

    const cell = document.getElementById(`cur-${t.id}`);
    if (cell && cache[t.symbol]) {
      cell.textContent = '$' + fmtPrice(cache[t.symbol]);
    }
  }
}


/**
 * Fetch price data from Django price_api endpoint.
 * Returns { price, trend, trades, status }
 */
async function fetchPrice(symbol) {
  const resp = await fetch(`/trades/price/${symbol}/`);
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.status === 'ok' ? data : null;
}


/**
 * Update signal panel below chart.
 * Shows Buy/Sell signal, live price, TP/SL distances.
 */
function updateSignalPanel(data) {
  const { price, trend, trades = [], symbol } = data;

  // ── Live price ──
  const priceEl = document.getElementById('live-price');
  if (priceEl) priceEl.textContent = '$' + fmtPrice(price);

  // ── Trade count ──
  const countEl = document.getElementById('sym-trade-count');
  if (countEl) countEl.textContent = trades.length;

  // ── Buy/Sell signal ──
  const tagEl  = document.getElementById('sig-tag');
  const descEl = document.getElementById('sig-desc');

  if (tagEl && descEl) {
    if (trend === 'BULLISH') {
      tagEl.textContent = '▲ BUY SIGNAL';
      tagEl.className   = 'tag tag-buy';
      descEl.textContent = 'Short MA > Long MA — upward momentum detected.';
    } else if (trend === 'BEARISH') {
      tagEl.textContent = '▼ SELL SIGNAL';
      tagEl.className   = 'tag tag-sell';
      descEl.textContent = 'Short MA < Long MA — downward momentum detected.';
    } else {
      tagEl.textContent = '→ NEUTRAL';
      tagEl.className   = 'tag tag-neu';
      descEl.textContent = 'Not enough data for signal yet.';
    }
  }

  // ── TP/SL distance badges ──
  const badgeDiv = document.getElementById('tpsl-badges');
  if (badgeDiv) {
    badgeDiv.innerHTML = '';
    trades.forEach(t => {
      const distTP = ((t.tp - price) / price * 100).toFixed(2);
      const distSL = ((price - t.sl) / price * 100).toFixed(2);
      const tpSign = distTP > 0 ? '+' : '';

      badgeDiv.innerHTML += `
        <div class="sig-box">
          <span class="tag tag-tp">TP</span>
          <span style="font-family:var(--mono);color:var(--accent);">$${_fmt(t.tp)}</span>
          <span style="color:var(--muted);font-size:0.75rem;">${tpSign}${distTP}% away</span>
        </div>
        <div class="sig-box">
          <span class="tag tag-sl">SL</span>
          <span style="font-family:var(--mono);color:var(--orange);">$${_fmt(t.sl)}</span>
          <span style="color:var(--muted);font-size:0.75rem;">-${distSL}% away</span>
        </div>`;
    });
  }

  // ── Update signal column in trades table ──
  const openTrades = window.OPEN_TRADES || [];
  openTrades.forEach(t => {
    if (t.symbol !== symbol) return;
    const cell = document.getElementById(`sig-${t.id}`);
    if (!cell) return;

    if (trend === 'BULLISH') {
      cell.innerHTML = '<span style="color:var(--green);font-family:var(--mono);font-size:0.8rem;">▲ BUY</span>';
    } else if (trend === 'BEARISH') {
      cell.innerHTML = '<span style="color:var(--red);font-family:var(--mono);font-size:0.8rem;">▼ SELL</span>';
    } else {
      cell.innerHTML = '<span class="muted" style="font-size:0.78rem;">→ Neutral</span>';
    }
  });
}


/**
 * Called when chart symbol changes (from chart.js).
 * Refreshes signal panel for new symbol.
 */
async function onSymbolChanged(newSymbol) {
  try {
    const data = await fetchPrice(newSymbol);
    if (data) updateSignalPanel(data);
  } catch (e) { /* silent */ }
}


/**
 * Check if any trades were auto-closed on server.
 * If yes — reload page to show updated table.
 */
async function checkForClosedTrades() {
  const trades = window.OPEN_TRADES || [];
  if (!trades.length) return;

  const sym = typeof curSymRaw !== 'undefined' ? curSymRaw : 'BTCUSDT';

  try {
    const data = await fetchPrice(sym);
    if (!data) return;

    const serverCount = (data.trades || []).length;
    const localCount  = trades.filter(t => t.symbol === sym).length;

    if (serverCount < localCount) {
      // A trade was auto-closed — reload page
      location.reload();
    }
  } catch (e) { /* silent */ }
}


/**
 * Draw equity curve on canvas.
 * Shows cumulative PnL over closed trades.
 */
function drawEquityCurve() {
  const canvas = document.getElementById('equity-canvas');
  if (!canvas) return;

  const ctx  = canvas.getContext('2d');
  const pnls = window.CLOSED_PNL || [];

  if (!pnls.length) {
    canvas.width  = canvas.offsetWidth || 300;
    canvas.height = 100;
    ctx.fillStyle = '#64748b';
    ctx.font      = '12px monospace';
    ctx.fillText('No closed trades yet.', 10, 50);
    return;
  }

  // Build cumulative PnL
  const cum = [];
  let sum = 0;
  pnls.forEach(p => { sum += parseFloat(p); cum.push(sum); });

  const W = canvas.offsetWidth || 300;
  const H = 100;
  canvas.width  = W;
  canvas.height = H;

  const mn  = Math.min(0, ...cum);
  const mx  = Math.max(0, ...cum);
  const rng = (mx - mn) || 1;

  const tx = i => (i / ((cum.length - 1) || 1)) * (W - 20) + 10;
  const ty = v => H - 10 - ((v - mn) / rng) * (H - 20);

  // Zero line
  ctx.strokeStyle = '#1e2d45';
  ctx.lineWidth   = 1;
  ctx.beginPath();
  ctx.moveTo(0, ty(0));
  ctx.lineTo(W, ty(0));
  ctx.stroke();

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, sum >= 0 ? 'rgba(0,230,118,0.35)' : 'rgba(255,23,68,0.35)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  ctx.beginPath();
  ctx.moveTo(tx(0), ty(cum[0]));
  cum.forEach((v, i) => { if (i > 0) ctx.lineTo(tx(i), ty(v)); });
  ctx.lineTo(tx(cum.length - 1), H);
  ctx.lineTo(tx(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle = sum >= 0 ? '#00e676' : '#ff1744';
  ctx.lineWidth   = 2;
  ctx.moveTo(tx(0), ty(cum[0]));
  cum.forEach((v, i) => { if (i > 0) ctx.lineTo(tx(i), ty(v)); });
  ctx.stroke();

  // Final label
  ctx.fillStyle = sum >= 0 ? '#00e676' : '#ff1744';
  ctx.font      = 'bold 11px monospace';
  ctx.fillText(
    (sum >= 0 ? '+' : '') + sum.toFixed(2) + '%',
    tx(cum.length - 1) - 50,
    ty(cum[cum.length - 1]) - 6
  );
}


// ── Helpers ──

function fmtPrice(price) {
  if (!price) return '—';
  return price.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  });
}

function _fmt(price) {
  if (!price) return '—';
  if (price >= 1000) return price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  if (price >= 1)    return price.toFixed(4);
  return price.toFixed(6);
}