/**
 * static/js/create_trade.js
 *
 * Create Trade page logic:
 *   - Fetches AI suggested TP/SL from server
 *   - Pre-fills form with ML prediction
 *   - Shows confidence percentage and direction
 *   - Live price preview as user types
 *   - Market type indicator (Crypto/Forex/Gold)
 */


// ── DOM Elements ──
let symbolSelect = null;
let tpInput      = null;
let slInput      = null;

// Current live price
let currentPrice = null;

// AI suggestion data
let aiSuggestion = null;


/**
 * Initialize create trade page.
 * Call on page load.
 */
function initCreateTrade() {
  symbolSelect = document.getElementById('id_symbol');
  tpInput      = document.getElementById('id_tp_percent');
  slInput      = document.getElementById('id_sl_percent');

  if (!symbolSelect) return;

  // Event listeners
  symbolSelect.addEventListener('change', onSymbolChange);
  tpInput.addEventListener('input', updatePreview);
  slInput.addEventListener('input', updatePreview);

  // Load initial symbol data
  onSymbolChange();
}


/**
 * Called when user changes the symbol dropdown.
 * Fetches live price + AI suggestion for new symbol.
 */
async function onSymbolChange() {
  const symbol = symbolSelect.value;
  if (!symbol) return;

  // Show market type badge
  updateMarketBadge(symbol);

  // Show loading state
  showAiLoading();

  // Fetch both in parallel
  await Promise.all([
    fetchLivePrice(symbol),
    fetchAiSuggestion(symbol),
  ]);
}


/**
 * Fetch live price from price_api endpoint.
 */
async function fetchLivePrice(symbol) {
  try {
    const resp = await fetch(`/trades/price/${symbol}/`);
    const data = await resp.json();

    if (data.status === 'ok') {
      currentPrice = data.price;
      updatePreview();

      // Show market trend signal
      showTrendSignal(data.trend);
    }
  } catch (e) {
    console.warn('Price fetch failed:', e);
  }
}


/**
 * Fetch AI suggested TP/SL from server.
 * Calls /trades/ai-suggest/<symbol>/ endpoint.
 */
async function fetchAiSuggestion(symbol) {
  try {
    const resp = await fetch(`/trades/ai-suggest/${symbol}/`);
    const data = await resp.json();

    aiSuggestion = data;
    displayAiSuggestion(data);

  } catch (e) {
    console.warn('AI suggestion fetch failed:', e);
    showAiError('AI suggestion unavailable. Enter TP/SL manually.');
  }
}


/**
 * Display AI suggestion box with direction, confidence, values.
 */
function displayAiSuggestion(data) {
  const box = document.getElementById('ai-suggestion-box');
  if (!box) return;

  if (!data.model_ready) {
    showAiError(data.message || 'Model not trained yet.');
    return;
  }

  box.classList.add('loaded');

  // Direction indicator
  const dirEl = document.getElementById('ai-direction');
  if (dirEl) {
    if (data.direction === 'UP') {
      dirEl.innerHTML = '<span class="direction-up">▲ Bullish</span> — AI predicts price will rise';
    } else if (data.direction === 'DOWN') {
      dirEl.innerHTML = '<span class="direction-down">▼ Bearish</span> — AI predicts price will fall';
    } else {
      dirEl.innerHTML = '<span class="direction-neut">→ Neutral</span> — No clear signal';
    }
  }

  // Confidence display
  const confEl = document.getElementById('ai-confidence');
  if (confEl) {
    confEl.textContent = `${data.confidence}% confident`;
    confEl.className   = 'ai-confidence ' + getConfidenceClass(data.confidence);
  }

  // TP value
  const tpEl = document.getElementById('ai-tp-value');
  if (tpEl) tpEl.textContent = data.tp_percent + '%';

  // SL value
  const slEl = document.getElementById('ai-sl-value');
  if (slEl) slEl.textContent = data.sl_percent + '%';

  // Show the suggestion box
  box.style.display = 'block';

  // Show apply button
  const applyBtn = document.getElementById('btn-apply-ai');
  if (applyBtn) applyBtn.style.display = 'block';
}


/**
 * Apply AI suggestion to the form inputs.
 * Called when user clicks "Apply AI Suggestion" button.
 */
function applyAiSuggestion() {
  if (!aiSuggestion || !aiSuggestion.model_ready) return;

  tpInput.value = aiSuggestion.tp_percent;
  slInput.value = aiSuggestion.sl_percent;

  // Visual feedback
  tpInput.style.borderColor = 'var(--accent)';
  slInput.style.borderColor = 'var(--accent)';

  setTimeout(() => {
    tpInput.style.borderColor = '';
    slInput.style.borderColor = '';
  }, 1500);

  updatePreview();
}


/**
 * Update live trade preview (Entry, TP target, SL target prices).
 */
function updatePreview() {
  if (!currentPrice) return;

  const tp = parseFloat(tpInput?.value) || 0;
  const sl = parseFloat(slInput?.value) || 0;

  const entryEl = document.getElementById('prev-entry');
  const tpEl    = document.getElementById('prev-tp');
  const slEl    = document.getElementById('prev-sl');
  const rrEl    = document.getElementById('prev-rr');

  if (entryEl) {
    entryEl.textContent = '$' + fmtPrice(currentPrice);
  }

  if (tpEl) {
    tpEl.textContent = tp
      ? '$' + fmtPrice(currentPrice * (1 + tp / 100))
      : '—';
  }

  if (slEl) {
    slEl.textContent = sl
      ? '$' + fmtPrice(currentPrice * (1 - sl / 100))
      : '—';
  }

  // Risk/Reward ratio
  if (rrEl && tp && sl) {
    const rr = (tp / sl).toFixed(1);
    rrEl.textContent = `${rr}:1`;
    rrEl.style.color = rr >= 2 ? 'var(--green)' : rr >= 1.5 ? 'var(--yellow)' : 'var(--red)';
  }
}


/**
 * Show trend signal in UI.
 */
function showTrendSignal(trend) {
  const el = document.getElementById('symbol-trend');
  if (!el) return;

  if (trend === 'BULLISH') {
    el.innerHTML = '<span class="trend-bull">▲ Bullish trend</span>';
  } else if (trend === 'BEARISH') {
    el.innerHTML = '<span class="trend-bear">▼ Bearish trend</span>';
  } else {
    el.innerHTML = '<span class="trend-neut">→ Neutral</span>';
  }
}


/**
 * Update market type badge (Crypto / Forex / Gold).
 */
function updateMarketBadge(symbol) {
  const el = document.getElementById('market-type-badge');
  if (!el) return;

  const cryptoSyms = [
    'BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT',
    'XRPUSDT','DOGEUSDT','ADAUSDT',
  ];
  const goldSyms = ['XAUUSD','XAGUSD','XTIUSD'];

  if (cryptoSyms.includes(symbol)) {
    el.textContent = '₿ Crypto';
    el.className   = 'market-type-badge market-crypto';
  } else if (goldSyms.includes(symbol)) {
    el.textContent = '🥇 Commodity';
    el.className   = 'market-type-badge market-commodity';
  } else {
    el.textContent = '💱 Forex';
    el.className   = 'market-type-badge market-forex';
  }
}


/**
 * Show AI loading state.
 */
function showAiLoading() {
  const box = document.getElementById('ai-suggestion-box');
  if (!box) return;

  box.classList.remove('loaded');
  box.style.display = 'block';
  box.innerHTML = `
    <div class="ai-loading">
      <div class="spinner"></div>
      <span>Loading AI suggestion for ${symbolSelect.value}...</span>
    </div>
  `;
}


/**
 * Show AI error message.
 */
function showAiError(message) {
  const box = document.getElementById('ai-suggestion-box');
  if (!box) return;

  box.style.display = 'block';
  box.innerHTML = `
    <div style="color:var(--muted); font-size:0.82rem;">
      🤖 ${message}
    </div>
  `;
}


/**
 * Get confidence CSS class based on value.
 */
function getConfidenceClass(confidence) {
  if (confidence >= 70) return 'high';
  if (confidence >= 55) return 'medium';
  return 'low';
}


/**
 * Format price for display.
 */
function fmtPrice(price) {
  if (!price) return '—';
  if (price >= 1000) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (price >= 1)  return price.toFixed(4);
  return price.toFixed(6);
}