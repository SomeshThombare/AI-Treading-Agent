# 🤖 AI Trading Agent

**An Intelligent Paper-Trading Platform Using LSTM Neural Networks**

A web-based paper-trading platform that lets beginner traders safely practise BUY/SELL trades on real cryptocurrency, forex, and gold market data — powered by an LSTM deep-learning model, an autonomous trading bot, a background trade monitor, and an AI chatbot assistant.

> ⚠️ **This is a paper-trading (simulation) platform only. No real money or real orders are involved.**

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Tech Stack & Versions](#-tech-stack--versions)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Setup Instructions (Any System)](#-setup-instructions-any-system)
- [Environment Variables / API Keys](#-environment-variables--api-keys)
- [Running the Project](#-running-the-project)
- [Training the LSTM Models](#-training-the-lstm-models)
- [Database Models](#-database-models)
- [APIs & External Services Used](#-apis--external-services-used)
- [Trading Symbols Supported](#-trading-symbols-supported)
- [Model Performance](#-model-performance)
- [Testing](#-testing)
- [Screenshots](#-screenshots)
- [Team](#-team)
- [Future Scope](#-future-scope)
- [License](#-license)

---
---

## 📖 Overview

The **AI Trading Agent** solves a simple problem: beginner traders lose real money because they enter live markets without enough practice or guidance. This platform gives every user a **$10,000 virtual balance** and a full trading workflow — market analysis, AI-assisted trade entry, autonomous execution, live monitoring, and performance reporting — without any financial risk.

At its core is a **two-layer LSTM neural network** trained on historical candlestick data enriched with 19 technical-indicator features. The model predicts short-term price direction and suggests Take Profit (TP) and Stop Loss (SL) levels, which the user can accept or edit before opening a trade.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔐 **User Authentication** | Secure register/login. Every new user starts with a $10,000 virtual balance. |
| 🧠 **LSTM Price Prediction** | Two-layer LSTM (64 + 32 units) predicts UP/DOWN direction with a confidence score. |
| 🎯 **AI-Assisted TP/SL** | Suggests Take Profit & Stop Loss percentages based on the model's prediction and volatility. |
| 📈 **Manual Trading** | Place both **BUY (long)** and **SELL (short)** trades with direction-aware P&L calculation. |
| 🤖 **Autonomous Trading Bot** | Auto-scans selected symbols and opens trades when confidence, risk, and diversification rules are met. |
| 👁️ **Trade Monitor** | Background process that polls live prices and auto-closes trades the instant TP or SL is hit. |
| 💬 **AI Chatbot** | Hybrid assistant — local knowledge base + safe calculator + Google Gemini API for open-ended questions and chart-image analysis. |
| 📊 **Live Charts** | Embedded TradingView widget with Entry / TP / SL lines drawn directly on the chart. |
| 📄 **Portfolio Reports** | Generate PDF (ReportLab) or Excel (openpyxl) reports with equity curve, win/loss chart, and full trade history. |
| 🎨 **Neon Glassmorphism UI** | Custom dark-themed responsive dashboard, built without any frontend framework. |
| ⚙️ **Risk Management** | Configurable max open trades, cooldown after loss, daily loss limit, per-market diversification. |

---

## 🛠 Tech Stack & Versions

### Backend
| Component | Version |
|---|---|
| Python | **3.11** |
| Django | **5.0** |
| SQLite | (bundled with Python) |

### Machine Learning
| Component | Version |
|---|---|
| TensorFlow | **2.15** |
| Keras | (bundled with TensorFlow 2.15) |
| pandas | latest stable (≥2.0) |
| numpy | latest stable (≥1.24) |
| scikit-learn | latest stable (≥1.3) |
| ta (technical analysis) | latest stable |

### Market Data APIs
| Source | Used For | Package |
|---|---|---|
| Binance Public API | Crypto (BTC, ETH, BNB, SOL, XRP) | `python-binance` or raw REST calls |
| MetaTrader5 | Forex & Gold (via XM Global demo account) | `MetaTrader5` (Windows only) |

### AI Chatbot
| Component | Version |
|---|---|
| google-generativeai | **0.7.0** |
| Model used | `gemini-2.5-flash` |

### Reports & Utilities
| Component | Purpose |
|---|---|
| ReportLab | PDF report generation |
| openpyxl | Excel (.xlsx) report generation |
| matplotlib | Chart generation embedded in PDF reports |
| Pillow (PIL) | Image handling for chatbot chart analysis |

### Frontend
| Component | Details |
|---|---|
| HTML5, CSS3, JavaScript | No framework — vanilla JS + Django Templates |
| TradingView Widget | Embedded live candlestick charts |

---

## 🏗 System Architecture

The system follows a **three-tier architecture**:

```
┌─────────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                      │
│   HTML / CSS / JavaScript + TradingView Widget           │
│   (Dashboard, Create Trade, Bot, Chat, Reports pages)     │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│                  APPLICATION LAYER                        │
│   Django 5.0 (Views, URL routing, business logic)         │
│                                                            │
│   ┌───────────────┐  ┌──────────────┐  ┌───────────────┐  │
│   │ LSTM Predictor │  │ Autonomous   │  │ Trade Monitor │  │
│   │ (TensorFlow)   │  │ Bot          │  │ (background)  │  │
│   └───────────────┘  └──────────────┘  └───────────────┘  │
│   ┌───────────────┐  ┌──────────────┐                     │
│   │ AI Chatbot     │  │ Report Gen.  │                     │
│   │ (KB + Gemini)  │  │ (PDF/Excel)  │                     │
│   └───────────────┘  └──────────────┘                     │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│                     DATA LAYER                             │
│         SQLite Database via Django ORM                     │
└─────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
┌───────────────┐               ┌──────────────────┐
│ Binance API    │               │ MetaTrader5 / XM │
│ (Crypto data)  │               │ (Forex & Gold)   │
└───────────────┘               └──────────────────┘
```

The **Trade Monitor** and **Autonomous Bot** run as separate long-lived processes (Django management commands) alongside the main web server, so trade execution and monitoring continue even while the user is not actively browsing the dashboard.

---

## 📁 Project Structure

```
ai_trading_agent/
│
├── manage.py
├── requirements.txt
├── .env                          # API keys & secrets (not committed)
│
├── ai_trading_agent/             # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── trading/                      # Main Django app
│   ├── models.py                 # Trade, AgentConfig, BotLog, UserBalance, etc.
│   ├── views.py                  # Dashboard, Create Trade, Bot, Reports views
│   ├── urls.py
│   ├── forms.py
│   │
│   ├── management/commands/
│   │   ├── run_agent.py          # Trade Monitor (auto-close on TP/SL)
│   │   ├── run_auto_agent.py     # Autonomous Trading Bot
│   │   └── train_models.py       # LSTM training script
│   │
│   ├── ml/
│   │   ├── lstm_model.py         # LSTM architecture & prediction logic
│   │   ├── indicators.py         # 19 technical-indicator feature engineering
│   │   └── data_fetch.py         # Binance / MetaTrader5 data fetchers
│   │
│   ├── chatbot/
│   │   ├── knowledge_base.py     # Local trading Q&A knowledge base
│   │   ├── calculator.py         # Safe math/risk-reward calculator
│   │   └── gemini_client.py      # Google Gemini API integration
│   │
│   ├── reports/
│   │   ├── pdf_report.py         # ReportLab PDF generator
│   │   └── excel_report.py       # openpyxl Excel generator
│   │
│   ├── templates/                # HTML templates (dashboard, trade, bot, chat, reports)
│   └── static/                   # CSS, JS, images
│
├── ml_models/                    # Saved trained LSTM models (.h5 / .keras files)
│   ├── BTCUSDT_model.h5
│   ├── ETHUSDT_model.h5
│   ├── BNBUSDT_model.h5
│   ├── EURUSD_model.h5
│   ├── GBPUSD_model.h5
│   └── XAUUSD_model.h5
│
└── db.sqlite3                    # SQLite database (created on first run)
```

---

## ✅ Prerequisites

Before setting up the project, make sure you have:

- **Python 3.11** installed ([python.org](https://www.python.org/downloads/))
- **pip** (comes with Python)
- **Git** (to clone the repository)
- **Windows OS** — required if using MetaTrader5 for forex/gold (MetaTrader5 Python package is Windows-only)
- An **XM Global demo trading account** (free) — for forex/gold live data via MetaTrader5
- A **Google AI Studio API key** (free tier available) — for the Gemini-powered chatbot
- Internet connection — for live market data (Binance + MetaTrader5) and Gemini API calls

> 💡 If you don't have Windows or don't want to use MetaTrader5, the crypto features (Binance API) work fine on macOS/Linux too — only forex/gold live data requires MetaTrader5.

---

## 🚀 Setup Instructions (Any System)

Follow these steps exactly to set up the project on a **new machine** from scratch.

### Step 1 — Clone the repository
```bash
git clone <your-repository-url>
cd ai_trading_agent
```

### Step 2 — Create and activate a virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install all dependencies
```bash
pip install -r requirements.txt
```

If `requirements.txt` is not present, install manually:
```bash
pip install django==5.0
pip install tensorflow==2.15
pip install pandas numpy scikit-learn
pip install ta
pip install python-binance
pip install MetaTrader5          # Windows only
pip install google-generativeai==0.7.0
pip install reportlab
pip install openpyxl
pip install matplotlib
pip install pillow
pip install python-dotenv
```

### Step 4 — Set up environment variables
Create a `.env` file in the project root (see [Environment Variables](#-environment-variables--api-keys) section below for exact keys needed).

### Step 5 — Apply database migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 6 — Create a superuser (optional, for Django admin access)
```bash
python manage.py createsuperuser
```

### Step 7 — Train the LSTM models (first time only)
```bash
python manage.py train_models --symbol BTCUSDT --candles 5000
python manage.py train_models --symbol ETHUSDT --candles 5000
python manage.py train_models --symbol BNBUSDT --candles 5000
python manage.py train_models --symbol EURUSD --candles 5000
python manage.py train_models --symbol GBPUSD --candles 5000
python manage.py train_models --symbol XAUUSD --candles 5000
```
> ⏱ Each model takes approximately 7–9 minutes to train on a standard laptop (Intel i5, 8GB RAM).

### Step 8 — Run the project
See [Running the Project](#-running-the-project) below — **3 terminals are required**.

---

## 🔑 Environment Variables / API Keys

Create a `.env` file in the project root with the following keys:

```env
# Django
SECRET_KEY=your-django-secret-key-here
DEBUG=True

# Google Gemini API (for AI Chatbot)
GEMINI_API_KEY=your-gemini-api-key-here

# MetaTrader5 / XM Global Demo Account (for Forex & Gold)
MT5_LOGIN=your-xm-demo-account-number
MT5_PASSWORD=your-xm-demo-password
MT5_SERVER=XMGlobal-Demo

# Binance (Public API — no key required for market data, but optional if using authenticated endpoints)
BINANCE_API_KEY=optional-if-using-authenticated-endpoints
BINANCE_API_SECRET=optional-if-using-authenticated-endpoints
```

### How to get each key:

| Key | Where to get it |
|---|---|
| `SECRET_KEY` | Generate any random string, or use Django's `get_random_secret_key()` |
| `GEMINI_API_KEY` | Sign up at [Google AI Studio](https://aistudio.google.com/) → Get API Key (free tier available) |
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | Register a free demo account at [XM Global](https://www.xm.com/) → Download MT5 → Note login credentials |
| `BINANCE_API_KEY` | Not required for public market data (candles, prices). Only needed for authenticated/trading endpoints — [Binance API docs](https://binance-docs.github.io/apidocs/) |

> 🔒 **Never commit your `.env` file to Git.** Add it to `.gitignore`.

---

## ▶️ Running the Project

The system requires **3 separate terminals** running simultaneously (all inside the activated virtual environment):

### Terminal 1 — Web Server
```bash
python manage.py runserver
```
Access the dashboard at: **http://127.0.0.1:8000**

### Terminal 2 — Trade Monitor
```bash
python manage.py run_agent
```
Continuously polls live prices and auto-closes trades when Take Profit or Stop Loss is hit.

### Terminal 3 — Autonomous Trading Bot
```bash
python manage.py run_auto_agent --interval 15
```
Scans selected symbols every 15 minutes (configurable) and opens trades automatically based on LSTM predictions and risk rules.

> ✅ All three must be running for the full experience: manual trading works with just Terminal 1, but bot trading and auto-close require Terminals 2 and 3 as well.

---

## 🧠 Training the LSTM Models

To retrain a model (e.g., with more candles or after a long time gap):

```bash
python manage.py train_models --symbol <SYMBOL> --candles <NUMBER>
```

**Example:**
```bash
python manage.py train_models --symbol BTCUSDT --candles 5000
```

**Parameters:**
- `--symbol` — Trading symbol (e.g., `BTCUSDT`, `ETHUSDT`, `EURUSD`, `XAUUSD`)
- `--candles` — Number of historical candles to train on (default/recommended: `5000`)

Trained models are saved in the `ml_models/` directory and automatically loaded by the prediction engine on the next request.

---

## 🗄 Database Models

| Model | Purpose |
|---|---|
| `User` (Django built-in) | User accounts |
| `UserBalance` | Tracks starting balance ($10,000 default) and current virtual balance per user |
| `Trade` | Stores each trade: symbol, direction (BUY/SELL), quantity, amount, entry price, TP, SL, status, PnL, timestamps |
| `AgentConfig` | Bot settings: confidence thresholds (per market), max open trades, cooldown, daily loss limit, fixed quantity/amount |
| `BotLog` | Logs every bot decision (opened, skipped, reason) with timestamp |
| `Conversation` | Chatbot conversation sessions |
| `ChatMessage` | Individual chatbot messages (user + AI responses) |

---

## 🌐 APIs & External Services Used

| API / Service | Purpose | Docs |
|---|---|---|
| **Binance Public REST API** | Live & historical OHLCV candle data for crypto | https://binance-docs.github.io/apidocs/ |
| **MetaTrader5 Python Package** | Live & historical data + demo trading for Forex/Gold | https://www.mql5.com/en/docs/integration/python_metatrader5 |
| **Google Gemini API** (`gemini-2.5-flash`) | Natural-language chatbot responses + chart image analysis | https://ai.google.dev/ |
| **TradingView Widget** | Embedded live charting on the dashboard | https://www.tradingview.com/widget/ |

---

## 💹 Trading Symbols Supported

| Symbol | Asset | Market Type |
|---|---|---|
| BTCUSDT | Bitcoin | Crypto |
| ETHUSDT | Ethereum | Crypto |
| BNBUSDT | BNB | Crypto |
| SOLUSDT | Solana | Crypto |
| XRPUSDT | Ripple | Crypto |
| EURUSD | Euro / US Dollar | Forex |
| GBPUSD | British Pound / US Dollar | Forex |
| USDJPY | US Dollar / Japanese Yen | Forex |
| XAUUSD | Gold | Commodity |
| XAGUSD | Silver | Commodity |

> Note: LSTM models are currently trained for **6 core symbols** (BTCUSDT, ETHUSDT, BNBUSDT, EURUSD, GBPUSD, XAUUSD). Additional symbols can be added by running `train_models` with the new symbol.

---

## 📊 Model Performance

| Symbol | Validation Accuracy |
|---|---|
| BTCUSDT | 65.2% |
| ETHUSDT | 63.7% |
| BNBUSDT | 62.9% |
| EURUSD | 61.4% |
| GBPUSD | 60.8% |
| **XAUUSD (Gold)** | **67.1%** (best) |
| **Average** | **63.5%** |

**Model Architecture:**
- Input: 60 time-step sequences × 19 technical-indicator features
- Layer 1: LSTM, 64 units (return sequences)
- Dropout: 0.2
- Layer 2: LSTM, 32 units
- Dropout: 0.2
- Dense: 16 units, ReLU
- Output: Dense, 1 unit, Sigmoid (binary UP/DOWN probability)
- Optimizer: Adam | Loss: Binary Cross-Entropy | Early stopping enabled

**19 Technical-Indicator Features (via `ta` library):**
RSI, EMA-9, EMA-21, EMA-50, MACD (+ signal + histogram), ATR, Bollinger Bands (upper/lower/width/%B), Stochastic %K/%D, OBV, price-change %, volume-change %, EMA ratio, price-to-EMA-21 ratio.

---

## 🧪 Testing

- **61 test cases** executed across all modules (Login, Registration, Manual Trade, LSTM Prediction, Autonomous Bot, Trade Monitor, AI Chatbot, Portfolio Reporting, Dashboard, Database)
- **All 61 test cases passed**
- Direction-aware PnL verified with real sample trades:
  - BUY: entry $65,000 → exit $67,000, qty 0.5 BTC → **+$1,000**
  - SELL: entry $65,000 → exit $63,000, qty 0.5 BTC → **+$1,000** (mirrored logic confirmed)

Run tests with:
```bash
python manage.py test
```

---

## 📸 Screenshots

> Screenshots of the Login, Dashboard, Create Trade (with AI Suggestion), Autonomous Bot, AI Chatbot, and Portfolio Reports are available in the `/screenshots` folder or the project report / presentation deck.

---

## 🔮 Future Scope

1. Replace LSTM with **Transformer-based architectures** and incorporate **news-sentiment analysis**.
2. Connect to a **live (small) brokerage account** with realistic slippage and brokerage-fee modelling.
3. Add **cloud deployment** for multi-user access and build **native mobile apps** (iOS/Android).
4. Support additional trading symbols across stocks and other commodities.

---

## 📄 License

This project was developed as a B.Tech academic project for educational purposes. Not licensed for commercial or live-trading use.

---

## 📚 Publication

Research paper published in **IJIRSET (International Journal of Innovative Research in Science, Engineering and Technology)**, Volume 15, Issue 6, June 2026.

---

### 🙋 Need Help?

If you run into setup issues:
1. Confirm Python version: `python --version` → should be **3.11.x**
2. Confirm virtual environment is activated (you should see `(venv)` in your terminal prompt)
3. Confirm all 3 terminals are running for full functionality
4. Check `.env` file has all required API keys filled in
5. For MetaTrader5 issues, confirm you're on **Windows** and the MT5 terminal app is installed and logged in with your XM demo account

---

*Built with ❤️ for beginner traders who want to learn without losing real money.*


