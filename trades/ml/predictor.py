"""
trades/ml/predictor.py

Loads trained LSTM model and predicts TP/SL for a symbol.

HOW IT WORKS:
  1. Load trained model from saved_models/
  2. Fetch latest 60 candles (LOOKBACK window)
  3. Calculate technical indicators
  4. Normalize data
  5. Run LSTM prediction
  6. Convert prediction to TP/SL percentages
  7. Return suggestion to the UI

USAGE:
  from trades.ml.predictor import get_ai_suggestion
  result = get_ai_suggestion('BTCUSDT')
  result = get_ai_suggestion('EURUSD')
  result = get_ai_suggestion('XAUUSD')

  Returns:
  {
    'symbol':      'BTCUSDT',
    'direction':   'UP',
    'confidence':  73.5,
    'tp_percent':  4.5,
    'sl_percent':  2.0,
    'model_ready': True,
    'message':     'AI suggests TP=4.5%, SL=2.0% (73.5% confident)'
  }
"""

import logging
import numpy as np
import pandas as pd
from .features import get_feature_columns

from .lstm_model import (
    load_model, predict, model_exists,
    get_tp_sl_from_prediction
)
from .features  import (
    calculate_features, normalize_features, get_feature_columns
)
from .trainer   import fetch_historical_data

logger = logging.getLogger(__name__)

# Number of past candles used for prediction
LOOKBACK = 60
BUFFER   = 15   # small extra for indicators

def get_ai_suggestion(symbol: str) -> dict:
    """
    Main function — get AI suggested TP/SL for a symbol.

    This is called when user opens "Create Trade" page.
    Returns pre-filled TP/SL values based on LSTM prediction.

    Args:
        symbol: e.g. 'BTCUSDT', 'EURUSD', 'XAUUSD'

    Returns:
        dict with all prediction details
    """
    symbol = symbol.upper()
    logger.info(f"Getting AI suggestion for {symbol}...")

    # Default response if model not ready
    default = _default_suggestion(symbol)

    # ── Check if model exists ──
    if not model_exists(symbol):
        logger.warning(f"No trained model for {symbol}")
        default['message'] = (
            f"No AI model for {symbol} yet. "
            f"Run: python manage.py train_models --symbol {symbol}"
        )
        default['model_ready'] = False
        return default

    try:
        # ── Step 1: Load trained model ──
        logger.info(f"[{symbol}] Loading model...")
        model, scaler_dict = load_model(symbol)

        if model is None:
            logger.error(f"[{symbol}] Failed to load model")
            default['message'] = f"Error loading model for {symbol}"
            return default

        # ── Step 2: Fetch latest candles ──
        logger.info(f"[{symbol}] Fetching latest {LOOKBACK + 50} candles...")
        df = fetch_historical_data(symbol, candles=LOOKBACK + 50)

        if df is None or len(df) < LOOKBACK:
            logger.error(f"[{symbol}] Not enough recent data")
            default['message'] = "Not enough market data. Try again."
            return default

       

        # ── Step 3: Calculate features ──
        logger.info(f"[{symbol}] Calculating features...")
        df = calculate_features(df)

        if len(df) < LOOKBACK:
            logger.error(f"[{symbol}] After feature calc, not enough rows")
            default['message'] = "Feature calculation failed. Try again."
            return default

        # ── Step 4: Normalize using same scaler as training ──
        logger.info(f"[{symbol}] Normalizing data...")
        df_norm = _apply_scaler(df, scaler_dict)

        # ── Step 5: Prepare input sequence ──
        feature_cols = get_feature_columns()
        available    = [c for c in feature_cols if c in df_norm.columns]

        # Take last LOOKBACK rows as input
        sequence = df_norm[available].values[-LOOKBACK:]

        if len(sequence) < LOOKBACK:
            logger.error(f"[{symbol}] Sequence too short: {len(sequence)}")
            default['message'] = "Insufficient data for prediction."
            return default

        # Reshape for LSTM: (1, LOOKBACK, features)
        X = np.array([sequence])

        # ── Step 6: Run LSTM prediction ──
        logger.info(f"[{symbol}] Running LSTM prediction...")
        direction, confidence = predict(model, X)

        logger.info(f"[{symbol}] Prediction: {direction} ({confidence:.2%})")

        # ── Step 7: Get symbol market type ──
        from trades.price_service import get_symbol_type
        symbol_type = get_symbol_type(symbol)

        # ── Step 8: Convert to TP/SL values ──
        tp_sl = get_tp_sl_from_prediction(
            direction   = direction,
            confidence  = confidence,
            symbol_type = symbol_type
        )

        # ── Step 9: Build final response ──
        confidence_pct = round(confidence * 100, 1)

        message = (
            f"AI predicts price will go {direction} "
            f"with {confidence_pct}% confidence. "
            f"Suggested TP={tp_sl['tp_percent']}%, "
            f"SL={tp_sl['sl_percent']}%"
        )

        return {
            'symbol':      symbol,
            'direction':   direction,
            'confidence':  confidence_pct,
            'tp_percent':  tp_sl['tp_percent'],
            'sl_percent':  tp_sl['sl_percent'],
            'model_ready': True,
            'message':     message,
            'symbol_type': symbol_type,
        }

    except Exception as e:
        logger.error(f"[{symbol}] Prediction error: {e}")
        default['message'] = f"Prediction error: {str(e)}"
        return default


def _apply_scaler(df: pd.DataFrame, scaler_dict: dict) -> pd.DataFrame:
    """
    Apply saved normalization values to new data.

    Uses the same min/max values from training so
    new data is normalized the same way as training data.
    """
    df_norm = df.copy()

    if scaler_dict is None:
        # No scaler — use simple normalization
        feature_cols = get_feature_columns()
        for col in feature_cols:
            if col not in df_norm.columns:
                continue
            col_min   = df_norm[col].min()
            col_max   = df_norm[col].max()
            col_range = col_max - col_min
            if col_range != 0:
                df_norm[col] = (df_norm[col] - col_min) / col_range
            else:
                df_norm[col] = 0.0
        return df_norm

    # Apply saved scaler
    for col, values in scaler_dict.items():
        if col not in df_norm.columns:
            continue
        col_min   = values['min']
        col_max   = values['max']
        col_range = col_max - col_min
        if col_range != 0:
            df_norm[col] = (df_norm[col] - col_min) / col_range
        else:
            df_norm[col] = 0.0

    return df_norm


def _default_suggestion(symbol: str) -> dict:
    """
    Default suggestion when model is not ready or fails.
    Returns conservative TP/SL values.
    """
    from trades.price_service import get_symbol_type
    symbol_type = get_symbol_type(symbol)

    # Conservative defaults per market type
    defaults = {
        'CRYPTO':    {'tp': 3.0, 'sl': 1.5},
        'FOREX':     {'tp': 1.0, 'sl': 0.5},
        'COMMODITY': {'tp': 1.5, 'sl': 0.8},
        'UNKNOWN':   {'tp': 2.0, 'sl': 1.0},
    }

    vals = defaults.get(symbol_type, defaults['UNKNOWN'])

    return {
        'symbol':      symbol,
        'direction':   'NEUTRAL',
        'confidence':  0.0,
        'tp_percent':  vals['tp'],
        'sl_percent':  vals['sl'],
        'model_ready': False,
        'message':     'Using default values — AI model not trained yet.',
        'symbol_type': symbol_type,
    }


def get_model_status(symbol: str) -> dict:
    """
    Check if a model exists and return its status.

    Used by dashboard to show which symbols have AI support.
    """
    symbol = symbol.upper()
    exists = model_exists(symbol)

    return {
        'symbol':    symbol,
        'trained':   exists,
        'status':    'Ready ✅' if exists else 'Not trained ⚠️',
        'message':   (
            f"Model ready for {symbol}"
            if exists else
            f"Run: python manage.py train_models --symbol {symbol}"
        ),
    }