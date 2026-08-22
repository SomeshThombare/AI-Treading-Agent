"""
trades/ml/lstm_model.py

LSTM Neural Network for crypto/forex price direction prediction.

WHAT IS LSTM?
  LSTM = Long Short-Term Memory
  It is a type of neural network designed for sequence data.
  Perfect for time series like price data because it remembers
  patterns from past candles to predict future direction.

MODEL ARCHITECTURE:
  Input:   60 candles × 11 features = (60, 11) shape
  Layer 1: LSTM(128 units) → learns long term patterns
  Layer 2: Dropout(0.3)    → prevents overfitting
  Layer 3: LSTM(64 units)  → learns short term patterns
  Layer 4: Dropout(0.2)    → prevents overfitting
  Layer 5: Dense(32)       → combines learned patterns
  Layer 6: Dense(1)        → outputs probability (0 to 1)

  Output:  probability > 0.5 = price goes UP
           probability < 0.5 = price goes DOWN

USAGE:
  from trades.ml.lstm_model import build_model, save_model, load_model
  model = build_model(input_shape=(60, 11))
  model = load_model('BTCUSDT')
"""

import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Path where trained models are saved
MODELS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'saved_models'
)

# Create saved_models folder if it doesn't exist
os.makedirs(MODELS_DIR, exist_ok=True)


def build_model(input_shape: tuple):
    """
    Build LSTM model architecture.

    Args:
        input_shape: tuple (lookback, num_features)
                     e.g. (60, 11) = 60 candles, 11 features

    Returns:
        Compiled Keras model ready for training
    """
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import (
            LSTM, Dense, Dropout, BatchNormalization
        )
        from tensorflow.keras.optimizers import Adam
        from tensorflow.keras.callbacks import EarlyStopping

        logger.info(f"Building LSTM model with input shape: {input_shape}")

        model = Sequential([

            # ── Layer 1: First LSTM ──
            # return_sequences=True means pass output to next LSTM layer
            LSTM(
                units           = 128,
                return_sequences= True,
                input_shape     = input_shape,
                name            = 'lstm_1'
            ),

            # Normalize activations for stable training
            BatchNormalization(name='bn_1'),

            # ── Layer 2: Dropout (prevents overfitting) ──
            # Randomly turns off 30% of neurons during training
            # Forces model to learn robust patterns
            Dropout(0.3, name='dropout_1'),

            # ── Layer 3: Second LSTM ──
            # return_sequences=False = final LSTM layer
            LSTM(
                units           = 64,
                return_sequences= False,
                name            = 'lstm_2'
            ),

            # Normalize again
            BatchNormalization(name='bn_2'),

            # ── Layer 4: Dropout ──
            Dropout(0.2, name='dropout_2'),

            # ── Layer 5: Dense layer (combines learned patterns) ──
            Dense(32, activation='relu', name='dense_1'),

            # ── Layer 6: Dropout ──
            Dropout(0.1, name='dropout_3'),

            # ── Layer 7: Output layer ──
            # sigmoid activation → output between 0 and 1
            # > 0.5 = UP prediction
            # < 0.5 = DOWN prediction
            Dense(1, activation='sigmoid', name='output'),
        ])

        # Compile model
        # Adam optimizer with small learning rate for stable training
        # binary_crossentropy loss for UP/DOWN classification
        model.compile(
            optimizer = Adam(learning_rate=0.001),
            loss      = 'binary_crossentropy',
            metrics   = ['accuracy']
        )

        logger.info(f"Model built successfully")
        logger.info(f"Total parameters: {model.count_params():,}")

        return model

    except ImportError:
        logger.error("TensorFlow not installed. Run: pip install tensorflow")
        raise


def train_model(model, X_train, y_train, X_val, y_val, epochs: int = 50):
    """
    Train the LSTM model on historical price data.

    Args:
        model:    compiled Keras model from build_model()
        X_train:  training sequences shape (samples, 60, 11)
        y_train:  training labels (1=UP, 0=DOWN)
        X_val:    validation sequences
        y_val:    validation labels
        epochs:   max training epochs (early stopping may stop earlier)

    Returns:
        Trained model + training history
    """
    try:
        from tensorflow.keras.callbacks import (
            EarlyStopping, ReduceLROnPlateau
        )

        logger.info(f"Training model on {len(X_train)} samples...")
        logger.info(f"Validation samples: {len(X_val)}")

        callbacks = [

            # Stop training early if validation accuracy stops improving
            # patience=10 means stop after 10 epochs without improvement
            EarlyStopping(
                monitor  = 'val_accuracy',
                patience = 10,
                restore_best_weights = True,
                verbose  = 1
            ),

            # Reduce learning rate when stuck
            # Helps model find better solution
            ReduceLROnPlateau(
                monitor  = 'val_loss',
                factor   = 0.5,
                patience = 5,
                min_lr   = 0.00001,
                verbose  = 1
            ),
        ]

        history = model.fit(
            X_train, y_train,
            validation_data = (X_val, y_val),
            epochs          = epochs,
            batch_size      = 32,
            callbacks       = callbacks,
            verbose         = 1,
            shuffle         = False,   # Don't shuffle time series data!
        )

        # Log final accuracy
        final_acc = history.history['val_accuracy'][-1]
        logger.info(f"Training complete. Final validation accuracy: {final_acc:.2%}")

        return model, history

    except Exception as e:
        logger.error(f"Training error: {e}")
        raise


def save_model(model, symbol: str, scaler_dict: dict = None):
    """
    Save trained model to disk.

    Args:
        model:      trained Keras model
        symbol:     e.g. 'BTCUSDT', 'EURUSD', 'XAUUSD'
        scaler_dict: normalization values (also saved)

    Saves:
        saved_models/BTCUSDT.keras  → model weights
        saved_models/BTCUSDT.pkl    → scaler values
    """
    import pickle

    symbol     = symbol.upper()
    model_path = os.path.join(MODELS_DIR, f"{symbol}.keras")
    scaler_path= os.path.join(MODELS_DIR, f"{symbol}_scaler.pkl")

    try:
        # Save model
        model.save(model_path)
        logger.info(f"Model saved: {model_path}")

        # Save scaler
        if scaler_dict:
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler_dict, f)
            logger.info(f"Scaler saved: {scaler_path}")

    except Exception as e:
        logger.error(f"Error saving model for {symbol}: {e}")
        raise


def load_model(symbol: str):
    """
    Load a previously trained model from disk.

    Args:
        symbol: e.g. 'BTCUSDT', 'EURUSD', 'XAUUSD'

    Returns:
        tuple: (model, scaler_dict) or (None, None) if not found
    """
    import pickle
    from tensorflow.keras.models import load_model as keras_load

    symbol      = symbol.upper()
    model_path  = os.path.join(MODELS_DIR, f"{symbol}.keras")
    scaler_path = os.path.join(MODELS_DIR, f"{symbol}_scaler.pkl")

    # Check if model exists
    if not os.path.exists(model_path):
        logger.warning(f"No trained model found for {symbol}")
        logger.warning(f"Run: python manage.py train_models --symbol {symbol}")
        return None, None

    try:
        # Load model
        model = keras_load(model_path)
        logger.info(f"Model loaded for {symbol}")

        # Load scaler
        scaler_dict = None
        if os.path.exists(scaler_path):
            with open(scaler_path, 'rb') as f:
                scaler_dict = pickle.load(f)

        return model, scaler_dict

    except Exception as e:
        logger.error(f"Error loading model for {symbol}: {e}")
        return None, None


def model_exists(symbol: str) -> bool:
    """Check if a trained model exists for this symbol."""
    symbol     = symbol.upper()
    model_path = os.path.join(MODELS_DIR, f"{symbol}.keras")
    return os.path.exists(model_path)


def predict(model, X: np.ndarray) -> tuple:
    """
    Run prediction on input sequences.

    Args:
        model: loaded Keras model
        X:     input array shape (samples, lookback, features)

    Returns:
        tuple: (direction, confidence)
          direction:  'UP' or 'DOWN'
          confidence: float 0.0 to 1.0 (e.g. 0.73 = 73% confident)
    """
    try:
        # Get raw probability (0 to 1)
        prob = float(model.predict(X, verbose=0)[0][0])

        if prob >= 0.5:
            direction  = 'UP'
            confidence = prob          # e.g. 0.73
        else:
            direction  = 'DOWN'
            confidence = 1.0 - prob   # e.g. 0.27 → confidence is 0.73

        logger.debug(f"Prediction: {direction} ({confidence:.2%} confident)")
        return direction, confidence

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return 'NEUTRAL', 0.0


def get_tp_sl_from_prediction(
    direction:   str,
    confidence:  float,
    symbol_type: str = 'CRYPTO'
) -> dict:
    """
    Convert ML prediction into TP/SL percentage suggestions.

    Logic:
      Higher confidence → wider TP, tighter SL
      Lower confidence  → conservative TP/SL

    Args:
        direction:   'UP' or 'DOWN'
        confidence:  float 0.0 to 1.0
        symbol_type: 'CRYPTO', 'FOREX', or 'COMMODITY'

    Returns:
        dict with tp_percent, sl_percent, direction, confidence
    """

    # Base TP/SL values differ by market type
    # Crypto is more volatile than Forex
    base_values = {
        'CRYPTO':    {'tp_base': 3.0, 'sl_base': 1.5},
        'FOREX':     {'tp_base': 1.0, 'sl_base': 0.5},
        'COMMODITY': {'tp_base': 1.5, 'sl_base': 0.8},
    }

    base = base_values.get(symbol_type, base_values['CRYPTO'])

    # Scale TP/SL based on confidence
    # confidence 0.5 → 0.0 multiplier (minimum)
    # confidence 1.0 → 1.0 multiplier (maximum)
    confidence_scale = (confidence - 0.5) * 2   # maps 0.5-1.0 to 0.0-1.0
    confidence_scale = max(0.1, confidence_scale) # minimum 0.1

    if direction == 'UP':
        # Price predicted to go UP
        # → wide TP (catch the upside), tight SL (limit downside)
        tp_percent = round(base['tp_base'] * (1 + confidence_scale), 1)
        sl_percent = round(base['sl_base'] * (1 - confidence_scale * 0.3), 1)

    elif direction == 'DOWN':
        # Price predicted to go DOWN
        # → tight TP, wider SL (price may continue down)
        tp_percent = round(base['tp_base'] * (1 - confidence_scale * 0.3), 1)
        sl_percent = round(base['sl_base'] * (1 + confidence_scale), 1)

    else:
        # NEUTRAL — use default conservative values
        tp_percent = base['tp_base']
        sl_percent = base['sl_base']

    # Ensure TP is always bigger than SL (good risk/reward)
    if tp_percent <= sl_percent:
        tp_percent = round(sl_percent * 2, 1)

    # Clamp values to safe ranges
    tp_percent = max(0.5, min(tp_percent, 20.0))
    sl_percent = max(0.3, min(sl_percent, 10.0))

    return {
        'tp_percent':  tp_percent,
        'sl_percent':  sl_percent,
        'direction':   direction,
        'confidence':  round(confidence * 100, 1),  # as percentage e.g. 73.5
        'confidence_raw': confidence,
    }