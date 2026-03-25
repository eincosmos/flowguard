import csv
import json
import pdfplumber
import pytesseract
from PIL import Image
from datetime import date
from dateutil import parser as dateparser
from typing import List, Dict, Optional
from pathlib import Path
import re

from models import Transaction


# ════════════════════════════════════════════════════════════════
#  MAIN ENTRY
# ════════════════════════════════════════════════════════════════

def normalise_all(filepaths: List[str]) -> Dict:
    all_transactions = []

    for fp in filepaths:
        ext = Path(fp).suffix.lower()

        if ext == ".json":
            txns = parse_manual_json(fp)
        elif ext == ".csv":
            txns = parse_bank_csv(fp)
        elif ext == ".pdf":
            txns = parse_bank_pdf(fp)
        elif ext in [".jpg", ".png", ".jpeg"]:
            txns = parse_receipt_image(fp)
        else:
            continue

        all_transactions.extend(txns)

    return {
        "transactions": [t.to_dict() for t in all_transactions],
        "stats": {
            "total": len(all_transactions)
        }
    }


# ════════════════════════════════════════════════════════════════
#  JSON PARSER
# ════════════════════════════════════════════════════════════════

def parse_manual_json(filepath: str):
    transactions = []

    with open(filepath, "r") as f:
        data = json.load(f)

    for item in data:
        try:
            t = Transaction(
                amount=float(item["amount"]),
                direction=item.get("direction", "OUT"),
                due_date=_parse_date(item["due_date"]),
                category=item.get("category", "OTHER"),
                counterparty_name=item.get("counterparty", "Unknown"),
                source_file=filepath,
            )
            t.compute_derived_fields()
            transactions.append(t)
        except:
            pass

    return transactions


# ════════════════════════════════════════════════════════════════
#  CSV PARSER
# ════════════════════════════════════════════════════════════════

def parse_bank_csv(filepath: str):
    transactions = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            amount = abs(_clean_number(row.get("amount", "0")))
            if amount == 0:
                continue

            desc = row.get("description", "")
            txn_date = _parse_date(row.get("date", ""))

            t = Transaction(
                amount=amount,
                direction="OUT",
                due_date=txn_date,
                category=_infer_category(desc),
                counterparty_name=_extract_counterparty(desc),
                source_file=filepath,
                raw_text=desc,
            )
            t.compute_derived_fields()
            transactions.append(t)

    return transactions


# ════════════════════════════════════════════════════════════════
#  PDF PARSER
# ════════════════════════════════════════════════════════════════

def parse_bank_pdf(filepath: str):
    transactions = []
    lines = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split("\n"))

    pattern = re.compile(
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)"
    )

    for line in lines:
        match = pattern.search(line)
        if not match:
            continue

        t = Transaction(
            amount=_clean_number(match.group(3)),
            direction="OUT",
            due_date=_parse_date(match.group(1)),
            category=_infer_category(match.group(2)),
            counterparty_name=_extract_counterparty(match.group(2)),
            source_file=filepath,
            raw_text=line,
        )
        t.compute_derived_fields()
        transactions.append(t)

    return transactions


# ════════════════════════════════════════════════════════════════
#  OCR PARSER (ADVANCED)
# ════════════════════════════════════════════════════════════════

def parse_receipt_image(filepath: str):
    transactions = []

    img = Image.open(filepath).convert("L")
    raw_text = pytesseract.image_to_string(img)
    raw_text = _clean_ocr_text(raw_text)

    print(f"\n[OCR TEXT]\n{raw_text}\n")

    amount = _extract_amount_advanced(raw_text)

    if not amount:
        print(f"[ERROR] Amount extraction failed:\n{raw_text}\n")
        return []

    txn_date = _extract_date(raw_text)
    due_date = _extract_due_date(raw_text)

    doc_type = "OBLIGATION" if "due" in raw_text.lower() else "TRANSACTION"

    direction = "OUT" if doc_type == "OBLIGATION" else _infer_direction(raw_text)

    t = Transaction(
        amount=amount,
        direction=direction,
        due_date=due_date,
        category=_infer_category(raw_text),
        counterparty_name=_extract_counterparty(raw_text),
        source_file=filepath,
        raw_text=raw_text,
    )

    t.compute_derived_fields()
    transactions.append(t)

    return transactions


# ════════════════════════════════════════════════════════════════
#  ADVANCED AMOUNT EXTRACTION (KEY FIX)
# ════════════════════════════════════════════════════════════════

def _extract_amount_advanced(text: str) -> Optional[float]:
    text = text.lower()
    text = _normalize_ocr_numbers(text)

    candidates = []

    # ❌ REMOVE LONG IDs
    text = re.sub(r"\b\d{9,}\b", " ", text)

    # ❌ REMOVE TIMES
    text = re.sub(r"\b\d{1,2}:\d{2}\b", " ", text)

    # ❌ REMOVE DATES (CRITICAL FIX)
    text = re.sub(r"\b\d{1,2}\s+[a-z]{3,}\s+\d{4}\b", " ", text)  # 25 mar 2026
    text = re.sub(r"\b\d{4}\b", " ", text)  # standalone years like 2026

    # 🔹 STEP 1: Labeled (BEST)
    for p in [r"(?:amount|paid|debited|credited)\s*[:\-]?\s*₹?\s*([0-9,\.]+)"]:
        for m in re.findall(p, text):
            val = _clean_number(m)
            if 1 <= val <= 1000000:
                return val

    # 🔹 STEP 2: ₹ / Rs
    for p in [r"₹\s*([0-9,\.]+)", r"rs\.?\s*([0-9,\.]+)"]:
        for m in re.findall(p, text):
            val = _clean_number(m)
            if 1 <= val <= 1000000:
                candidates.append((val, 3))

    # 🔹 STEP 3: CONTEXT (KEY)
    words = text.split()

    for i, w in enumerate(words):
        if w.isdigit():
            val = float(w)

            # reject unrealistic
            if val > 50000 or val < 1:
                continue

            context = " ".join(words[max(0, i-3):i+3])

            score = 0
            if "completed" in context or "paid" in context:
                score += 4
            if "to" in context:
                score += 2
            if "upi" in context:
                score += 1

            if score > 0:
                candidates.append((val, score))

    # 🔹 STEP 4: fallback (SAFE)
    for m in re.findall(r"\b\d{2,5}\b", text):
        val = float(m)
        if 1 <= val <= 50000:
            candidates.append((val, 1))

    if not candidates:
        return None

    # 🎯 FINAL: highest score first, then closest to realistic txn range
    candidates.sort(key=lambda x: (x[1], -abs(x[0] - 500)), reverse=True)

    return candidates[0][0]
# ════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════

def _normalize_ocr_numbers(text: str) -> str:
    table = str.maketrans({"O":"0","l":"1","S":"5"})
    return " ".join([t.translate(table) if re.search(r"\d", t) else t for t in text.split()])

def _clean_ocr_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w₹Rs\.\-\s:]", " ", text)
    return text.strip()

def _extract_date(text: str):
    m = re.search(r"\d{1,2}\s+[A-Za-z]+\s+\d{4}", text)
    return dateparser.parse(m.group()).date() if m else None

def _extract_due_date(text: str):
    m = re.search(r"(due on|due date).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", text, re.I)
    return dateparser.parse(m.group(2)).date() if m else None

def _infer_direction(text: str):
    return "IN" if "received" in text.lower() else "OUT"

def _infer_category(text: str):
    text = text.lower()
    if "tax" in text: return "TAX"
    if "rent" in text: return "RENT"
    if "loan" in text: return "LOAN"
    return "OTHER"

def _extract_counterparty(text: str):
    return " ".join(text.split()[:3]).title()

def _clean_number(x: str):
    try:
        return float(x.replace(",", "").replace("₹", "").replace("Rs", ""))
    except:
        return 0.0

def _parse_date(x: str):
    try:
        return dateparser.parse(str(x)).date()
    except:
        return date.today()