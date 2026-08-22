"""
trades/chatbot/calculator.py
Trading Math Calculator — handles full math expressions.
"""

import re
import logging

logger = logging.getLogger(__name__)


def extract_numbers(text: str) -> list:
    """Extract all numbers. Handles 65,000 → 65000 and decimals."""
    cleaned = re.sub(r'(\d),(\d)', r'\1\2', text)
    cleaned = re.sub(r'(\d),(\d)', r'\1\2', cleaned)
    cleaned = re.sub(r'(\d),(\d)', r'\1\2', cleaned)
    matches = re.findall(r'[-+]?\d+\.?\d*', cleaned)
    numbers = []
    for m in matches:
        try:
            numbers.append(float(m))
        except ValueError:
            pass
    return numbers


def detect_calculation(query: str):
    """Detect calculation type."""
    q = query.lower().strip()
    numbers = extract_numbers(q)

    # ── Complex math expression (has multiple operators or parentheses) ──
    if _looks_like_math_expression(q):
        return 'expression'

    # ── Simple math (one operator, 2 numbers) ──
    if len(numbers) >= 2:
        if any(op in q for op in ['+', '-', '*', '/', '=', 'plus', 'minus',
                                    'times', 'divided', 'sum of', 'add', 'subtract',
                                    'multiply', 'into']):
            return 'simple_math'

    # ── Percentage ──
    if '%' in q or 'percent' in q or 'percentage' in q:
        return 'percentage'

    # ── Trading calculations ──
    if any(w in q for w in ['risk reward', 'risk/reward', 'r:r', 'r/r ratio']):
        return 'risk_reward'

    if 'position size' in q or 'position sizing' in q:
        return 'position_size'

    if 'entry' in q and ('tp' in q or 'take profit' in q):
        return 'trade_calc'

    if any(w in q for w in ['profit', 'loss', 'pnl', 'p&l']):
        if any(w in q for w in ['calculate', 'compute', 'what', 'find']):
            return 'pnl_calc'

    return None


def _looks_like_math_expression(query: str) -> bool:
    """
    Detect if query contains a complex math expression.
    Triggers when query has 2+ math operators, parentheses, or 3+ numbers with operators.
    """
    q = query.strip()

    # Count math operators
    operators = sum(q.count(op) for op in ['+', '-', '*', '/', '×', '÷'])

    # Has parentheses?
    has_parens = '(' in q and ')' in q

    # Has 3+ numbers?
    numbers = extract_numbers(q)
    has_many_numbers = len(numbers) >= 3

    # Math expression if: 2+ operators OR parentheses OR 3+ numbers with operator
    if operators >= 2:
        return True
    if has_parens and operators >= 1:
        return True
    if has_many_numbers and operators >= 1:
        return True

    return False


def try_calculate(query: str):
    """Try to perform calculation. Returns answer dict or None."""
    calc_type = detect_calculation(query)
    if not calc_type:
        return None

    numbers = extract_numbers(query)

    try:
        if calc_type == 'expression':
            return _calc_expression(query)
        elif calc_type == 'simple_math':
            return _calc_simple_math(query, numbers)
        elif calc_type == 'percentage':
            return _calc_percentage(query, numbers)
        elif calc_type == 'trade_calc':
            return _calc_trade(query, numbers)
        elif calc_type == 'risk_reward':
            return _calc_risk_reward(numbers)
        elif calc_type == 'position_size':
            return _calc_position_size(query, numbers)
        elif calc_type == 'pnl_calc':
            return _calc_pnl(numbers)
    except Exception as e:
        logger.error(f"Calculator error: {e}")
        return None

    return None


# ─────────────────────────────────────────────────────
#  Complex Expression Evaluator (NEW)
# ─────────────────────────────────────────────────────

def _calc_expression(query: str):
    """
    Safely evaluate math expressions like:
      "4 + 5 / 5"
      "90 + (9.8 * 3.9) / 90"
      "(10 + 5) * 2"
    """
    q = query.strip()

    # Extract just the math part (remove "=" and "?" and text)
    # Replace common words with operators
    q = q.replace('×', '*').replace('÷', '/')
    q = q.replace('plus', '+').replace('minus', '-')
    q = q.replace('times', '*').replace('divided by', '/').replace('divide by', '/')
    q = q.replace('multiply', '*').replace('multiplied by', '*')

    # Remove "=" and "?" and text labels
    q = re.sub(r'[=?]', '', q)

    # Remove commas in numbers
    q = re.sub(r'(\d),(\d)', r'\1\2', q)
    q = re.sub(r'(\d),(\d)', r'\1\2', q)

    # Extract only valid math characters
    math_expr = re.sub(r'[^0-9+\-*/().\s]', '', q).strip()

    if not math_expr:
        return None

    # Check it has at least one operator
    if not any(op in math_expr for op in ['+', '-', '*', '/']):
        return None

    # Validate it's safe to eval (only math chars)
    if not re.match(r'^[\d+\-*/().\s]+$', math_expr):
        return None

    # Check for empty parens or invalid syntax
    if '()' in math_expr or '//' in math_expr or '**' in math_expr:
        return None

    try:
        # Safe eval - only math characters allowed
        result = eval(math_expr, {"__builtins__": {}}, {})

        return {
            'answer': f"**{math_expr} = {_fmt_num(result)}**",
            'source': 'calculator',
        }
    except ZeroDivisionError:
        return {'answer': "❌ Cannot divide by zero.", 'source': 'calculator'}
    except Exception as e:
        logger.error(f"Expression eval error: {e}")
        return None


# ─────────────────────────────────────────────────────
#  Simple Math (2 numbers, 1 operator)
# ─────────────────────────────────────────────────────

def _calc_simple_math(query: str, numbers: list):
    """Simple arithmetic with 2 numbers."""
    q = query.lower()

    if len(numbers) < 2:
        return None

    a, b = numbers[0], numbers[1]

    if '+' in q or 'plus' in q or 'add' in q or 'sum' in q:
        result = a + b
        return {'answer': f"**{_fmt_num(a)} + {_fmt_num(b)} = {_fmt_num(result)}**",
                'source': 'calculator'}

    if '-' in q or 'minus' in q or 'subtract' in q:
        result = a - b
        return {'answer': f"**{_fmt_num(a)} - {_fmt_num(b)} = {_fmt_num(result)}**",
                'source': 'calculator'}

    if '*' in q or 'times' in q or 'multiply' in q or 'into' in q:
        result = a * b
        return {'answer': f"**{_fmt_num(a)} × {_fmt_num(b)} = {_fmt_num(result)}**",
                'source': 'calculator'}

    if '/' in q or 'divided' in q or 'divide' in q:
        if b == 0:
            return {'answer': "❌ Cannot divide by zero.", 'source': 'calculator'}
        result = a / b
        return {'answer': f"**{_fmt_num(a)} ÷ {_fmt_num(b)} = {_fmt_num(result)}**",
                'source': 'calculator'}

    return None


def _fmt_num(n):
    """Format number nicely."""
    if isinstance(n, (int, float)):
        if n == int(n):
            return f"{int(n):,}"
        return f"{n:,.4f}".rstrip('0').rstrip('.')
    return str(n)


# ─────────────────────────────────────────────────────
#  Percentage (handles all phrasings)
# ─────────────────────────────────────────────────────

def _calc_percentage(query: str, numbers: list):
    """Smart percentage detection."""
    if len(numbers) < 2:
        return None

    q = query.lower()
    pct_value = None
    other_value = None

    pct_match = re.search(r'(\d+\.?\d*)\s*%', q)
    if pct_match:
        pct_value = float(pct_match.group(1))
        for n in numbers:
            if abs(n - pct_value) > 0.001:
                other_value = n
                break

    if pct_value is None:
        pct_match = re.search(r'(\d+\.?\d*)\s*percent', q)
        if pct_match:
            pct_value = float(pct_match.group(1))
            for n in numbers:
                if abs(n - pct_value) > 0.001:
                    other_value = n
                    break

    if pct_value is None or other_value is None:
        pct_value = numbers[0]
        other_value = numbers[1] if len(numbers) > 1 else 100

    if 'change' in q or ('from' in q and 'to' in q):
        old, new = numbers[0], numbers[1]
        if old == 0:
            return {'answer': "❌ Cannot calculate change from 0.", 'source': 'calculator'}
        change = ((new - old) / old) * 100
        return {
            'answer': f"**Change from {_fmt_num(old)} to {_fmt_num(new)} = {change:+.2f}%**",
            'source': 'calculator',
        }

    result = (pct_value / 100) * other_value
    return {
        'answer': f"**{_fmt_num(pct_value)}% of {_fmt_num(other_value)} = {_fmt_num(result)}**",
        'source': 'calculator',
    }


# ─────────────────────────────────────────────────────
#  Trading Calculations (unchanged)
# ─────────────────────────────────────────────────────

def _calc_trade(query: str, numbers: list):
    """Trade analysis."""
    if len(numbers) < 3:
        return None

    entry, tp, sl = numbers[0], numbers[1], numbers[2]
    tp_distance = tp - entry
    sl_distance = entry - sl
    tp_percent = (tp_distance / entry) * 100
    sl_percent = (sl_distance / entry) * 100
    rr = abs(tp_distance) / sl_distance if sl_distance > 0 else 0

    if rr >= 3:
        verdict = '🟢 EXCELLENT'
    elif rr >= 2:
        verdict = '✅ GOOD'
    elif rr >= 1.5:
        verdict = '⚠️ MODERATE'
    else:
        verdict = '❌ POOR'

    answer = f"""**📊 Trade Analysis**

Entry: ${entry:,.2f}
TP: ${tp:,.2f} ({tp_percent:+.2f}%)
SL: ${sl:,.2f} ({sl_percent:.2f}% risk)

**R/R: 1:{rr:.2f}** — {verdict}"""

    return {'answer': answer, 'source': 'calculator'}


def _calc_risk_reward(numbers: list):
    if len(numbers) < 2:
        return {'answer': "Need 2 numbers. Try: 'R/R for entry 100 TP 110 SL 95'",
                'source': 'calculator'}

    if len(numbers) >= 3:
        return _calc_trade("entry tp sl", numbers)

    profit, loss = numbers[0], numbers[1]
    rr = profit / loss if loss > 0 else 0
    return {
        'answer': f"**R/R Ratio: 1:{rr:.2f}**\nProfit ${profit:,.2f} / Loss ${loss:,.2f}",
        'source': 'calculator',
    }


def _calc_position_size(query: str, numbers: list):
    if len(numbers) < 4:
        return {'answer': "Need 4 numbers: account, risk%, entry, SL.\nTry: 'Position size 5000 2% 65000 64500'",
                'source': 'calculator'}

    account, risk_pct, entry, sl = numbers[0], numbers[1], numbers[2], numbers[3]
    risk_amt = account * (risk_pct / 100)
    price_risk = abs(entry - sl)

    if price_risk == 0:
        return {'answer': "❌ Entry = SL not allowed.", 'source': 'calculator'}

    units = risk_amt / price_risk
    position_value = units * entry

    return {
        'answer': f"""**📐 Position Size**

Account: ${account:,.2f}
Risk: {risk_pct}% = ${risk_amt:,.2f}
Units: **{units:.4f}**
Position Value: **${position_value:,.2f}**
Max Loss: ${risk_amt:,.2f}""",
        'source': 'calculator',
    }


def _calc_pnl(numbers: list):
    if len(numbers) < 2:
        return {'answer': "Need entry & exit. Try: 'PnL entry 100 exit 110'",
                'source': 'calculator'}

    entry, exit_price = numbers[0], numbers[1]
    pnl_dollars = exit_price - entry
    pnl_percent = (pnl_dollars / entry) * 100
    result_emoji = '🟢' if pnl_dollars >= 0 else '🔴'

    return {
        'answer': f"""{result_emoji} **PnL: ${pnl_dollars:+,.4f} ({pnl_percent:+.2f}%)**
Entry ${entry:,.4f} → Exit ${exit_price:,.4f}""",
        'source': 'calculator',
    }