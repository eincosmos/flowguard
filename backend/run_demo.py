# run_demo.py
"""
Quick Demo Runner
-----------------
Usage: python3 run_demo.py --cash 50000 --buffer 5000
"""

import json
import argparse
from datetime import date
from main import run_pipeline  # Your main pipeline function

def main():
    parser = argparse.ArgumentParser(description="FlowGuard Demo")
    parser.add_argument("--cash", type=float, default=50000, help="Initial cash")
    parser.add_argument("--buffer", type=float, default=5000, help="Buffer reserve")
    parser.add_argument("--data", type=str, default="sample_data/test_obligations.json", help="Input JSON")
    args = parser.parse_args()

    # Load test data
    with open(args.data, 'r') as f:
        obligations = json.load(f)

    # Mock expected inflows (customize as needed)
    inflows = [
        {'amount': 20000, 'date': date(2026, 3, 27)},
        {'amount': 15000, 'date': date(2026, 3, 30)}
    ]

    print(f"💰 Initial Cash: ₹{args.cash} | Buffer: ₹{args.buffer}")
    print(f"📦 Loading {len(obligations)} obligations from {args.data}\n")

    # Run pipeline
    results = run_pipeline(
        obligations,
        initial_cash=args.cash,
        buffer_cash=args.buffer,
        expected_inflows=inflows
    )

    # Print results
    print("\n" + "="*60)
    print("🚀 FINAL DECISIONS")
    print("="*60)
    for r in results:
        action_icon = "🔴" if r.get('action') == 'FLAG_CRITICAL' else "🟢" if r.get('action') == 'PAY' else "🟡"
        print(f"{action_icon} {r.get('counterparty')} | ₹{r.get('amount')} | {r.get('action')}")
        print(f"   💬 {r.get('human_explanation', 'N/A')}")
        print(f"   ⚡ Risk: {r.get('risk_level', 'N/A')} | Urgency: {r.get('urgency', 'N/A')}")
        print("-"*60)

if __name__ == "__main__":
    main()