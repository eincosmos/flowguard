# scorer.py
# Stage 2: Consequence Scoring Engine

from datetime import date
import math


# --- CONFIG CONSTANTS ---

ALPHA = 0.4
BETA = 0.45
GAMMA = 0.15


BASE_RISK_MAP = {
    "GST": 0.02,
    "SALARY": 0.025,
    "LOAN": 0.02,
    "RENT": 0.018,
    "SUPPLIER": 0.015,
    "OTHER": 0.01
}


FLEXIBILITY_MAP = {
    "FIXED": 1.0,
    "NEGOTIABLE": 0.85,
    "DEFERRABLE": 0.7
}


CRITICALITY_MAP = {
    "CRITICAL_SUPPLIER": 2.0,
    "IMPORTANT_SUPPLIER": 1.5,
    "SUPPLIER": 1.2,
    "OTHER": 1.0
}


# --- CORE FUNCTION ---

def compute_consequence_score(txn: dict, today: date = None) -> float:

    if today is None:
        today = date.today()

    # --- Extract ---
    amount = max(txn.get("amount", 0), 0)
    penalty_rate = txn.get("penalty_rate_annual", 0)
    due_date = txn.get("due_date")
    category = txn.get("category", "OTHER")
    flexibility = txn.get("flexibility", "DEFERRABLE")
    relationship_score = txn.get("relationship_score", 50)
    obligation_weight = txn.get("obligation_weight", 5)

    # --- Safety ---
    relationship_score = max(0, min(100, relationship_score))

    # --- LOG-SCALED AMOUNT (KEY FIX) ---
    # prevents large transactions from dominating
    effective_amount = math.log1p(amount)  # log(1 + amount)

    # --- Days Remaining ---
    if not due_date:
        days_remaining = 30
    else:
        days_remaining = (due_date - today).days

    # --- Urgency ---
    if days_remaining <= 0:
        urgency = 2.5
    else:
        urgency = 1 / ((days_remaining + 1) ** 1.3)

    # --- Base Risk ---
    base_risk = BASE_RISK_MAP.get(category, 0.01)

    # --- Flexibility ---
    flexibility_multiplier = FLEXIBILITY_MAP.get(flexibility, 0.7)

    # --- Criticality ---
    criticality_factor = CRITICALITY_MAP.get(category, 1.0)

    # --- Risk Components (using effective_amount) ---
    financial_risk = (effective_amount * penalty_rate)

    operational_risk = effective_amount * base_risk

    relationship_risk = (
        effective_amount *
        ((100 - relationship_score) / 100) ** 2 *
        criticality_factor
    )

    # --- Combine ---
    total_risk = (
        ALPHA * financial_risk +
        BETA * operational_risk +
        GAMMA * relationship_risk
    )

    # --- Final CS ---
    cs = total_risk * urgency * obligation_weight * flexibility_multiplier

    return max(cs, 0.01)


# --- BULK SCORING ---

def score_all(transactions: list, today: date = None) -> list:
    results = []

    for txn in transactions:
        score = compute_consequence_score(txn, today)
        txn["consequence_score"] = score
        results.append(txn)

    return results
    