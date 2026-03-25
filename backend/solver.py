# solver_v3_production.py
"""
Stage 3: Decision Engine (Production-Ready v3)
----------------------------------------------
Incorporates:
1. Score Normalization (0-100 internal standard)
2. Dynamic Overdue Boost (No magic numbers)
3. Cumulative Inflow Logic (Realistic cash forecasting)
4. Relationship Weighting (Signal utilization)
"""

import math
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Action(Enum):
    PAY = "PAY"
    DEFER = "DEFER"
    NEGOTIATE = "NEGOTIATE"
    PAY_PARTIAL = "PAY_PARTIAL"
    FLAG_CRITICAL = "FLAG_CRITICAL"

class ReasonKey(Enum):
    URGENT_HIGH_RISK = "URGENT_HIGH_RISK"
    HIGH_IMPACT = "HIGH_IMPACT"
    SAFE_TO_DELAY = "SAFE_TO_DELAY"
    CASH_CONSTRAINT = "CASH_CONSTRAINT"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    RELATIONSHIP_CRITICAL = "RELATIONSHIP_CRITICAL"
    LEGAL_PRIORITY = "LEGAL_PRIORITY"
    SURVIVAL_PRIORITY = "SURVIVAL_PRIORITY"
    OVERDUE_CRITICAL = "OVERDUE_CRITICAL"

class DecisionEngineProduction:
    def __init__(self, available_cash: float, buffer_cash: float = 0.0, expected_inflows: List[Dict] = None):
        self.total_budget = available_cash
        self.available_cash = available_cash
        self.buffer_cash = buffer_cash
        self.expected_inflows = expected_inflows or []
        
        # Hierarchy Weights (Multipliers)
        self.hierarchy_weights = {
            "LEGAL": 2.0,          
            "SURVIVAL": 1.5,       
            "CRITICAL_SUPPLIER": 1.2,
            "OTHER": 1.0
        }

    def _normalize_score(self, score: float, min_val: float = 0.0, max_val: float = 1.5) -> float:
        """
        🔥 Fix 1: Normalize Stage 2 output (0-1.5) to Internal Standard (0-100)
        """
        if max_val == min_val:
            return 50.0
        normalized = ((score - min_val) / (max_val - min_val)) * 100
        return max(0, min(100, normalized))

    def _calculate_efficiency(self, amount: float, consequence_100: float) -> float:
        """
        🔥 Efficiency: Risk Reduction per Rupee (Log-Scaled)
        """
        if amount <= 0:
            return consequence_100 * 1000
        return consequence_100 / math.log1p(amount)

    def _get_hierarchy_weight(self, category: str) -> float:
        category_upper = category.upper()
        if any(x in category_upper for x in ["TAX", "GST", "LEGAL", "EMI", "LOAN"]):
            return self.hierarchy_weights["LEGAL"]
        elif any(x in category_upper for x in ["SALARY", "RENT", "UTILITIES"]):
            return self.hierarchy_weights["SURVIVAL"]
        elif any(x in category_upper for x in ["CRITICAL", "KEY"]):
            return self.hierarchy_weights["CRITICAL_SUPPLIER"]
        return self.hierarchy_weights["OTHER"]

    def _check_inflow_coverage(self, due_date: date, amount: float) -> bool:
        """
        🔥 Fix 3: Cumulative Inflow Logic
        Checks if SUM of all inflows before due_date covers the amount.
        """
        if not due_date:
            return False
        
        total_inflow = sum(
            i['amount'] for i in self.expected_inflows
            if isinstance(i.get('date'), date) and i['date'] <= due_date
        )
        return total_inflow >= amount

    def _generate_reasoning(self, txn: Dict, action: Action, is_overdue: bool, consequence_100: float) -> str:
        days_due = (txn.get('due_date') - date.today()).days if isinstance(txn.get('due_date'), date) else 0
        flexibility = txn.get('flexibility', 'NONE')
        relationship = txn.get('relationship_score', 0) # Expected 0-100

        if is_overdue:
            return ReasonKey.OVERDUE_CRITICAL.value
        
        if action == Action.FLAG_CRITICAL:
            return ReasonKey.INSUFFICIENT_FUNDS.value
        
        h_weight = self._get_hierarchy_weight(txn.get('category', ''))
        if h_weight >= 2.0 and action == Action.PAY:
            return ReasonKey.LEGAL_PRIORITY.value
        elif h_weight >= 1.5 and action == Action.PAY:
            return ReasonKey.SURVIVAL_PRIORITY.value

        if consequence_100 > 80 and days_due <= 7:
            return ReasonKey.URGENT_HIGH_RISK.value
        
        if relationship > 90 and action == Action.PAY:
            return ReasonKey.RELATIONSHIP_CRITICAL.value
            
        if action == Action.DEFER and flexibility in ['DEFERRABLE', 'NEGOTIABLE']:
            return ReasonKey.SAFE_TO_DELAY.value
            
        if action == Action.PAY:
            return ReasonKey.HIGH_IMPACT.value

        return ReasonKey.CASH_CONSTRAINT.value

    def solve(self, transactions: List[Dict]) -> List[Dict]:
        decisions = []
        today = date.today()
        
        # 1. Enrich Transactions
        enriched_txns = []
        for txn in transactions:
            amount = txn.get('amount', 1.0)
            raw_consequence = txn.get('consequence_score', 0.0)
            
            # 🔥 Fix 1: Normalize Consequence to 0-100
            consequence_100 = self._normalize_score(raw_consequence)
            
            h_weight = self._get_hierarchy_weight(txn.get('category', ''))
            efficiency = self._calculate_efficiency(amount, consequence_100)
            
            # 🔥 Fix 4: Relationship Weighting (Signal Utilization)
            relationship = txn.get('relationship_score', 0) # Assume 0-100
            relationship_bonus = (relationship / 100) * 2
            
            # 🔥 Fix 2: Dynamic Overdue Boost
            days_due = (txn.get('due_date') - today).days if isinstance(txn.get('due_date'), date) else 999
            is_overdue = days_due <= 0
            overdue_boost = max(consequence_100 * 5, 100) if is_overdue else 0
            
            # Composite Score
            composite_score = (h_weight * consequence_100) + efficiency + relationship_bonus + overdue_boost
            
            #Priority
            # 🔥 HARD PRIORITY OVERRIDE (Option B)
            category = txn.get("category", "").upper()

            if any(x in category for x in ["GST", "TAX"]):
                composite_score += 1000   # force top priority

            elif any(x in category for x in ["LOAN", "EMI"]):
                composite_score += 800    # financial commitments

            elif any(x in category for x in ["SALARY"]):
                composite_score += 700    # survival

            elif any(x in category for x in ["RENT"]):
                composite_score += 600    # operational survival

            enriched_txns.append({
                **txn,
                'efficiency': efficiency,
                'hierarchy_weight': h_weight,
                'composite_score': composite_score,
                'is_overdue': is_overdue,
                'days_due': days_due,
                'consequence_100': consequence_100
            })

        # 2. Sort
        enriched_txns.sort(key=lambda x: (
            -x['composite_score'], 
            x.get('due_date', date.max), 
            x.get('amount', 0)
        ))

        # 3. Allocation Loop
        for idx, txn in enumerate(enriched_txns):
            amount = txn['amount']
            flexibility = txn.get('flexibility', 'NONE')
            due_date = txn.get('due_date')
            is_overdue = txn['is_overdue']
            consequence_100 = txn['consequence_100']
            
            action = None
            reason = None
            remaining_cash = self.available_cash

            usable_cash = self.available_cash - self.buffer_cash
            can_pay_full = usable_cash >= amount
            
            if can_pay_full:
                action = Action.PAY
                self.available_cash -= amount
                remaining_cash = self.available_cash
            else:
                if self._check_inflow_coverage(due_date, amount):
                    action = Action.DEFER
                    reason = ReasonKey.SAFE_TO_DELAY.value
                elif flexibility == "NEGOTIABLE":
                    action = Action.NEGOTIATE
                elif flexibility == "DEFERRABLE":
                    action = Action.DEFER
                elif self.available_cash > 0:
                    action = Action.PAY_PARTIAL
                    self.available_cash = 0
                    remaining_cash = 0
                else:
                    action = Action.FLAG_CRITICAL
                    remaining_cash = self.available_cash

            if not reason:
                reason = self._generate_reasoning(txn, action, is_overdue, consequence_100)

            decision = {
                "priority_rank": idx + 1,
                "counterparty": txn.get('counterparty_name', 'Unknown'),
                "amount": amount,
                "action": action.value,
                "consequence_score": round(consequence_100, 2), # Output normalized score
                "efficiency_score": round(txn['efficiency'], 4),
                "reasoning_key": reason,
                "remaining_cash": round(remaining_cash, 2),
                "confidence": 0.95 if action == Action.PAY else 0.80,
                "is_overdue": is_overdue
            }
            
            decisions.append(decision)

        return decisions

# ==========================================
# READY FOR STAGE 4
# ==========================================
if __name__ == "__main__":
    print("✅ Solver v3 Production Ready.")
    print("🚀 Next Step: Build Stage 4 (Explanation Engine / UI)")