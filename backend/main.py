from normaliser import normalise_all
from scorer import score_all
from solver import DecisionEngineProduction
from llm import ExplanationEngineProduction
from cash_engine import compute_current_cash, split_transactions

import json


def run_full_pipeline():

    print("🚀 FULL PIPELINE (REAL FLOW)...\n")

    # =============================
    # 🔥 Load INPUT (Stage 0)
    # =============================
    raw = json.load(open("sample_data/test_obligations.json"))

    initial_cash = 50000
    buffer = 5000

    # =============================
    # Stage 1
    # =============================
    print("📥 Stage 1: Normalising...")
    stage1 = normalise_all(raw)
    transactions = stage1["transactions"]

    # Split past vs pending
    past, pending = split_transactions(transactions)

    # =============================
    # 💰 Cash Engine
    # =============================
    available_cash = compute_current_cash(past, initial_cash)
    print(f"💰 Available Cash: {available_cash}")

    # =============================
    # Stage 2
    # =============================
    print("📊 Stage 2: Scoring...")
    pending_out = [
        t for t in pending
        if t.get("direction") == "OUT"
    ]

    scored = score_all(pending_out)

    # =============================
    # Stage 3
    # =============================
    print("⚙️ Stage 3: Decision Engine...")
    solver = DecisionEngineProduction(
        available_cash=available_cash,
        buffer_cash=buffer
    )

    decisions = solver.solve(scored)

    # =============================
    # Stage 4
    # =============================
    print("🧠 Stage 4: Explanation Engine...")
    explainer = ExplanationEngineProduction(
        provider="groq",
        use_llm=True,
        tone="professional",
        batch_size=10
    )

    unified = explainer.explain_decisions_batch(decisions, available_cash)

    summary = explainer.generate_executive_summary(decisions, available_cash)

    # =============================
    # OUTPUT
    # =============================
    print("\n" + "="*50)
    print("📊 FINAL DASHBOARD")
    print("="*50)

    print(f"💡 {summary}\n")

    STATUS_MAP = {
        "FLAG_CRITICAL": "🔴",
        "PAY": "🟢",
        "DEFER": "🟡",
        "NEGOTIATE": "🟠"
    }

    for d in unified:
        status = STATUS_MAP.get(d['action'], "⚪")

        print(f"{status} {d['counterparty']} ({d['action']})")
        print(f"   💬 {d.get('human_explanation', 'N/A')}")
        print(f"   ⚡ Urgency: {d.get('urgency', 'N/A')} | Risk: {d.get('risk_level', 'N/A')}")
        print("-" * 50)

    return unified


if __name__ == "__main__":
    run_full_pipeline()