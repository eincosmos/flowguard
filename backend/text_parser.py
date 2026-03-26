import json
import re
import os
from datetime import datetime, timedelta
from typing import Optional, Literal, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator, ValidationError

load_dotenv()

# 🔥 SAFE CLIENT INIT
try:
    from openai import OpenAI
    api_key = os.getenv("GROQ_API_KEY")
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    ) if api_key else None
except:
    client = None


# ==========================================
# 🔥 1. SCHEMA
# ==========================================
class TransactionSchema(BaseModel):
    counterparty: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    due_date: str
    category: Literal["GST", "RENT", "SUPPLIER", "LOAN", "SALARY", "INCOME", "OTHER"]
    direction: Literal["IN", "OUT"]
    status: Literal["PENDING", "OVERDUE", "PAID"] = "PENDING"

    @validator("due_date")
    def validate_date(cls, v):
        datetime.strptime(v, "%Y-%m-%d")
        return v


# ==========================================
# 🔥 2. HELPERS
# ==========================================
def _extract_amount(text: str) -> float:
    text = text.lower().replace('o', '0')  # OCR fix
    match = re.search(r'₹?\s*([\d,]+\.?\d*)\s*(k|thousand)?', text)

    if not match:
        return 0.0

    amt = float(match.group(1).replace(',', ''))
    if match.group(2):
        amt *= 1000

    return amt


def _parse_date(text: str) -> str:
    from dateutil import parser as date_parser

    try:
        dt = date_parser.parse(text, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except:
        return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")


def _extract_counterparty(text: str) -> str:
    patterns = [
        r'to\s+([A-Za-z\s]+)',
        r'from\s+([A-Za-z\s]+)',
        r'for\s+([A-Za-z\s]+)'
    ]

    for p in patterns:
        match = re.search(p, text, re.I)
        if match:
            return match.group(1).strip()

    text_lower = text.lower()
    if "gst" in text_lower:
        return "GST Department"
    if "rent" in text_lower:
        return "Landlord"
    if "salary" in text_lower:
        return "Employees"

    return "Unknown"


# ==========================================
# 🔥 3. FALLBACK PARSER
# ==========================================
def _fallback_parse(text: str) -> dict:
    text_lower = text.lower()

    amount = _extract_amount(text)
    due_date = _parse_date(text)
    counterparty = _extract_counterparty(text)

    direction = "IN" if any(w in text_lower for w in ["receive", "income", "incoming"]) else "OUT"

    if "gst" in text_lower:
        category = "GST"
    elif "rent" in text_lower:
        category = "RENT"
    elif "salary" in text_lower:
        category = "SALARY"
    elif "loan" in text_lower or "emi" in text_lower:
        category = "LOAN"
    elif direction == "IN":
        category = "INCOME"
    else:
        category = "SUPPLIER"

    return {
        "counterparty": counterparty,
        "amount": amount,
        "due_date": due_date,
        "category": category,
        "direction": direction,
        "status": "PENDING"
    }


# ==========================================
# 🔥 4. MAIN PARSER
# ==========================================
def parse_text_to_transaction(text: str, use_fallback: bool = True) -> Optional[dict]:

    if client:
        try:
            prompt = f"""
Extract financial data from this text:

"{text}"

Return JSON:
{{
  "counterparty": "",
  "amount": number,
  "due_date": "YYYY-MM-DD",
  "category": "GST | RENT | SUPPLIER | LOAN | SALARY | INCOME | OTHER",
  "direction": "IN | OUT",
  "status": "PENDING"
}}
"""

            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            data = json.loads(response.choices[0].message.content)

            # Normalize amount
            data["amount"] = _extract_amount(str(data.get("amount", ""))) or data.get("amount", 0)

            validated = TransactionSchema(**data)
            result = validated.model_dump()

            result["confidence"] = 0.9
            return result

        except Exception as e:
            print(f"⚠️ LLM failed: {e}")

    if use_fallback:
        print("🔄 Using fallback parser...")
        result = _fallback_parse(text)

        try:
            validated = TransactionSchema(**result)
            result = validated.model_dump()
            result["confidence"] = 0.7
            return result
        except:
            return result

    return None


# ==========================================
# 🔥 5. BATCH PARSER
# ==========================================
def parse_batch_transactions(texts: List[str]) -> List[dict]:
    results = []
    for t in texts:
        txn = parse_text_to_transaction(t)
        if txn:
            results.append(txn)
    return results


# ==========================================
# 🚀 TEST
# ==========================================
if __name__ == "__main__":
    examples = [
        "Pay GST of ₹20,000 by 2026-04-15",
        "Receive salary income of 50k next Friday",
        "Office rent 45000 due tomorrow",
        "Vendor payment 3500 rupees by month end"
    ]

    print("🚀 Parsing...\n")
    for ex in examples:
        print("INPUT:", ex)
        print(json.dumps(parse_text_to_transaction(ex), indent=2))
        print("-" * 50)