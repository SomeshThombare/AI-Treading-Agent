"""
trades/chatbot/ai_engine.py
Main AI Engine — Hybrid Routing System (IMPROVED VERSION)
"""

import logging
import time
from django.conf import settings

from .trading_kb import search_kb
from .calculator import try_calculate

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
#  Gemini Configuration
# ─────────────────────────────────────────────────────

GEMINI_AVAILABLE = False
gemini_model = None

try:
    import google.generativeai as genai

    if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)

        # ── IMPROVED SYSTEM PROMPT ──
        SYSTEM_PROMPT = """You are a helpful trading assistant chatbot. Be friendly, concise, and direct.

CRITICAL RULES YOU MUST FOLLOW:

1. **SHORT ANSWERS BY DEFAULT**
   - For simple math: Give ONLY the answer in 1 line.
   - For simple questions: Reply in 1-3 sentences.
   - Only give long answers when user asks "explain in detail".

2. **ANSWER MATH DIRECTLY**
   - "300 of 30%" → "90" (that's it!)
   - "0.3 + 0.5" → "0.8"
   - "What is 2+2" → "4"
   - DO NOT add trading examples unless asked.

3. **DON'T REFUSE GENERAL QUESTIONS**
   - If user asks general knowledge (PM of India, weather, time),
     answer briefly then offer to help with trading.
   - Example: "Narendra Modi is current PM of India. Now back to trading - any questions?"
   - Don't refuse simple factual questions.

4. **FOR CHART IMAGES — BE PRACTICAL**
   - If user asks "market UP or DOWN?" → give the direction from chart.
   - If user asks "buy or sell?" → give educational direction based on what chart shows.
   - Always remind it's for paper trading practice.
   - DO NOT keep refusing — give the analysis they asked for.

5. **SPECIFIC QUESTIONS DESERVE SPECIFIC ANSWERS**
   - User asks "today's volatile pairs?" → give actual common volatile pairs
     (GBP/JPY, EUR/JPY, GBP/AUD typically volatile) and brief why.
   - Don't just say "I cannot give real-time data" — give educational examples.

6. **MATCH USER'S LANGUAGE**
   - User writes in Hindi/Marathi → reply in same language.
   - User writes informal → reply informally.
   - User writes brief → reply brief.

7. **FORMATTING**
   - Use **bold** only for key answer values.
   - No bullet points unless user asks for list.
   - No "Practical Example:" sections unless requested.
   - Plain conversational text is best.

REMEMBER: Users hate long lectures. Be the helpful friend, not a textbook."""

        # gemini_model = genai.GenerativeModel(
        #     'gemini-2.5-flash',
        #     system_instruction=SYSTEM_PROMPT,
        # )
        gemini_model = genai.GenerativeModel(
    'gemini-2.5-flash-lite',   # ← 4x more daily requests (1000 vs 250)
    system_instruction=SYSTEM_PROMPT,
)
        GEMINI_AVAILABLE = True
        logger.info("[AI] Gemini API initialized with improved prompt")
    else:
        logger.warning("[AI] Gemini API key not configured")

except ImportError:
    logger.error("[AI] google-generativeai package not installed")
except Exception as e:
    logger.error(f"[AI] Gemini initialization failed: {e}")


# ─────────────────────────────────────────────────────
#  Main Routing Function
# ─────────────────────────────────────────────────────

def get_response(query: str, image=None, chat_history=None):
    """Main entry point — routes query to best handler."""
    start_time = time.time()

    # Image upload → Gemini Vision
    if image is not None:
        result = _analyze_image(query, image)
        result['response_time_ms'] = int((time.time() - start_time) * 1000)
        return result

    if not query or not query.strip():
        return {
            'answer': "Please type a question or upload a chart! 💬",
            'source': 'system',
            'response_time_ms': 0,
        }

    # Priority 1: Math (instant)
    calc_result = try_calculate(query)
    if calc_result:
        calc_result['response_time_ms'] = int((time.time() - start_time) * 1000)
        return calc_result

    # Priority 2: KB (instant) — ONLY for clear topical questions
    # Skip KB if query looks like a question that needs context-aware AI
    if _should_use_kb(query):
        kb_result = search_kb(query)
        if kb_result:
            kb_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return kb_result

    # Priority 3: Gemini AI
    if GEMINI_AVAILABLE:
        ai_result = _ask_gemini(query, chat_history)
        ai_result['response_time_ms'] = int((time.time() - start_time) * 1000)
        return ai_result

    # Fallback
    return {
        'answer': (
            "Try asking about RSI, MACD, Doji, or simple math calculations!"
        ),
        'source': 'fallback',
        'response_time_ms': int((time.time() - start_time) * 1000),
    }


def _should_use_kb(query: str) -> bool:
    """
    Decide if query should use KB or go to AI.
    KB is for direct concept questions like 'what is RSI'.
    Skip KB for context-dependent questions.
    """
    q = query.lower().strip()

    # Short queries asking for definition → use KB
    if len(q.split()) <= 6:
        return True

    # Skip KB if asking for prediction/analysis/recommendation
    skip_words = [
        'predict', 'forecast', 'guess', 'analyze the',
        'should i', 'when should', 'best time',
        'today', 'now', 'currently', 'this week',
        'recommend', 'suggest', 'which pair',
        'how about', 'what about',
    ]
    if any(w in q for w in skip_words):
        return False

    return True


# ─────────────────────────────────────────────────────
#  Gemini Text Q&A
# ─────────────────────────────────────────────────────

def _ask_gemini(query: str, chat_history=None):
    """Send query to Gemini API."""
    if not GEMINI_AVAILABLE:
        return {'answer': "AI service not configured.", 'source': 'ai_error'}

    try:
        prompt = _build_prompt(query, chat_history)
        logger.info(f"[AI] Calling Gemini: {query[:60]}...")
        response = gemini_model.generate_content(prompt)
        answer_text = response.text if hasattr(response, 'text') else str(response)

        return {'answer': answer_text.strip(), 'source': 'gemini_ai'}

    except Exception as e:
        logger.exception("Gemini call failed")
        return {
            'answer': f"⚠️ AI temporarily unavailable. Error: {str(e)[:80]}",
            'source': 'ai_error',
        }


def _build_prompt(query: str, chat_history=None):
    """Build context-aware prompt."""
    parts = []

    if chat_history:
        recent = chat_history[-4:]
        if recent:
            parts.append("Recent conversation:")
            for msg in recent:
                role = "User" if msg.get('role') == 'user' else "Assistant"
                text = msg.get('message', '')[:150]
                parts.append(f"{role}: {text}")
            parts.append("")

    parts.append(f"User: {query}")
    parts.append("Assistant (be SHORT and DIRECT):")

    return "\n".join(parts)


# ─────────────────────────────────────────────────────
#  Image Analysis
# ─────────────────────────────────────────────────────

def _analyze_image(query: str, image):
    """Analyze chart with Gemini Vision."""
    if not GEMINI_AVAILABLE:
        return {
            'answer': "📷 Image received but AI vision not configured.",
            'source': 'ai_error',
        }

    try:
        if not query or not query.strip():
            query = "Analyze this chart"

        # Detect if user wants short or detailed analysis
        short_keywords = ['short', 'brief', 'quick', 'simple', 'just',
                          'tell me', 'direction', 'up or down', 'buy or sell']
        wants_short = any(w in query.lower() for w in short_keywords)

        if wants_short:
            vision_prompt = f"""User uploaded a trading chart and asked: "{query}"

Give a SHORT educational answer (2-4 lines max):
1. Current direction (uptrend/downtrend/sideways)
2. Key observation (1 candle pattern or indicator signal)
3. Educational suggestion for paper trade (entry/exit idea)

Be direct. This is for paper trading education only."""
        else:
            vision_prompt = f"""User uploaded a trading chart and asked: "{query}"

Provide a clear analysis covering:
1. **Trend direction**: Where is price heading?
2. **Key pattern**: Any notable candle pattern?
3. **Support/Resistance**: Important price levels
4. **Educational insight**: What to learn from this chart

Keep it concise. Use **bold** for important values.
This is for paper trading education."""

        logger.info("[AI] Calling Gemini Vision")
        response = gemini_model.generate_content([vision_prompt, image])
        answer_text = response.text if hasattr(response, 'text') else str(response)

        return {
            'answer': f"🖼️ **Chart Analysis**\n\n{answer_text.strip()}",
            'source': 'gemini_vision',
        }

    except Exception as e:
        logger.exception("Vision call failed")
        return {
            'answer': f"⚠️ Image analysis failed: {str(e)[:80]}",
            'source': 'ai_error',
        }


def check_status():
    """Check AI engine health."""
    return {
        'gemini_available': GEMINI_AVAILABLE,
        'model_name': 'gemini-2.5-flash' if GEMINI_AVAILABLE else None,
        'kb_topics': 18,
        'calculator': True,
    }