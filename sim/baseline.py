"""Run one seeded collections pass with LLM or explicit offline mode."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import neatlogs

from agents.baseline import BudgetExceeded, LLM
from sim.ledger import AS_OF, SEED, generate_ledger
from sim.payer import PayerSimulator

ROOT = Path(__file__).resolve().parents[1]
RUN_RECORD = ROOT / "state" / "last_run.json"
RUN_LEDGER = ROOT / "state" / "llm_baseline_ledger.json"


def run(offline: bool = False) -> dict:
    trace_key = os.getenv("NEATLOGS_API_KEY")
    if not trace_key:
        raise RuntimeError("NEATLOGS_API_KEY is required; refusing to run without an exported Neatlogs trace")
    neatlogs.init(api_key=trace_key, workflow_name="chaser-baseline")
    invoices = generate_ledger(seed=int(os.getenv("CHASER_SEED", SEED)), as_of=AS_OF)
    simulator = PayerSimulator(seed=int(os.getenv("CHASER_SEED", SEED)), as_of=AS_OF)
    llm = LLM(offline=offline)
    now = datetime.now(timezone.utc).isoformat()
    total_calls = 0
    trace_id = None
    error = None
    with neatlogs.trace("chaser-baseline-run", kind="WORKFLOW") as root_span:
        for invoice in invoices:
            per_invoice = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0, "cache_hits": 0}
            try:
                message = llm.draft(invoice, per_invoice, offline=offline)
                invoice["history"].append({"at": now, "type": "message_sent", "text": message})
                neatlogs.log("sent reminder for {invoice_id} at stage {stage}", invoice_id=invoice["id"], stage=invoice["stage"])

                simulated = simulator.reply(invoice, message)
                classified = llm.classify(simulated["text"], invoice, per_invoice, offline=offline)
                invoice["history"].append({"at": now, "type": "payer_reply", "text": simulated["text"], "classification": classified})
                intent = classified["intent"]
                if intent == "paid":
                    amount = classified["amount_mentioned"]
                    if amount is not None and 0 < amount < invoice["amount"]:
                        invoice["status"] = "partial"
                        invoice["history"].append({"at": now, "type": "partial_payment", "amount": int(amount), "currency": invoice["currency"]})
                    else:
                        invoice["status"] = "paid"
                elif intent == "promise":
                    invoice["status"] = "promised"
                    invoice["history"].append({"at": now, "type": "payment_promise", "date": classified["promised_date"]})
                elif intent == "dispute":
                    invoice["status"] = "disputed"
                elif intent == "info_request":
                    invoice["stage"] = min(3, invoice["stage"] + 1)
                per_invoice["status"] = invoice["status"]
                neatlogs.log(
                    "classified payer reply for {invoice_id} as {intent}",
                    invoice_id=invoice["id"], intent=intent,
                    invoice_cost_usd=round(per_invoice["cost_usd"], 8),
                    input_tokens=per_invoice["input_tokens"], output_tokens=per_invoice["output_tokens"],
                )
            except ValueError as exc:
                invoice["review_required"] = True
                invoice["history"].append({"at": now, "type": "human_review", "reason": str(exc)})
                per_invoice["status"] = "human_review"
            except BudgetExceeded as exc:
                error = str(exc)
                invoice["history"].append({"at": now, "type": "budget_stop", "reason": error})
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                invoice["history"].append({"at": now, "type": "run_error", "reason": error})
                break
            finally:
                total_calls += per_invoice["calls"]
                invoice["llm_usage"] = per_invoice
        trace_id = f"{root_span.get_span_context().trace_id:032x}"

    paid = [inv for inv in invoices if inv["status"] == "paid"]
    partial = [entry for inv in invoices for entry in inv["history"] if entry.get("type") == "partial_payment"]
    recovered = sum(inv["amount"] for inv in paid) + sum(entry["amount"] for entry in partial)
    run_cost = sum(inv.get("llm_usage", {}).get("cost_usd", 0.0) for inv in invoices)
    trace_link = f"https://neatlogs.com/traces/{trace_id}"
    result = {
        "run_at": now,
        "seed": int(os.getenv("CHASER_SEED", SEED)),
        "invoices_total": len(invoices),
        "resolved_invoices": len(paid),
        "recovered_ngn": recovered,
        "llm_calls": total_calls,
        "input_tokens": sum(inv.get("llm_usage", {}).get("input_tokens", 0) for inv in invoices),
        "output_tokens": sum(inv.get("llm_usage", {}).get("output_tokens", 0) for inv in invoices),
        "estimated_cost_usd": round(run_cost, 8),
        "cost_per_invoice_usd": round(run_cost / len(invoices), 8) if invoices else 0,
        "per_invoice": {inv["id"]: inv.get("llm_usage", {}) for inv in invoices},
        "trace_id": trace_id,
        "trace_link": trace_link,
        "offline": offline,
        "error": error,
    }
    RUN_LEDGER.write_text(json.dumps(invoices, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RUN_RECORD.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if offline:
        (ROOT / "state" / "offline_baseline.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    else:
        (ROOT / "state" / "llm_baseline.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    neatlogs.flush()
    neatlogs.shutdown()
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="use template drafting and deterministic local reply parsing")
    args = parser.parse_args()
    run(offline=args.offline)
