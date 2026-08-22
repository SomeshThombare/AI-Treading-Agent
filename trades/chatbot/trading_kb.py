"""
trades/chatbot/trading_kb.py
Trading Knowledge Base — answers common questions instantly.
"""

import re
import logging

logger = logging.getLogger(__name__)


KB = {
    'rsi': {
        'keywords': ['rsi', 'relative strength index', 'overbought', 'oversold'],
        'answer': """**RSI (Relative Strength Index)** 📊

A momentum indicator measuring speed of price changes.

📊 **Range:** 0 to 100
• Above 70 → Overbought (sell signal)
• Below 30 → Oversold (buy signal)
• 50 → Neutral

📐 **Formula:**
RSI = 100 - (100 / (1 + RS))
where RS = Average Gain / Average Loss (14 periods)

💡 **How to use:**
• Confirm trend direction
• Spot reversal points
• Watch for divergences (price up, RSI down = warning)

**Used in:** Your project uses RSI(14) as one of 11 LSTM features.""",
    },

    'macd': {
        'keywords': ['macd', 'moving average convergence divergence'],
        'answer': """**MACD (Moving Average Convergence Divergence)** 📈

A trend-following momentum indicator.

📐 **Components:**
• MACD Line = EMA(12) - EMA(26)
• Signal Line = EMA(9) of MACD Line
• Histogram = MACD - Signal

🎯 **Trading Signals:**
• MACD crosses above Signal → BUY signal ✅
• MACD crosses below Signal → SELL signal ❌
• Histogram increasing → Trend strengthening
• Histogram decreasing → Trend weakening

**Used in:** Your LSTM model uses both MACD and MACD Signal as features.""",
    },

    'ema': {
        'keywords': ['ema', 'exponential moving average'],
        'answer': """**EMA (Exponential Moving Average)** 📉

A moving average that gives MORE weight to recent prices.

📐 **Formula:**
EMA = (Price × multiplier) + (Previous EMA × (1 - multiplier))
where multiplier = 2 / (period + 1)

🎯 **Common Periods:**
• EMA-9 → Very short term (scalping)
• EMA-21 → Short term (day trading)
• EMA-50 → Medium term
• EMA-200 → Long term (institutional)

💡 **Trading Rules:**
• Price above EMA → Uptrend (bullish)
• Price below EMA → Downtrend (bearish)
• Short EMA crosses above Long EMA → Golden Cross (BUY)
• Short EMA crosses below Long EMA → Death Cross (SELL)

**Used in:** Your project uses EMA-9 and EMA-21 in LSTM features.""",
    },

    'atr': {
        'keywords': ['atr', 'average true range', 'volatility'],
        'answer': """**ATR (Average True Range)** 📊

Measures market VOLATILITY (how much price moves).

📐 **What is True Range:**
TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
ATR = 14-period average of TR

🎯 **What it tells you:**
• HIGH ATR → High volatility (bigger price swings)
• LOW ATR → Low volatility (price stable)

💡 **Practical Uses:**
• Set Stop Loss = 1.5 × ATR from entry
• Set Take Profit = 2-3 × ATR from entry
• Adjust position size based on volatility

**Used in:** Your project uses ATR(14) for volatility-adjusted predictions.""",
    },

    'bollinger': {
        'keywords': ['bollinger', 'bollinger bands', 'bb'],
        'answer': """**Bollinger Bands** 📊

Three lines showing price volatility around a moving average.

📐 **Components:**
• Middle Band = 20-period SMA
• Upper Band = SMA + (2 × Standard Deviation)
• Lower Band = SMA - (2 × Standard Deviation)

🎯 **Trading Signals:**
• Price touches Upper → Possibly overbought
• Price touches Lower → Possibly oversold
• Bands squeeze tight → Big move coming
• Bands expand wide → High volatility period

💡 **Best with:** Combine with RSI for confirmation""",
    },

    'doji': {
        'keywords': ['doji', 'doji candle', 'doji pattern'],
        'answer': """**Doji Candle** 🕯️

A candle where Open ≈ Close (very small body).

📊 **Looks like:** ━┼━ (cross or plus sign)

🎯 **Meaning:**
• Market INDECISION
• Buyers and sellers are balanced
• Often signals trend REVERSAL

🕯️ **Types:**
• **Standard Doji** → Neutral, wait for confirmation
• **Dragonfly Doji** → Bullish reversal (long lower wick)
• **Gravestone Doji** → Bearish reversal (long upper wick)
• **4-Price Doji** → All 4 prices same (very rare)

💡 **How to trade:**
• Appears at top → Watch for bearish reversal
• Appears at bottom → Watch for bullish reversal
• Confirm with NEXT candle direction""",
    },

    'hammer': {
        'keywords': ['hammer', 'hammer candle'],
        'answer': """**Hammer Candle** 🔨

A bullish reversal pattern at the bottom of a downtrend.

📊 **Looks like:**
• Small body at the top
• LONG lower wick (2-3× body size)
• Little or no upper wick

🎯 **Meaning:**
• Sellers pushed price DOWN
• But buyers stepped in strongly
• Reversal from down to up is likely

💡 **Trading Rule:**
• Wait for NEXT candle to confirm
• Enter long position above hammer high
• Stop loss below hammer low""",
    },

    'engulfing': {
        'keywords': ['engulfing', 'bullish engulfing', 'bearish engulfing'],
        'answer': """**Engulfing Pattern** 🌊

A strong reversal signal using TWO candles.

🟢 **Bullish Engulfing:**
• Day 1: Small red (bearish) candle
• Day 2: BIG green candle that engulfs entire red body
• Signals: Reversal from down to up

🔴 **Bearish Engulfing:**
• Day 1: Small green (bullish) candle
• Day 2: BIG red candle that engulfs entire green body
• Signals: Reversal from up to down

💡 **Best when:**
• Appears after strong trend
• High volume on engulfing candle
• Near support/resistance level""",
    },

    'pinbar': {
        'keywords': ['pin bar', 'pinbar', 'shooting star'],
        'answer': """**Pin Bar (Shooting Star/Hammer)** 📍

A reversal candle with a LONG wick.

📊 **Structure:**
• Small body
• LONG wick (2-3× body)
• Short opposite wick

🎯 **Two types:**
• **Bullish Pin Bar** → Long lower wick
• **Bearish Pin Bar** → Long upper wick

📈 **Trading:**
• At support → bullish pin = BUY signal
• At resistance → bearish pin = SELL signal""",
    },

    'take profit': {
        'keywords': ['take profit', 'tp', 'profit target'],
        'answer': """**Take Profit (TP)** ✅

Pre-set price where you AUTO-EXIT a trade with profit.

🎯 **Why it matters:**
• Locks in gains automatically
• Removes emotion from exit decisions
• Prevents giving back profits

📐 **How to set TP:**
1. **Percentage method:** Entry + (Entry × TP%)
2. **R:R ratio method:** TP = Entry + (2-3 × SL distance)
3. **ATR method:** TP = Entry + (2-3 × ATR value)
4. **Resistance method:** TP just below resistance

💡 **In your project:**
AI suggests TP based on LSTM confidence:
• Higher confidence → wider TP
• Lower confidence → conservative TP""",
    },

    'stop loss': {
        'keywords': ['stop loss', 'sl', 'stop'],
        'answer': """**Stop Loss (SL)** 🛑

Pre-set price where you AUTO-EXIT to LIMIT losses.

🎯 **Why critical:**
• Prevents catastrophic losses
• Protects your capital
• Removes emotional decisions
• Lets you sleep at night!

📐 **How to set SL:**
1. **Percentage method:** Entry - (Entry × SL%)
2. **ATR method:** SL = Entry - (1.5 × ATR)
3. **Support method:** SL just below support

⚠️ **Rules:**
• NEVER trade without a Stop Loss
• Don't move SL further from entry
• Risk only 1-2% of account per trade

💡 **In your project:**
AI suggests SL based on market type:
• Crypto: 1.5% base
• Forex: 0.5% base
• Gold: 0.8% base""",
    },

    'risk reward': {
        'keywords': ['risk reward', 'risk/reward', 'r/r', 'rr ratio'],
        'answer': """**Risk/Reward Ratio (R:R)** ⚖️

The ratio of POTENTIAL PROFIT vs POTENTIAL LOSS.

📐 **Formula:**
R:R = (TP distance) / (SL distance)

📊 **Examples:**
• Entry $100, TP $105, SL $98
  Profit: $5, Loss: $2
  R:R = 5/2 = **2.5:1** ✅ GOOD

• Entry $100, TP $102, SL $98
  R:R = **1:1** ❌ POOR

🎯 **Best Practice:**
• Minimum 2:1 R:R for any trade
• 3:1 or better is excellent
• Even with 40% win rate, 2:1 R:R = profitable!

💡 **Math example:**
2:1 R:R, 40% wins, 100 trades:
• 40 wins × 2 = +80
• 60 losses × 1 = -60
• Net = +20 units profit!

**Your project:** Enforces minimum 2:1 R:R automatically.""",
    },

    'leverage': {
        'keywords': ['leverage', 'margin'],
        'answer': """**Leverage** 💪

Trading with BORROWED money to amplify position size.

📊 **Example with 10x leverage:**
• You have $100
• Trade with 10x = $1,000 position
• Profit/loss on $1,000

🎯 **Common Leverages:**
• Forex: up to 30x (regulated)
• Crypto: 1x to 100x (varies)
• Stocks: 2x to 5x typically

⚠️ **DANGER:**
• 10x leverage = 10% move = 100% account loss
• Liquidation if price moves against you
• Many beginners lose accounts with high leverage

💡 **Recommendation:**
• Start with 1x to 5x maximum
• Never risk more than 1-2% per trade

**Note:** Your paper trading project uses 1x (spot) — no liquidation risk!""",
    },

    'spread': {
        'keywords': ['spread', 'bid ask spread'],
        'answer': """**Spread** 💱

The DIFFERENCE between BUY price (ask) and SELL price (bid).

📊 **Example:**
• BTC Bid (sell): $65,000
• BTC Ask (buy):  $65,005
• Spread = $5 = 0.0077%

🎯 **Why it matters:**
• You buy at ASK (higher)
• You sell at BID (lower)
• Trade opens already in LOSS by spread

💡 **Comparison:**
• Major Forex (EUR/USD): 1-3 pips (tight)
• Crypto BTC: 0.01-0.05% (good)
• Exotic Forex: 20-50 pips (wide!)""",
    },

    'scalping': {
        'keywords': ['scalp', 'scalping'],
        'answer': """**Scalping** ⚡

Strategy aiming for SMALL profits on MANY trades.

📊 **Characteristics:**
• Timeframe: 1-min to 5-min charts
• Trade duration: Seconds to minutes
• Target: 0.1% to 0.5% per trade
• Frequency: 10-50+ trades per day

🎯 **Best for:**
• Highly liquid markets (major forex, BTC)
• Low spread instruments

⚠️ **Challenges:**
• Stressful (constant attention)
• Spread/fees eat into profit
• Requires fast execution""",
    },

    'swing trading': {
        'keywords': ['swing', 'swing trading'],
        'answer': """**Swing Trading** 📊

Holding trades for DAYS to WEEKS to catch larger moves.

📊 **Characteristics:**
• Timeframe: 4-hour or daily charts
• Trade duration: 2 days to 2 weeks
• Target: 3-10% per trade
• Frequency: 2-5 trades per week

🎯 **Why popular:**
• Less stressful than day trading
• Don't need constant monitoring
• Good for working professionals

📈 **Setup:**
1. Identify trend on daily chart
2. Find entry on 4-hour pullback
3. Set TP at next resistance
4. SL below recent support""",
    },

    'trend': {
        'keywords': ['trend', 'uptrend', 'downtrend'],
        'answer': """**Trend** 📈📉

The overall DIRECTION of price movement.

📈 **Uptrend (Bullish):**
• Higher highs (HH)
• Higher lows (HL)
• Strategy: BUY pullbacks

📉 **Downtrend (Bearish):**
• Lower highs (LH)
• Lower lows (LL)
• Strategy: SELL rallies

➡️ **Sideways (Range):**
• Price moves in a range
• No clear direction
• Strategy: BUY support, SELL resistance

💡 **Confirmation:**
• EMA-50 and EMA-200
• Price above both = Strong uptrend
• EMA-50 crosses EMA-200 = Trend change

⚖️ **Golden Rule:**
"The trend is your friend until it ends." """,
    },

    'help': {
        'keywords': ['help', 'what can you do', 'commands'],
        'answer': """**👋 Trading Assistant — How I Can Help**

📚 **I can explain:**
• Technical indicators (RSI, MACD, EMA, ATR, Bollinger)
• Candle patterns (Doji, Hammer, Engulfing, Pin Bar)
• Trading concepts (TP, SL, R/R, leverage, spread)
• Strategies (Scalping, Swing, Trend)

🧮 **I can calculate:**
• Risk/Reward ratio
• Position sizing
• Profit/Loss percentages
• Account risk per trade

🖼️ **I can analyze:**
• Chart screenshots (upload image)
• Candle patterns in your images
• Trade setups visually

💬 **Examples to try:**
• "What is RSI?"
• "Calculate risk: entry 65000, TP 67000, SL 64000"
• "Position size: 5000 USD, 2% risk, BTC 65000, SL 64500"
• "Explain Doji candles"

Or just ASK any trading question!""",
    },
}


def search_kb(query: str):
    """
    Search knowledge base for matching answer.
    Returns dict with 'answer' and 'source' or None.
    """
    if not query:
        return None

    query_lower = query.lower().strip()
    best_match = None
    best_score = 0

    for topic, data in KB.items():
        score = 0
        for keyword in data['keywords']:
            if keyword in query_lower:
                score += len(keyword.split()) * 2
            elif re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
                score += len(keyword.split())

        if score > best_score:
            best_score = score
            best_match = (topic, data)

    if best_score >= 1 and best_match:
        return {
            'answer': best_match[1]['answer'],
            'source': 'kb',
            'topic':  best_match[0],
            'score':  best_score,
        }

    return None


def get_all_topics():
    """Return list of all topics."""
    return list(KB.keys())