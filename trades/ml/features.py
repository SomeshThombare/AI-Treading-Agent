"""
trades/ml/features.py

Calculates technical indicators used as LSTM model input features.

Indicators calculated (18 features):
  - RSI        → overbought/oversold signal
  - EMA9/21/50 → short/medium/long term trend
  - MACD + Signal + Histogram → momentum signal
  - ATR        → volatility measure
  - Bollinger Bands (upper, lower, width, %B) → mean reversion
  - Stochastic %K and %D → momentum/reversal signal
  - OBV        → volume trend / accumulation
  - Price change % → momentum
  - Volume change % → buying/selling pressure
  - EMA ratio  → trend strength
  - Price vs EMA21 ratio → bullish/bearish position

USAGE:
  from trades.ml.features import calculate_features
  df = calculate_features(price_dataframe)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators from OHLCV price data.

    Args:
        df: DataFrame with columns: open, high, low, close, volume

    Returns:
        DataFrame with all indicator columns added.
    """
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in df.columns:
            logger.warning(f"Missing column: {col} — using zeros")
            df[col] = 0.0

    # ── RSI (14 period) ──────────────────────────────────────────
    df['rsi'] = _calculate_rsi(df['close'], period=14)

    # ── EMAs ─────────────────────────────────────────────────────
    df['ema9']  = df['close'].ewm(span=9,  adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

    # ── MACD + Signal + Histogram ─────────────────────────────────
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd']         = ema12 - ema26
    df['macd_signal']  = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist']    = df['macd'] - df['macd_signal']

    # ── ATR (Average True Range) ──────────────────────────────────
    df['atr'] = _calculate_atr(df, period=14)

    # ── Bollinger Bands (20 period, 2 std) ────────────────────────
    bb_mid          = df['close'].rolling(window=20).mean()
    bb_std          = df['close'].rolling(window=20).std()
    df['bb_upper']  = bb_mid + (2 * bb_std)
    df['bb_lower']  = bb_mid - (2 * bb_std)
    df['bb_width']  = (df['bb_upper'] - df['bb_lower']) / bb_mid   # volatility squeeze signal
    df['bb_pct']    = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-9)  # 0=at lower, 1=at upper

    # ── Stochastic Oscillator %K and %D ──────────────────────────
    low14  = df['low'].rolling(window=14).min()
    high14 = df['high'].rolling(window=14).max()
    df['stoch_k'] = 100 * (df['close'] - low14) / (high14 - low14 + 1e-9)
    df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()

    # ── OBV (On-Balance Volume) ───────────────────────────────────
    df['obv'] = _calculate_obv(df)

    # ── Price and Volume momentum ─────────────────────────────────
    df['price_change']  = df['close'].pct_change() * 100
    df['volume_change'] = df['volume'].pct_change() * 100

    # ── Trend strength ratios ─────────────────────────────────────
    df['ema_ratio']       = df['ema9'] / (df['ema21'] + 1e-9)   # >1 = short > long = bullish
    df['price_ema_ratio'] = df['close'] / (df['ema21'] + 1e-9)  # >1 = price above MA = bullish
    df['ema_slope']       = df['ema21'].diff(3) / (df['ema21'].shift(3) + 1e-9)  # EMA21 slope

    # ── Candle body / wick features ───────────────────────────────
    df['candle_body']    = abs(df['close'] - df['open']) / (df['close'] + 1e-9)  # body size %
    df['upper_wick']     = (df['high'] - df[['close', 'open']].max(axis=1)) / (df['close'] + 1e-9)
    df['lower_wick']     = (df[['close', 'open']].min(axis=1) - df['low'])  / (df['close'] + 1e-9)

    # Drop rows with NaN (first few rows from rolling windows)
    df.dropna(inplace=True)

    logger.debug(f"Features calculated. Shape: {df.shape}")
    return df


def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta    = prices.diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    return 100 - (100 / (1 + rs))


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - prev_close),
        abs(df['low']  - prev_close),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _calculate_obv(df: pd.DataFrame) -> pd.Series:
    """
    On-Balance Volume: running total of volume,
    added when price rises, subtracted when price falls.
    Tracks whether volume is flowing into or out of an asset.
    """
    direction = np.sign(df['close'].diff()).fillna(0)
    obv       = (direction * df['volume']).cumsum()
    # Normalize OBV to percentage change to keep scale comparable
    obv_pct   = obv.pct_change() * 100
    return obv_pct


def get_feature_columns() -> list:
    """
    Returns the ordered list of feature column names used by the LSTM model.
    Order must match exactly between training and prediction.
    """
    return [
        # Price & trend
        'close',
        'ema_ratio',
        'price_ema_ratio',
        'ema_slope',

        # Momentum
        'rsi',
        'macd',
        'macd_signal',
        'macd_hist',
        'stoch_k',
        'stoch_d',

        # Volatility
        'atr',
        'bb_width',
        'bb_pct',

        # Volume
        'volume_change',
        'obv',

        # Price action
        'price_change',
        'candle_body',
        'upper_wick',
        'lower_wick',
    ]


def normalize_features(df: pd.DataFrame) -> tuple:
    """
    Normalize all features to 0-1 range for LSTM input.
    Returns (normalized_df, scaler_dict) where scaler_dict
    stores min/max values needed to reverse normalization.
    """
    feature_cols = get_feature_columns()
    df_norm      = df.copy()
    scaler_dict  = {}

    for col in feature_cols:
        if col not in df_norm.columns:
            continue

        col_min   = df_norm[col].min()
        col_max   = df_norm[col].max()
        col_range = col_max - col_min

        if col_range == 0:
            df_norm[col] = 0.0
        else:
            df_norm[col] = (df_norm[col] - col_min) / col_range

        scaler_dict[col] = {'min': col_min, 'max': col_max}

    return df_norm, scaler_dict


def create_sequences(df: pd.DataFrame, lookback: int = 100) -> tuple:
    """
    Create input sequences for LSTM model.

    lookback=100 means: use last 100 candles to predict next direction.
    Increased from 60 to capture more market context.

    Returns:
        tuple: (X, y)
          X shape: (samples, lookback, features)
          y shape: (samples,)  → 1=UP, 0=DOWN

    Label filtering: only label a candle UP/DOWN if the
    move is larger than a small threshold (0.05%), reducing
    noise from flat/sideways candles.
    """
    feature_cols   = get_feature_columns()
    available_cols = [c for c in feature_cols if c in df.columns]
    data           = df[available_cols].values

    X, y = [], []
    threshold = 0.0005  # 0.05% minimum move to count as signal

    for i in range(lookback, len(data) - 1):
        X.append(data[i - lookback:i])

        current_close = df['close'].iloc[i]
        next_close    = df['close'].iloc[i + 1]
        change        = (next_close - current_close) / (current_close + 1e-9)

        if change > threshold:
            y.append(1)   # UP
        elif change < -threshold:
            y.append(0)   # DOWN
        else:
            y.append(1 if next_close >= current_close else 0)  # small move: use direction

    return np.array(X), np.array(y)