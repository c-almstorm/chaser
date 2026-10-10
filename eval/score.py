"""Report the baseline's resolution, recovery, and per-invoice cost."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def score() -> dict:
    invoices = json.loads((ROOT / "data" / "ledger.json").read_text(encoding="utf-8"))
    run_path = ROOT / "state" / "last_run.json"
    run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else {}
    paid = [invoice for invoice in invoices if invoice["status"] == "paid"]
    partial = [event for inv in invoices for event in inv["history"] if event.get("type") == "partial_payment"]
    amount = sum(invoice["amount"] for invoice in paid) + sum(event["amount"] for event in partial)
    cost = float(run.get("estimated_cost_usd", 0.0))
    result = {
        "invoices_resolved": len(paid),
        "total_amount_recovered": f"NGN {amount:,}",
        "cost_per_invoice_usd": round(cost / len(invoices), 6) if invoices else 0,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    score()
