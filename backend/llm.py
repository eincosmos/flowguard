# llm_v3_production.py
"""
Stage 4: Intelligence Layer (Production Perfect v3)
---------------------------------------------------
Fixes Applied:
1. ✅ Unique ID Matching (No duplicate overwrite)
2. ✅ Chunking System (Unlimited transactions)
3. ✅ Dynamic Risk Normalization (No hardcoded max)
4. ✅ Deep Merge (Decision + Explanation unified)
"""

import json
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import math

load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    print("⚠️ Please install: pip install openai")
    OpenAI = None

# 🔥 1. Reason Map (Grounded Truth)
REASON_MAP = {
    "LEGAL_PRIORITY": "This is a legal obligation (Tax/EMI). Delaying risks penalties or legal action.",
    "SURVIVAL_PRIORITY": "Critical for business continuity (Rent/Salary). Delaying risks operations.",
    "OVERDUE_CRITICAL": "Payment is already late. Immediate action required to stop escalation.",
    "URGENT_HIGH_RISK": "High risk + approaching deadline. Paying now prevents future crisis.",
    "HIGH_IMPACT": "Best risk reduction per rupee spent. High efficiency priority.",
    "SAFE_TO_DELAY": "Low risk + flexible terms. Cash can be preserved for critical items.",
    "RELATIONSHIP_CRITICAL": "Supplier is vital to supply chain. Protecting relationship is key.",
    "CASH_CONSTRAINT": "Decision driven by limited cash. Prioritizing higher risk items.",
    "INSUFFICIENT_FUNDS": "Critical alert: Funds insufficient even after prioritization."
}

# 🔥 2. Tone Profiles
TONE_PROFILES = {
    "strict": "Be direct, factual, and urgent. No fluff.",
    "friendly": "Be supportive, reassuring, but clear about risks.",
    "professional": "Be balanced, objective, and advisory."
}

class ExplanationEngineProduction:
    def __init__(
        self, 
        provider: str = "groq", 
        use_llm: bool = True, 
        tone: str = "professional",
        batch_size: int = 10
    ):
        self.use_llm = use_llm
        self.client = None
        self.model = ""
        self.tone = tone
        self.batch_size = batch_size  # 🔥 Fix 2: Configurable chunk size
        self.max_observed_risk = 1.5  # 🔥 Fix 3: Dynamic tracking
        
        if not use_llm or OpenAI is None:
            return

        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                self.model = "llama-3.1-70b-versatile"
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o-mini"
        
        if not self.client:
            print("⚠️ No API key found. Falling back to Template Engine.")
            self.use_llm = False

    def _normalize_risk(self, score: float) -> float:
        """
        🔥 Fix 3: Dynamic Risk Normalization
        Tracks max observed risk and normalizes accordingly
        """
        # Update max observed
        if score > self.max_observed_risk:
            self.max_observed_risk = score
        
        # Avoid division by zero
        if self.max_observed_risk <= 0:
            return 50.0
        
        # Normalize to 0-100
        normalized = (score / self.max_observed_risk) * 100
        return min(100, max(0, normalized))

    def _filter_outbound(self, decisions: List[Dict]) -> List[Dict]:
        """
        🔥 Fix 2: Only explain OUT transactions (payments)
        """
        return [
            d for d in decisions 
            if d.get("direction", "OUT") == "OUT" 
            or d.get("action") in ["PAY", "DEFER", "NEGOTIATE", "PAY_PARTIAL", "FLAG_CRITICAL"]
        ]

    def _assign_unique_ids(self, decisions: List[Dict]) -> List[Dict]:
        """
        🔥 Fix 1: Assign unique IDs to prevent duplicate matching issues
        """
        for idx, d in enumerate(decisions):
            d['_unique_id'] = f"txn_{idx}_{d.get('counterparty', 'unknown').replace(' ', '_')}"
        return decisions

    def _build_prompt(self, decision: Dict, cash_context: float) -> str:
        reason_key = decision.get('reasoning_key', 'CASH_CONSTRAINT')
        reason_definition = REASON_MAP.get(reason_key, "Prioritized based on risk.")
        
        risk_100 = self._normalize_risk(decision.get('consequence_score', 0))
        tone_instruction = TONE_PROFILES.get(self.tone, TONE_PROFILES["professional"])

        return f"""
        You are a seasoned CFO advising a stressed business owner.
        {tone_instruction}
        
        CONTEXT:
        - Available Cash: ₹{cash_context}
        - Counterparty: {decision['counterparty']}
        - Amount: ₹{decision['amount']}
        - Action: {decision['action']}
        - Technical Reason: {reason_key} ({reason_definition})
        - Risk Score: {risk_100}/100
        
        TASK:
        Explain this decision in 2 sentences max.
        1. Tell them WHAT to do.
        2. Tell them WHY (based on the Technical Reason).
        3. Warn them about the RISK if they ignore this.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "explanation": "String",
            "risk_level": "HIGH | MEDIUM | LOW",
            "urgency": "IMMEDIATE | SOON | LATER"
        }}
        """

    def _get_llm_explanation(self, decision: Dict, cash: float) -> Optional[Dict]:
        try:
            prompt = self._build_prompt(decision, cash)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial advisor. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"⚠️ LLM Error: {e}")
            return None

    def _get_fallback_explanation(self, decision: Dict, cash: float) -> Dict:
        reason_key = decision.get('reasoning_key', 'CASH_CONSTRAINT')
        definition = REASON_MAP.get(reason_key, "Prioritized based on risk.")
        
        action = decision['action']
        counterparty = decision['counterparty']
        amount = decision['amount']
        
        risk_100 = self._normalize_risk(decision.get('consequence_score', 0))

        explanation = f"{action} ₹{amount} to {counterparty}. {definition}"
        
        if risk_100 >= 70:
            risk = "HIGH"
        elif risk_100 >= 40:
            risk = "MEDIUM"
        else:
            risk = "LOW"
            
        urgency = "IMMEDIATE" if action == "PAY" else ("SOON" if action == "NEGOTIATE" else "LATER")

        return {
            "explanation": explanation,
            "risk_level": risk,
            "urgency": urgency
        }

    def _chunk_list(self, items: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        🔥 Fix 2: Chunking helper for batch processing
        """
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    def explain_decisions_batch(self, decisions: List[Dict], cash: float) -> List[Dict]:
        """
        🔥 Fix 1, 2, 4: Batch + Chunking + Unique ID + Deep Merge
        """
        # 🔥 Fix 1: Assign unique IDs
        decisions = self._assign_unique_ids(decisions)
        
        # 🔥 Fix 2: Filter outbound
        filtered = self._filter_outbound(decisions)
        
        if not filtered:
            return []
        
        if not self.use_llm or not self.client:
            explanations = [self._get_fallback_explanation(d, cash) for d in filtered]
        else:
            # 🔥 Fix 2: Chunk processing for unlimited transactions
            chunks = self._chunk_list(filtered, self.batch_size)
            all_explanations = []
            
            for chunk in chunks:
                chunk_explanations = self._process_batch_chunk(chunk, cash)
                all_explanations.extend(chunk_explanations)
            
            explanations = all_explanations
        
        # 🔥 Fix 4: Deep Merge - Return unified objects
        return self._deep_merge_explanations(filtered, explanations)

    def _process_batch_chunk(self, chunk: List[Dict], cash: float) -> List[Dict]:
        """
        Process a single chunk of decisions
        """
        try:
            items = []
            for d in chunk:
                risk_100 = self._normalize_risk(d.get('consequence_score', 0))
                items.append(f"""
                - ID: {d['_unique_id']} | {d['counterparty']} | ₹{d['amount']} | {d['action']} | 
                  Reason: {d.get('reasoning_key', 'UNKNOWN')} | Risk: {risk_100}/100
                """)
            
            tone_instruction = TONE_PROFILES.get(self.tone, TONE_PROFILES["professional"])
            
            batch_prompt = f"""
            You are a seasoned CFO. {tone_instruction}
            
            CASH AVAILABLE: ₹{cash}
            
            PAYMENT DECISIONS:
            {chr(10).join(items)}
            
            For EACH decision, provide:
            1. One sentence explanation
            2. Risk level (HIGH/MEDIUM/LOW)
            3. Urgency (IMMEDIATE/SOON/LATER)
            
            OUTPUT FORMAT (JSON ONLY):
            {{
                "explanations": [
                    {{
                        "_unique_id": "...",
                        "explanation": "...",
                        "risk_level": "...",
                        "urgency": "..."
                    }}
                ]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial advisor. Output ONLY valid JSON."},
                    {"role": "user", "content": batch_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Map by unique ID (🔥 Fix 1: No duplicate overwrite)
            explanations_map = {e['_unique_id']: e for e in result.get('explanations', [])}
            
            output = []
            for d in chunk:
                uid = d['_unique_id']
                if uid in explanations_map:
                    output.append(explanations_map[uid])
                else:
                    output.append(self._get_fallback_explanation(d, cash))
            
            return output
            
        except Exception as e:
            print(f"⚠️ Batch Chunk Error: {e}")
            return [self._get_fallback_explanation(d, cash) for d in chunk]

    def _deep_merge_explanations(self, decisions: List[Dict], explanations: List[Dict]) -> List[Dict]:
        """
        🔥 Fix 4: Deep Merge - Decision + Explanation unified
        Returns complete objects with all fields
        """
        merged = []
        for i, d in enumerate(decisions):
            # Create copy to avoid mutating original
            unified = {**d}
            
            if i < len(explanations):
                exp = explanations[i]
                unified['human_explanation'] = exp.get('explanation', '')
                unified['risk_level'] = exp.get('risk_level', 'MEDIUM')
                unified['urgency'] = exp.get('urgency', 'SOON')
            
            # Remove internal tracking fields
            unified.pop('_unique_id', None)
            
            merged.append(unified)
        
        return merged

    def explain_decision(self, decision: Dict, cash: float) -> Dict:
        """Single decision (backward compatible)"""
        if self.use_llm and self.client:
            result = self._get_llm_explanation(decision, cash)
            if result:
                return {**decision, **result}
        return {**decision, **self._get_fallback_explanation(decision, cash)}

    def generate_executive_summary(self, decisions: List[Dict], cash: float) -> str:
        """
        🔥 Strategic Executive Summary
        """
        pay_count = sum(1 for d in decisions if d['action'] == 'PAY')
        critical_count = sum(1 for d in decisions if d['action'] == 'FLAG_CRITICAL')
        defer_count = sum(1 for d in decisions if d['action'] == 'DEFER')
        
        sorted_by_risk = sorted(
            decisions, 
            key=lambda x: self._normalize_risk(x.get('consequence_score', 0)), 
            reverse=True
        )[:2]
        
        top_risks = [f"{d['counterparty']} (₹{d['amount']})" for d in sorted_by_risk]
        
        if not self.use_llm or not self.client:
            return f"Summary: Pay {pay_count} items. {critical_count} critical. {defer_count} deferred."

        try:
            prompt = f"""
            You are a CFO summarizing financial position.
            
            DATA:
            - Cash: ₹{cash}
            - Actions: {pay_count} Pay, {critical_count} Critical, {defer_count} Deferred
            - Top Risks: {', '.join(top_risks)}
            
            Summarize in 1 sentence covering:
            1. Financial position
            2. Immediate action needed
            3. Risk outlook
            
            Be direct and actionable.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Summary: Pay {pay_count} items. {critical_count} critical. {defer_count} deferred."
