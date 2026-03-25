# backend/models.py
# The canonical Transaction object — every module depends on this.
# Never change this schema mid-hackathon without telling your team.

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import hashlib
import json

# ── Category weights (India-specific, research-backed) ──────────
OBLIGATION_WEIGHTS = {
    "TAX":      10.0,   # GST — legal penalty + prosecution
    "SALARY":    9.5,   # Labour Court exposure
    "LOAN":      8.5,   # NPA + credit score damage
    "RENT":      8.0,   # Eviction risk
    "SUPPLIER":  7.0,   # Supply chain break
    "UTILITY":   5.0,   # Disconnection after grace
    "OTHER":     3.0,   # Relationship friction only
}

# ── Flexibility multipliers ──────────────────────────────────────
FLEXIBILITY_MULTIPLIERS = {
    "FIXED":       1.0,   # No negotiation possible
    "NEGOTIABLE":  0.7,   # Some room to discuss
    "DEFERRABLE":  0.4,   # Can be pushed without penalty
}

# ── Default penalty rates by category ───────────────────────────
DEFAULT_PENALTY_RATES = {
    "TAX":      18.0,
    "SALARY":    0.0,   # No financial penalty but high legal risk
    "LOAN":     24.0,   # Typical NBFC rate
    "RENT":      0.0,   # Usually no formal penalty
    "SUPPLIER": 12.0,   # Typical trade credit rate
    "UTILITY":   2.0,
    "OTHER":     0.0,
}

# ── Default flexibility by category ─────────────────────────────
DEFAULT_FLEXIBILITY = {
    "TAX":      "FIXED",
    "SALARY":   "FIXED",
    "LOAN":     "FIXED",
    "RENT":     "NEGOTIABLE",
    "SUPPLIER": "NEGOTIABLE",
    "UTILITY":  "NEGOTIABLE",
    "OTHER":    "DEFERRABLE",
}


@dataclass
class Transaction:
    # ── Core fields (always required) ───────────────────────────
    amount: float
    direction: str                   # "IN" or "OUT"
    due_date: date
    category: str                    # see OBLIGATION_WEIGHTS keys
    counterparty_name: str

    # ── Scoring fields (auto-filled by normaliser if missing) ────
    flexibility: str = ""
    penalty_rate_annual: float = 0.0
    obligation_weight: float = 0.0
    relationship_score: float = 50.0  # default: neutral relationship
    is_recurring: bool = False

    # ── Computed fields (always derived, never set manually) ─────
    penalty_per_day: float = 0.0
    source_hash: str = ""
    source_file: str = ""            # which file this came from
    raw_text: str = ""               # original extracted text (for audit)

    def compute_derived_fields(self):
        """Call this after setting all base fields."""
        # Fill defaults from category if not explicitly set
        if not self.flexibility:
            self.flexibility = DEFAULT_FLEXIBILITY.get(self.category, "NEGOTIABLE")

        if self.penalty_rate_annual == 0.0:
            self.penalty_rate_annual = DEFAULT_PENALTY_RATES.get(self.category, 0.0)

        if self.obligation_weight == 0.0:
            self.obligation_weight = OBLIGATION_WEIGHTS.get(self.category, 3.0)

        # penalty_per_day = (amount × annual_rate%) / 365
        self.penalty_per_day = round(
            (self.amount * self.penalty_rate_annual / 100) / 365, 2
        )

        # SHA-256 hash for deduplication
        # Hash on: amount + counterparty + due_date (not source file)
        hash_input = f"{self.amount}|{self.counterparty_name.lower().strip()}|{self.due_date}"
        self.source_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def to_dict(self):
        return {
            "amount": self.amount,
            "direction": self.direction,
            "due_date": str(self.due_date) if self.due_date else None,
            "category": self.category,
            "counterparty_name": self.counterparty_name,
            "flexibility": self.flexibility,
            "penalty_rate_annual": self.penalty_rate_annual,
            "obligation_weight": self.obligation_weight,
            "relationship_score": self.relationship_score,
            "is_recurring": self.is_recurring,
            "penalty_per_day": self.penalty_per_day,
            "source_hash": self.source_hash,
            "source_file": self.source_file,
        }