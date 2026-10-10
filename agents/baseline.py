"""LLM drafting and strict, cached reply classification."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "state" / "llm_cache.json"
BUDGET_USD = 12.0
INTENTS = {"promise", "dispute", "info_request", "paid", "silent"}


def _rate(env_name: str, default: str) -> float:
    return float(os.getenv(env_name, default)) / 1_000_000


class BudgetExceeded(RuntimeError):
    pass


class LLM:
    """LiteLLM client with a disk prompt cache and per-request cost metering."""

    def __init__(self, offline: bool = False):
        self.offline = offline
        if offline:
            self.client = None
        else:
            key = os.getenv("LITELLM_API_KEY")
            if not key:
                raise RuntimeError("LITELLM_API_KEY is required unless --offline is set")
            client = OpenAI(
                api_key=key,
                base_url=os.getenv("LITELLM_BASE_URL", "https://litellm.ai/neatlogs/v1"),
            )
            try:
                import neatlogs
                self.client = neatlogs.wrap(client)
            except Exception:
                self.client = client
        self.cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
        self.run_cost = 0.0

    def _complete(self, role: str, messages: list[dict], max_tokens: int, invoice_cost: dict) -> tuple[str, dict]:
        if self.offline:
            raise RuntimeError("Offline mode does not make completion calls")
        model = os.getenv(
            "LITELLM_DRAFT_MODEL" if role == "draft" else "LITELLM_CLASSIFY_MODEL",
            "anthropic/claude-3-5-sonnet-latest" if role == "draft" else "anthropic/claude-3-5-haiku-latest",
        )
        key = hashlib.sha256(json.dumps([model, messages], sort_keys=True).encode()).hexdigest()
        if key in self.cache:
            cached = self.cache[key]
            usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "cached": True}
            invoice_cost["cache_hits"] += 1
            return cached["text"], usage

        input_rate = _rate("LITELLM_DRAFT_INPUT_USD_PER_1M" if role == "draft" else "LITELLM_CLASSIFY_INPUT_USD_PER_1M", "3" if role == "draft" else "0.8")
        output_rate = _rate("LITELLM_DRAFT_OUTPUT_USD_PER_1M" if role == "draft" else "LITELLM_CLASSIFY_OUTPUT_USD_PER_1M", "15" if role == "draft" else "4")
        input_estimate = max(1, len(json.dumps(messages)) // 3)
        reserve = input_estimate * input_rate + max_tokens * output_rate
        if self.run_cost + reserve > BUDGET_USD:
            raise BudgetExceeded(f"Request would exceed the $12.00 run budget (spent ${self.run_cost:.4f})")

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        input_tokens = int(response.usage.prompt_tokens if response.usage else input_estimate)
        output_tokens = int(response.usage.completion_tokens if response.usage else max_tokens)
        cost = input_tokens * input_rate + output_tokens * output_rate
        if self.run_cost + cost > BUDGET_USD:
            raise BudgetExceeded("Actual completion cost crossed the $12.00 run budget; stopping immediately")
        self.run_cost += cost
        usage = {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost, "cached": False}
        invoice_cost["calls"] += 1
        invoice_cost["input_tokens"] += input_tokens
        invoice_cost["output_tokens"] += output_tokens
        invoice_cost["cost_usd"] += cost
        self.cache[key] = {"text": text, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(self.cache, indent=2) + "\n", encoding="utf-8")
        return text, usage

    def draft(self, invoice: dict, invoice_cost: dict, offline: bool = False) -> str:
        directions = [
            "friendly first reminder", "polite follow-up requesting payment timing",
            "firm overdue reminder requesting a resolution date", "final escalation requesting immediate contact",
        ]
        stage = min(3, max(0, int(invoice["stage"])))
        if offline:
            return (
                f"Hello {invoice['payer']}, this is a {directions[stage]} about invoice {invoice['id']} for "
                f"{invoice['amount']:,} {invoice['currency']}, due {invoice['due_date']}. Please let us know "
                "when payment will be made or if you need any documents."
            )
        text, _ = self._complete("draft", [
            {"role": "system", "content": "Draft concise, respectful B2B invoice reminders. Do not invent facts or threaten the payer."},
            {"role": "user", "content": f"Write one {directions[stage]} to {invoice['payer']} for invoice {invoice['id']}, amount {invoice['amount']} {invoice['currency']}, due {invoice['due_date']}."},
        ], 140, invoice_cost)
        return text.strip()

    def classify(self, reply: str, invoice: dict, invoice_cost: dict, offline: bool = False) -> dict:
        if offline:
            low = reply.lower()
            if not reply.strip():
                return {"intent": "silent", "promised_date": None, "amount_mentioned": None}
            if "different amount" in low or "dispute" in low:
                intent = "dispute"
            elif "statement" in low or "document" in low:
                intent = "info_request"
            elif "by " in low and "20" in low:
                intent = "promise"
            else:
                intent = "paid"
            date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", reply)
            amount_match = re.search(r"(?:remitted|pay)\s+(\d[\d,]*)", low)
            amount = int(amount_match.group(1).replace(",", "")) if amount_match else None
            return {"intent": intent, "promised_date": date_match.group(1) if date_match else None, "amount_mentioned": amount}

        schema = '{"intent":"promise|dispute|info_request|paid|silent","promised_date":null,"amount_mentioned":null}'
        base_messages = [
            {"role": "system", "content": f"Classify the payer's reply. Return only strict JSON matching this shape: {schema}. promised_date is an ISO date string or null. amount_mentioned is a number or null. Use intent=paid for full or partial payment."},
            {"role": "user", "content": f"Invoice amount: {invoice['amount']} {invoice['currency']}\nPayer reply: {reply!r}"},
        ]
        for attempt in range(2):
            messages = base_messages if attempt == 0 else base_messages + [
                {"role": "assistant", "content": "Your prior response was not valid. Retry with exactly one JSON object and no prose."}
            ]
            raw, _ = self._complete("classify", messages, 100, invoice_cost)
            try:
                result = json.loads(raw)
                if not isinstance(result, dict) or set(result) != {"intent", "promised_date", "amount_mentioned"}:
                    raise ValueError("unexpected JSON shape")
                if result["intent"] not in INTENTS:
                    raise ValueError("unknown intent")
                if result["promised_date"] is not None:
                    if not isinstance(result["promised_date"], str):
                        raise ValueError("promised_date must be a string or null")
                    date.fromisoformat(result["promised_date"])
                if result["amount_mentioned"] is not None:
                    if not isinstance(result["amount_mentioned"], (int, float)) or result["amount_mentioned"] < 0:
                        raise ValueError("amount_mentioned must be non-negative numeric or null")
                return result
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
        raise ValueError("Reply classification failed strict JSON validation after one retry")
