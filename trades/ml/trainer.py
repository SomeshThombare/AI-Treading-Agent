"""
trades/ml/trainer.py

Fetches historical price data and trains the LSTM model.

HOW IT WORKS:
  1. Fetch 500+ candles from MT5 (Forex/Gold) or Binance (Crypto)
  2. Calculate technical indicators (RSI, EMA, MACD...)
  3. Create sequences for LSTM input
  4. Split data into train/validation sets
  5. Train LSTM model
  6. Save trained model to saved_models/

USAGE:
  from trades.ml.trainer import train_symbol
  result = train_symbol('BTCUSDT')
  result = train_symbol('EURUSD')
  result = train_symbol('XAUUSD')

  Or via management command:
  python manage.py train_models
  python manage.py train_models --symbol BTCUSDT
"""

import logging
import pandas as pd
import numpy as np

from .features   import calculate_features, normalize_features, create_sequences, get_feature_columns
from .lstm_model import build_model, train_model, save_model

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────

# How many candles to fetch for training
CANDLES_TO_FETCH = 1000

# Lookback window — how many past candles LSTM uses
LOOKBACK = 60

# Train/validation split ratio
TRAIN_RATIO = 0.80   # 80% train, 20% validation

# Symbols to train (grouped by data source)
CRYPTO_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT',
    'SOLUSDT', 'XRPUSDT',
]

MT5_SYMBOLS = [
    'EURUSD', 'GBPUSD', 'USDJPY',
    'XAUUSD',   # Gold
    'XAGUSD',   # Silver
]


# ─────────────────────────────────────────────────────
#  Main Training Function
# ─────────────────────────────────────────────────────

def train_symbol(symbol: str, candles: int = CANDLES_TO_FETCH) -> dict:
    """
    Full training pipeline for one symbol.

    Steps:
      1. Fetch historical data
      2. Calculate features
      3. Normalize data
      4. Create sequences
      5. Train LSTM
      6. Save model

    Args:
        symbol:  e.g. 'BTCUSDT', 'EURUSD', 'XAUUSD'
        candles: number of historical candles to use

    Returns:
        dict with training results:
        {
          'symbol':   'BTCUSDT',
          'success':  True,
          'accuracy': 0.68,
          'samples':  940,
          'error':    None
        }
    """
    symbol = symbol.upper()
    logger.info(f"{'='*50}")
    logger.info(f"Training model for: {symbol}")
    logger.info(f"{'='*50}")

    result = {
        'symbol':   symbol,
        'success':  False,
        'accuracy': 0.0,
        'samples':  0,
        'error':    None,
    }

    try:
        # ── Step 1: Fetch historical data ──
        logger.info(f"[{symbol}] Step 1: Fetching {candles} candles...")
        df = fetch_historical_data(symbol, candles)

        if df is None or len(df) < 200:
            raise ValueError(
                f"Not enough data for {symbol}. "
                f"Got {len(df) if df is not None else 0} candles, need 200+"
            )

        logger.info(f"[{symbol}] Fetched {len(df)} candles successfully")

        # ── Step 2: Calculate technical indicators ──
        logger.info(f"[{symbol}] Step 2: Calculating features...")
        df = calculate_features(df)
        logger.info(f"[{symbol}] Features calculated. Shape: {df.shape}")

        # ── Step 3: Normalize data ──
        logger.info(f"[{symbol}] Step 3: Normalizing data...")
        df_norm, scaler_dict = normalize_features(df)

        # ── Step 4: Create LSTM sequences ──
        logger.info(f"[{symbol}] Step 4: Creating sequences (lookback={LOOKBACK})...")
        X, y = create_sequences(df_norm, lookback=LOOKBACK)

        if len(X) < 100:
            raise ValueError(f"Not enough sequences: {len(X)}, need 100+")

        logger.info(f"[{symbol}] Sequences: X={X.shape}, y={y.shape}")
        logger.info(f"[{symbol}] UP labels: {y.sum()} ({y.mean():.1%})")

        result['samples'] = len(X)

        # ── Step 5: Split into train/validation ──
        logger.info(f"[{symbol}] Step 5: Splitting train/validation...")
        split     = int(len(X) * TRAIN_RATIO)
        X_train   = X[:split]
        y_train   = y[:split]
        X_val     = X[split:]
        y_val     = y[split:]

        logger.info(f"[{symbol}] Train: {len(X_train)}, Val: {len(X_val)}")

        # ── Step 6: Build LSTM model ──
        logger.info(f"[{symbol}] Step 6: Building LSTM model...")
        input_shape = (X_train.shape[1], X_train.shape[2])
        model       = build_model(input_shape)

        # ── Step 7: Train model ──
        logger.info(f"[{symbol}] Step 7: Training LSTM model...")
        model, history = train_model(
            model, X_train, y_train, X_val, y_val,
            epochs=100
        )

        # Get best validation accuracy
        best_accuracy = max(history.history['val_accuracy'])
        result['accuracy'] = round(best_accuracy, 4)

        logger.info(f"[{symbol}] Best accuracy: {best_accuracy:.2%}")

        # ── Step 8: Save model ──
        logger.info(f"[{symbol}] Step 8: Saving model...")
        save_model(model, symbol, scaler_dict)

        result['success'] = True
        logger.info(f"[{symbol}] ✅ Training complete! Accuracy: {best_accuracy:.2%}")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"[{symbol}] ❌ Training failed: {e}")

    return result


def train_all_symbols() -> list:
    """
    Train models for ALL configured symbols.

    Returns:
        list of result dicts from train_symbol()
    """
    all_symbols = CRYPTO_SYMBOLS + MT5_SYMBOLS
    results     = []

    logger.info(f"Training {len(all_symbols)} models...")

    for symbol in all_symbols:
        result = train_symbol(symbol)
        results.append(result)

        if result['success']:
            logger.info(
                f"✅ {symbol}: accuracy={result['accuracy']:.2%}, "
                f"samples={result['samples']}"
            )
        else:
            logger.error(f"❌ {symbol}: {result['error']}")

    # Summary
    success_count = sum(1 for r in results if r['success'])
    logger.info(f"\nTraining summary: {success_count}/{len(all_symbols)} successful")

    return results


# ─────────────────────────────────────────────────────
#  Data Fetching — MT5 + Binance
# ─────────────────────────────────────────────────────

def fetch_historical_data(symbol: str, candles: int = 500) -> pd.DataFrame | None:
    """
    Fetch historical OHLCV candle data for a symbol.

    Automatically uses correct source:
      Crypto  → Binance API
      Forex   → MT5 terminal
      Gold    → MT5 terminal

    Args:
        symbol:  e.g. 'BTCUSDT', 'EURUSD', 'XAUUSD'
        candles: number of candles to fetch

    Returns:
        DataFrame with columns: open, high, low, close, volume
        Or None if fetching fails
    """
    symbol = symbol.upper()

    # Determine data source from symbol
    from trades.price_service import BINANCE_SYMBOLS, MT5_SYMBOLS

    if symbol in BINANCE_SYMBOLS:
        return _fetch_binance_data(symbol, candles)
    elif symbol in MT5_SYMBOLS:
        return _fetch_mt5_data(symbol, candles)
    else:
        # Try Binance first then MT5
        df = _fetch_binance_data(symbol, candles)
        if df is not None:
            return df
        return _fetch_mt5_data(symbol, candles)


def _fetch_binance_data(symbol: str, candles: int = 500) -> pd.DataFrame | None:
    """
    Fetch historical candle data from Binance API.

    URL: https://api.binance.com/api/v3/klines
    Returns: OHLCV data as DataFrame
    """
    import requests

    url = "https://api.binance.com/api/v3/klines"

    params = {
        'symbol':   symbol,
        'interval': '1h',      # 1 hour candles
        'limit':    min(candles, 1000),  # Binance max is 1000
    }

    try:
        logger.info(f"[BINANCE] Fetching {candles} candles for {symbol}...")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            logger.error(f"[BINANCE] Error {response.status_code}: {response.text[:100]}")
            return None

        raw    = response.json()
        df     = pd.DataFrame(raw, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        # Keep only OHLCV columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()

        # Convert types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df.set_index('timestamp', inplace=True)
        df.dropna(inplace=True)

        logger.info(f"[BINANCE] Fetched {len(df)} candles for {symbol}")
        return df

    except Exception as e:
        logger.error(f"[BINANCE] Error fetching data for {symbol}: {e}")
        return None


def _fetch_mt5_data(symbol: str, candles: int = 500) -> pd.DataFrame | None:
    """
    Fetch historical candle data from MT5 terminal.

    Requires MT5 terminal to be open and logged in.
    Returns: OHLCV data as DataFrame
    """
    try:
        import MetaTrader5 as mt5
        from datetime import datetime

        logger.info(f"[MT5] Fetching {candles} candles for {symbol}...")

        # Connect to MT5
        if not mt5.initialize():
            logger.error(f"[MT5] Cannot connect: {mt5.last_error()}")
            return None

        # Fetch candles (TIMEFRAME_H1 = 1 hour candles)
        rates = mt5.copy_rates_from_pos(
            symbol,
            mt5.TIMEFRAME_H1,
            0,         # start from most recent
            candles    # number of candles
        )

        mt5.shutdown()

        if rates is None or len(rates) == 0:
            logger.error(f"[MT5] No data returned for {symbol}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Rename columns to match standard format
        df.rename(columns={
            'open':       'open',
            'high':       'high',
            'low':        'low',
            'close':      'close',
            'tick_volume':'volume',
        }, inplace=True)

        df = df[['open', 'high', 'low', 'close', 'volume']].copy()
        df.dropna(inplace=True)

        logger.info(f"[MT5] Fetched {len(df)} candles for {symbol}")
        return df

    except ImportError:
        logger.error("[MT5] MetaTrader5 not installed")
        return None

    except Exception as e:
        logger.error(f"[MT5] Error fetching data for {symbol}: {e}")
        return None