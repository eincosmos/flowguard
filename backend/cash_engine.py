def compute_current_cash(transactions, initial_cash):
    """
    Computes available cash based on past transactions only
    """
    cash = initial_cash

    for txn in transactions:
        status = txn.get("status", "PENDING")

        if status != "PAST":
            continue

        amount = txn.get("amount", 0)
        direction = txn.get("direction")

        # --- Safety checks ---
        if direction not in ("IN", "OUT"):
            # skip invalid transaction
            continue

        if amount < 0:
            continue

        # --- Apply transaction ---
        if direction == "IN":
            cash += amount
        else:  # OUT
            cash -= amount

    return cash


# ----------------------------------------
# Helper: Split transactions
# ----------------------------------------

def split_transactions(transactions):
    """
    Splits transactions into past and pending
    """
    past = []
    pending = []

    for txn in transactions:
        status = txn.get("status", "PENDING")

        if status == "PAST":
            past.append(txn)
        else:
            pending.append(txn)

    return past, pending