# main.py

import argparse
from datetime import date, datetime
from input_loader import InputLoader
from solver import DecisionEngineProduction
from llm import ExplanationEngineProduction


def run_pipeline(
    obligations: list,
    initial_cash: float,
    buffer_cash: float = 5000,
    expected_inflows: list = None
):
    """Core pipeline: Stage 2 → 3 → 4"""

    expected_inflows = expected_inflows or []

    # 🔥 Normalize schema
    for txn in obligations:
        if 'counterparty' not in txn and 'counterparty_name' in txn:
            txn['counterparty'] = txn['counterparty_name']
        if 'counterparty_name' not in txn and 'counterparty' in txn:
            txn['counterparty_name'] = txn['counterparty']

        # Normalize category
        if txn.get("category") == "TAX":
            txn["category"] = "GST"

    print(f"💰 Cash: ₹{initial_cash} | Buffer: ₹{buffer_cash}")
    print(f"📦 Processing {len(obligations)} obligations\n")

    # 🔥 SPLIT INFLOW / OUTFLOW (CRITICAL FIX)
    outgoing = []
    incoming = []

    for txn in obligations:
        if txn.get("category") == "INCOME" or txn.get("direction") == "IN":
            incoming.append(txn)
        else:
            outgoing.append(txn)

    # 🔥 Convert incoming → expected inflows
    for txn in incoming:
        due_date = txn.get("due_date")
        if isinstance(due_date, str):
            try:
                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
            except:
                continue

        if due_date:
            expected_inflows.append({
                "amount": txn["amount"],
                "date": due_date
            })

    # 🔥 Stage 2: Risk Scoring (only outgoing)
    for txn in outgoing:
        if 'consequence_score' not in txn:
            if txn.get('category') in ['GST', 'TAX', 'LOAN']:
                txn['consequence_score'] = 0.9
            elif txn.get('category') in ['RENT', 'SALARY']:
                txn['consequence_score'] = 0.75
            else:
                txn['consequence_score'] = 0.4

        if 'relationship_score' not in txn:
            txn['relationship_score'] = 50

        if 'flexibility' not in txn:
            txn['flexibility'] = "NONE" if txn.get('category') == 'GST' else "DEFERRABLE"

    # 🔥 Stage 3: Decision Engine
    print("⚙️ Stage 3: Computing decisions...")
    solver = DecisionEngineProduction(
        available_cash=initial_cash,
        buffer_cash=buffer_cash,
        expected_inflows=expected_inflows
    )

    decisions = solver.solve(outgoing)

    # 🔥 Stage 4: Explanation Engine
    print("🧠 Stage 4: Generating explanations...")
    explainer = ExplanationEngineProduction(use_llm=True)

    try:
        results = explainer.explain_decisions_batch(decisions, initial_cash)
    except Exception:
        print("⚠️ LLM failed — using fallback")
        explainer = ExplanationEngineProduction(use_llm=False)
        results = explainer.explain_decisions_batch(decisions, initial_cash)

    return results, incoming


def main():
    parser = argparse.ArgumentParser(description="🛡️ FlowGuard: AI CFO for MSMEs")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--json", type=str)
    input_group.add_argument("--text", type=str)
    input_group.add_argument("--ocr", type=str)

    parser.add_argument("--cash", type=float, required=True)
    parser.add_argument("--buffer", type=float, default=5000)
    parser.add_argument("--demo", action="store_true")

    args = parser.parse_args()

    # Load input
    if args.json:
        obligations = InputLoader.load(args.json, source_type="json")
    elif args.text:
        result = InputLoader.load(args.text, source_type="text")
        obligations = [result] if result else []
    elif args.ocr:
        obligations = InputLoader.load(args.ocr, source_type="ocr")
    else:
        obligations = []

    if not obligations:
        print("❌ No valid obligations loaded.")
        return

    inflows = []
    if args.demo:
        inflows = [
            {'amount': 20000, 'date': date(2026, 3, 27)},
            {'amount': 15000, 'date': date(2026, 3, 30)}
        ]
        print("🎬 Demo mode: Added expected inflows")

    # Run pipeline
    results, incoming = run_pipeline(
        obligations,
        initial_cash=args.cash,
        buffer_cash=args.buffer,
        expected_inflows=inflows
    )

    # 🔥 PRINT INFLOWS
    if incoming:
        print("\n💰 EXPECTED INFLOWS")
        print("=" * 50)
        for i in incoming:
            print(f"🟢 {i['counterparty']} → ₹{i['amount']:,.0f} on {i['due_date']}")
        print("=" * 50)

    # Dashboard
    print("\n" + "=" * 70)
    print("📊 FLOWGUARD DECISION DASHBOARD")
    print("=" * 70)

    for r in results:
        icon = (
            "🔴" if r.get('action') == 'FLAG_CRITICAL'
            else "🟢" if r.get('action') == 'PAY'
            else "🟡"
        )

        amount_display = r.get("paid_amount", r["amount"])

        print(f"{icon} {r.get('counterparty')} | ₹{amount_display:,.0f} | {r.get('action')}")
        print(f"   💬 {r.get('human_explanation', 'N/A')}")
        print(f"   ⚡ Risk: {r.get('risk_level')} | Urgency: {r.get('urgency')}")
        print("-" * 70)


if __name__ == "__main__":
    main()