import re
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


# =============================
# DATA MODEL
# =============================
@dataclass
class Transaction:
    amount: float
    direction: str  # IN | OUT
    due_date: Optional[str]
    category: str
    counterparty_name: Optional[str]
    flexibility: str = "DEFERRABLE"
    penalty_rate_annual: float = 0.0
    obligation_weight: float = 3.0
    relationship_score: float = 50.0
    is_recurring: bool = False
    penalty_per_day: float = 0.0
    source_hash: Optional[str] = None
    source_file: Optional[str] = None
    confidence: float = 0.0


# =============================
# NORMALIZATION
# =============================
_OCR_MAP = str.maketrans({
    "O": "0", "o": "0",
    "I": "1", "l": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "₹": ""
})

def _normalize_text(text: str) -> str:
    text = text.translate(_OCR_MAP)

    # Remove multi-character currency strings
    text = re.sub(r'\b(rs\.?|inr\.?)\b', '', text, flags=re.I)

    # 25k → 25000
    text = re.sub(r'(\d+)\s*k\b',
                  lambda m: str(int(m.group(1)) * 1000),
                  text, flags=re.I)

    # 31 800 → 31800
    text = re.sub(r'(\d)\s+(\d{3})', r'\1\2', text)

    return text


# =============================
# AMOUNT EXTRACTION
# =============================
_AMOUNT_PATTERN = re.compile(
    r'(?<!\w)(?:₹|rs\.?|inr\.?)?\s*((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)(?!\w)',
    re.IGNORECASE
)


def _extract_amount(text: str) -> Optional[float]:
    matches = []

    for m in _AMOUNT_PATTERN.finditer(text):
        raw = m.group(0)
        num = m.group(1).replace(",", "")

        try:
            val = float(num)
        except:
            continue

        score = 0.5

        if "₹" in raw or "rs" in raw.lower():
            score += 0.3
        if "." in num:
            score += 0.1

        matches.append((val, score, m.start()))

    if not matches:
        return None

    matches.sort(key=lambda x: (x[1], -x[2]), reverse=True)
    return matches[0][0]


# =============================
# DATE EXTRACTION
# =============================
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}


def _extract_due_date(text: str) -> Optional[str]:
    t = text.lower()

    # 30/03/2026
    m = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b', t)
    if m:
        d, mo, y = map(int, m.groups())
        if y < 100:
            y += 2000
        return datetime(y, mo, d).strftime("%Y-%m-%d")

    # March 30 2026
    m = re.search(
        r'\b(' + '|'.join(_MONTHS.keys()) + r')\s+(\d{1,2})(?:,)?\s+(\d{4})\b', t)
    if m:
        mo = _MONTHS[m.group(1)]
        d = int(m.group(2))
        y = int(m.group(3))
        return datetime(y, mo, d).strftime("%Y-%m-%d")

    return None


# =============================
# CATEGORY + DIRECTION
# =============================
def _infer_category(text: str) -> str:
    t = text.lower()
    if "rent" in t or "landlord" in t:
        return "RENT"
    if "tax" in t or "gst" in t:
        return "TAX"
    if "salary" in t:
        return "SALARY"
    if "supplier" in t or "vendor" in t:
        return "SUPPLIER"
    if "loan" in t or "emi" in t:
        return "LOAN"
    return "OTHER"


def _infer_direction(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["received", "credited"]):
        return "IN"
    return "OUT"


# =============================
# COUNTERPARTY
# =============================
def _extract_counterparty(text: str) -> Optional[str]:
    t = text.lower()

    if "landlord" in t:
        return "Landlord"
    if "owner" in t:
        return "Owner"

    patterns = [
        r'paid to\s+([a-z\s]+)',
        r'received from\s+([a-z\s]+)',
        r'to\s+([a-z\s]+)\s+on'
    ]

    for p in patterns:
        m = re.search(p, t)
        if m:
            name = m.group(1).strip()
            return " ".join(w.capitalize() for w in name.split())

    return None


# =============================
# ENRICHMENT
# =============================
def _enrichment(category: str):
    mapping = {
        "TAX": (0.18, 5.0, "FIXED"),
        "RENT": (0.12, 4.5, "FIXED"),
        "SUPPLIER": (0.06, 3.5, "DEFERRABLE"),
        "SALARY": (0.0, 5.0, "FIXED"),
        "LOAN": (0.14, 5.0, "FIXED"),
    }
    return mapping.get(category, (0.0, 3.0, "DEFERRABLE"))


# =============================
# HASH
# =============================
def _build_hash(amount, cp, date, text):
    raw = f"{amount}|{cp}|{date}|{text[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# =============================
# MAIN PIPELINE
# =============================
def normalize_input(raw_text: str,
                    source_file: Optional[str] = None) -> Dict[str, Any]:

    text = _normalize_text(raw_text)

    amount = _extract_amount(text)
    due_date = _extract_due_date(text)
    category = _infer_category(text)
    direction = _infer_direction(text)
    counterparty = _extract_counterparty(text)

    penalty, weight, flexibility = _enrichment(category)

    confidence = 0.3
    if amount: confidence += 0.3
    if due_date: confidence += 0.15
    if counterparty: confidence += 0.15
    if category != "OTHER": confidence += 0.1

    tx = Transaction(
        amount=amount or 0.0,
        direction=direction,
        due_date=due_date,
        category=category,
        counterparty_name=counterparty,
        flexibility=flexibility,
        penalty_rate_annual=penalty,
        obligation_weight=weight,
        source_hash=_build_hash(amount, counterparty, due_date, raw_text),
        source_file=source_file,
        confidence=round(min(confidence, 0.99), 2)
    )

    return asdict(tx)


# =============================
# TEST
# =============================
if __name__ == "__main__":
    text = "Landlord rent amount of 25k should be paid on or before March 30 2026"
    print(normalize_input(text))

def normalise_all(data):
    """
    Supports:
    1. JSON input (list of dicts) ✅
    2. File paths (OCR/text) ✅
    """

    results = []

    # =============================
    # CASE 1: JSON INPUT (your test case)
    # =============================
    if isinstance(data, list) and isinstance(data[0], dict):

        for item in data:
            category = item.get("category", "OTHER")

            # enrichment
            penalty, weight, flexibility = _enrichment(category)

            # --- FIX DATE ---
            due_date_str = item.get("due_date")
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except:
                    due_date = None
            else:
                due_date = None

            tx = {
                "amount": item.get("amount", 0.0),
                "direction": "OUT",
                "due_date": due_date,
                "category": category,
                "counterparty_name": item.get("counterparty"),
                "flexibility": flexibility,
                "penalty_rate_annual": penalty,
                "obligation_weight": weight,
                "relationship_score": item.get("relationship_score", 50),
                "is_recurring": item.get("is_recurring", False),
            }

            results.append(tx)

        return {"transactions": results}

    # =============================
    # CASE 2: FILE INPUT (your original logic)
    # =============================
    for f in data:
        with open(f, "r", errors="ignore") as file:
            text = file.read()

        results.append(normalize_input(text, source_file=f))

    return {
        "transactions": results,
        "stats": {
            "count": len(results)
        }
    }