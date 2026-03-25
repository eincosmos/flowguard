from normaliser import normalise_all
from scorer import score_all
from solver import DecisionEngineProduction
from cash_engine import compute_current_cash, split_transactions


def run_pipeline(inputs, initial_cash, buffer_cash=0, expected_inflows=None):

    # Stage 1
    stage1 = normalise_all(inputs)
    transactions = stage1["transactions"]

    # Split
    past, pending = split_transactions(transactions)

    # 💰 Cash Engine
    available_cash = compute_current_cash(past, initial_cash)

    print("💰 Available Cash:", available_cash)

    # Stage 2
    # 🔥 filter ONLY payable obligations
    pending_out = [
        t for t in pending
        if t.get("direction") == "OUT"
    ]

    scored = score_all(pending_out)

    # Stage 3
    solver = DecisionEngineProduction(
        available_cash=available_cash,
        buffer_cash=buffer_cash,
        expected_inflows=expected_inflows
    )

    decisions = solver.solve(scored)

    return decisions