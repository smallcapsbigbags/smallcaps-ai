"""Small, auditable quantity checks. Unsupported arithmetic is rejected, not guessed.

This is not a general financial parser: it recognises scalar monetary amounts,
percentages, basis points and common counts. Semantic comparability still needs review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SCALE = {'': Decimal(1), 'k': Decimal(1000), 'thousand': Decimal(1000),
         'm': Decimal(1000000), 'million': Decimal(1000000),
         'bn': Decimal(1000000000), 'billion': Decimal(1000000000)}
NUMBER = r'[+\-−]?\d[\d,]*(?:\.\d+)?'
RX = re.compile(
    rf'(?<![\w.])(?P<bound>more than|greater than|over|up to|at least|at most|[<>]=?)?\s*'
    rf'(?P<sign>[+\-−])?\s*(?P<currency>£|US\$|A\$|\$|€|GBP\s*|USD\s*|EUR\s*)?\s*'
    rf'(?P<number>{NUMBER})(?P<scale>\s*(?:billion|million|thousand|bn|k|m))?'
    rf'(?P<unit>\s*(?:%|bps\b|basis points\b|p\b|pence\b|months?\b|years?\b|homes?\b|shares?\b))?(?!\w|\.\d)',
    re.I)
CURRENCIES = {'£':'GBP', 'gbp':'GBP', '$':'USD', 'us$':'USD', 'usd':'USD',
              'a$':'AUD', '€':'EUR', 'eur':'EUR'}
BOUNDS = {'more than':'>', 'greater than':'>', 'over':'>', 'up to':'<=',
          'at most':'<=', 'at least':'>='}
WORDS = {'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6',
         'seven':'7','eight':'8','nine':'9','ten':'10','eleven':'11','twelve':'12'}


def normalise(text: str) -> str:
    return ' '.join(text.replace('−','-').replace('–','-').replace('‑','-').split()).lower()


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    unit: str
    bound: str
    precision: Decimal


def quantities(text: str) -> list[Quantity]:
    text = re.sub(r'\b('+'|'.join(WORDS)+r')[- ](?=months?\b|years?\b|homes?\b)',
                  lambda m: WORDS[m[1].lower()]+' ', text, flags=re.I)
    result = []
    for match in RX.finditer(text):
        try:
            raw = match['number'].replace(',','').replace('−','-')
            num = Decimal(raw)
            if match['sign'] in {'-','−'}: num = -abs(num)
        except InvalidOperation:
            continue
        scale = SCALE[(match['scale'] or '').strip().lower()]
        unit = (match['unit'] or '').strip().lower()
        currency = CURRENCIES.get((match['currency'] or '').strip().lower())
        if currency:
            unit = currency
        elif unit in {'p','pence'}:
            unit, scale = 'GBP', Decimal('.01')
        elif unit in {'bps','basis points'}:
            unit, scale = '%', Decimal('.01')
        elif unit.endswith('s') and unit != '%':
            unit = unit[:-1]
        bound = normalise(match['bound'] or '')
        decimals = len(raw.partition('.')[2])
        result.append(Quantity(num*scale, unit or 'number', BOUNDS.get(bound,bound),
                               Decimal(10) ** -decimals * scale))
    return result


def scalar(text: str) -> Quantity | None:
    values = quantities(text)
    return values[0] if len(values) == 1 else None


def source_quantities(text: str) -> list[Quantity]:
    result = quantities(text)
    # Explicit table headers supply the unit for otherwise bare table cells.
    header = re.search(r"£\s*(?:['’]?000|m(?:illion)?\b)", text, re.I)
    if header:
        scale = Decimal(1000) if '000' in header[0] else Decimal(1000000)
        result += [Quantity(q.amount*scale,'GBP',q.bound,q.precision*scale)
                   for q in result if q.unit == 'number']
    return result


def equal_at_display_precision(display: Quantity, source: Quantity) -> bool:
    if display.unit != source.unit:
        return False
    # Counts and dates cannot be rounded away. Monetary figures allow display rounding.
    tolerance = display.precision / 2 if display.unit in {'GBP','USD','EUR','AUD','%'} else Decimal(0)
    return abs(display.amount-source.amount) < tolerance if tolerance else display.amount == source.amount


def supported_numbers(display: str, evidence: str) -> bool:
    if any(q.upper() not in evidence.upper() for q in re.findall(r'\bQ[1-4]\s+20\d{2}\b', display, re.I)):
        return False
    values, candidates = quantities(display), source_quantities(evidence)
    return all(any(equal_at_display_precision(q, c) for c in candidates) for q in values)


def bound_preserved(display: str, evidence: str) -> bool:
    # A floor, ceiling or strict inequality cannot become an exact amount or vice versa.
    for q in quantities(display):
        candidates = [c for c in source_quantities(evidence) if equal_at_display_precision(q,c)]
        if candidates and not any(q.bound == c.bound for c in candidates):
            return False
    return True


def calculate(operation: str, left: Quantity, right: Quantity) -> Quantity:
    if left.unit != right.unit or left.bound or right.bound:
        raise ValueError('Calculation inputs must have matching units and no inequalities')
    if operation in {'ratio','percent-change'} and right.amount == 0:
        raise ValueError('Zero denominator')
    if operation == 'percent-change':
        if right.amount <= 0:
            raise ValueError('Percentage change from a non-positive baseline is ambiguous')
        amount, unit = (left.amount/right.amount-1)*100, '%'
    elif operation == 'ratio':
        amount, unit = left.amount/right.amount*100, '%'
    elif operation == 'difference':
        amount, unit = left.amount-right.amount, left.unit
    elif operation == 'sum':
        amount, unit = left.amount+right.amount, left.unit
    else:
        raise ValueError('Unsupported operation')
    return Quantity(amount, unit, '', Decimal('0.00000001'))
