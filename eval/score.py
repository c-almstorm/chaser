"""Print a comparable score for any saved baseline run."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def score(path: Path = ROOT / "state" / "last_run.json") -> dict:
    run = json.loads(path.read_text(encoding="utf-8"))
    total = int(run.get("invoices_total", 0))
    recovered = int(run.get("recovered_ngn", 0))
    cost = float(run.get("estimated_cost_usd", 0.0))
    result = {
        "invoices_resolved": int(run.get("resolved_invoices", 0)),
        "amount_recovered_ngn": recovered,
        "cost_per_invoice_usd": round(cost / total, 8) if total else 0.0,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_record", nargs="?", type=Path, default=ROOT / "state" / "last_run.json")
    score(parser.parse_args().run_record)
