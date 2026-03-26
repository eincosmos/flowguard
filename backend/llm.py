# llm.py

import json
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


REASON_MAP = {
    "LEGAL_PRIORITY": "Legal obligation. Delaying risks penalties.",
    "SURVIVAL_PRIORITY": "Critical for business continuity.",
    "OVERDUE_CRITICAL": "Already overdue. Immediate action required.",
    "SAFE_TO_DELAY": "Low risk and flexible.",
    "INSUFFICIENT_FUNDS": "Not enough funds available."
}


class ExplanationEngineProduction:
    def __init__(self, use_llm=True):
        self.use_llm = use_llm
        self.client = None
        self.model = "gpt-4o-mini"
        self.max_observed_risk = 0.0

        if use_llm and OpenAI:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key)
            else:
                self.use_llm = False

    def _normalize_risk(self, score):
        if score > self.max_observed_risk:
            self.max_observed_risk = score

        if self.max_observed_risk == 0:
            return 0

        return min(100, (score / self.max_observed_risk) * 100)

    def _assign_ids(self, decisions):
        for i, d in enumerate(decisions):
            d["_id"] = f"txn_{i}"
        return decisions

    def _fallback(self, d):
        risk = self._normalize_risk(d.get("consequence_score", 0))

        # 🔥 FIX: Critical override
        if d.get("action") == "FLAG_CRITICAL":
            level = "HIGH"
            urgency = "IMMEDIATE"
        elif risk > 70:
            level = "HIGH"
            urgency = "IMMEDIATE"
        elif risk > 40:
            level = "MEDIUM"
            urgency = "SOON"
        else:
            level = "LOW"
            urgency = "LATER"

        reason = REASON_MAP.get(d.get("reasoning_key"), "Priority decision")

        return {
            "_id": d["_id"],
            "explanation": f"{d['action']} ₹{d.get('paid_amount', d['amount'])} to {d['counterparty']}. {reason}",
            "risk_level": level,
            "urgency": urgency
        }

    def _chunk(self, arr, size=5):
        for i in range(0, len(arr), size):
            yield arr[i:i + size]

    def explain_decisions_batch(self, decisions, cash):
        decisions = self._assign_ids(decisions)

        if not decisions:
            return []

        # 🔥 Fallback-first approach (stable for hackathon)
        explanations = [self._fallback(d) for d in decisions]

        exp_map = {e["_id"]: e for e in explanations}

        final = []
        for d in decisions:
            exp = exp_map.get(d["_id"], self._fallback(d))

            merged = {**d}
            merged["human_explanation"] = exp["explanation"]
            merged["risk_level"] = exp["risk_level"]
            merged["urgency"] = exp["urgency"]

            merged.pop("_id", None)
            final.append(merged)

        return final