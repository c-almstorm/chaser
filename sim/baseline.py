"""Run one complete pass of the single-agent collections baseline."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import neatlogs

from agents.baseline import draft_message, format_message
from sim.payer import PayerSimulator

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "ledger.json"
RUN_RECORD = ROOT / "state" / "last_run.json"


def run() -> dict:
    neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="chaser-baseline")
    invoices = json.loads(LEDGER.read_text(encoding="utf-8"))
    simulator = PayerSimulator(seed=42)
    now = datetime.now(timezone.utc).isoformat()
    llm_calls = 0

    with neatlogs.trace("chaser-baseline-run", kind="WORKFLOW"):
        misses_before = draft_message.cache_info().misses
        for invoice in invoices:
            if invoice["status"] != "open":
                continue
            message = format_message(invoice)
            invoice["history"].append({"at": now, "type": "message_sent", "text": message})
            neatlogs.log("sent reminder for {invoice_id} at stage {stage}", invoice_id=invoice["id"], stage=invoice["stage"])

            reply = simulator.reply(invoice, message)
            invoice["history"].append({"at": now, "type": "payer_reply", **reply})
            if reply["type"] == "paid":
                invoice["status"] = "paid"
            elif reply["type"] == "promise":
                invoice["status"] = "promised"
                invoice["history"].append({"at": now, "type": "payment_promise", "date": reply["date"]})
            elif reply["type"] == "dispute":
                invoice["status"] = "disputed"
            elif reply["type"] == "partial":
                invoice["status"] = "partial"
                invoice["history"].append({"at": now, "type": "partial_payment", "amount": reply["amount"], "currency": invoice["currency"]})
            elif reply["type"] == "statement":
                invoice["stage"] = min(3, invoice["stage"] + 1)
            neatlogs.log("payer outcome for {invoice_id}: {outcome}", invoice_id=invoice["id"], outcome=reply["type"])
        llm_calls = draft_message.cache_info().misses - misses_before if os.getenv("LITELLM_API_KEY") else 0

    LEDGER.write_text(json.dumps(invoices, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paid = [inv for inv in invoices if inv["status"] == "paid"]
    partial = [entry for inv in invoices for entry in inv["history"] if entry.get("type") == "partial_payment"]
    recovered = sum(inv["amount"] for inv in paid) + sum(entry["amount"] for entry in partial)
    result = {
        "run_at": now,
        "invoices_total": len(invoices),
        "resolved_invoices": len(paid),
        "recovered_ngn": recovered,
        "llm_calls": llm_calls,
        "estimated_cost_usd": 0.0,
        "trace_link": None,
    }
    RUN_RECORD.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    neatlogs.flush()
    neatlogs.shutdown()
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
