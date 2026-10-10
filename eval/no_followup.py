"""Seeded zero-contact control: no outbound message and no payer response."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import neatlogs

from sim.ledger import AS_OF, SEED, generate_ledger
from sim.payer import PayerSimulator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "no_followup.json"


def run() -> dict:
    key = os.getenv("NEATLOGS_API_KEY")
    if not key:
        raise RuntimeError("NEATLOGS_API_KEY is required; refusing to run without an exported Neatlogs trace")
    neatlogs.init(api_key=key, workflow_name="chaser-no-followup")
    seed = int(os.getenv("CHASER_SEED", SEED))
    invoices = generate_ledger(seed=seed, as_of=AS_OF)
    _simulator = PayerSimulator(seed=seed, as_of=AS_OF)
    with neatlogs.trace("chaser-no-followup-run", kind="WORKFLOW") as root:
        neatlogs.log("no-follow-up control; outbound messages {count}", count=0)
        trace_id = f"{root.get_span_context().trace_id:032x}"
    result = {
        "seed": seed,
        "invoices_total": len(invoices),
        "resolved_invoices": 0,
        "recovered_ngn": 0,
        "llm_calls": 0,
        "estimated_cost_usd": 0.0,
        "cost_per_invoice_usd": 0.0,
        "trace_id": trace_id,
        "trace_link": f"https://app.neatlogs.com/traces/{trace_id}",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    neatlogs.flush()
    neatlogs.shutdown()
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
