"""Deterministic seeded synthetic payer responses."""

from __future__ import annotations

import random
from datetime import date, timedelta


class PayerSimulator:
    def __init__(self, seed: int = 42, as_of: date = date(2026, 10, 10)):
        self.random = random.Random(seed)
        self.as_of = as_of

    def reply(self, invoice: dict, message: str) -> dict:
        outcome = self.random.choices(
            ["paid", "promise", "dispute", "info_request", "silent", "partial"],
            weights=[25, 27, 10, 14, 14, 10],
            k=1,
        )[0]
        if outcome == "paid":
            return {"type": "paid", "text": "Payment has been sent in full. Thank you."}
        if outcome == "promise":
            promised_date = self.as_of + timedelta(days=self.random.randint(2, 14))
            return {"type": "promise", "date": promised_date.isoformat(), "text": f"We will settle this invoice by {promised_date.isoformat()}."}
        if outcome == "dispute":
            return {"type": "dispute", "text": "Our records show a different amount. Please review the invoice."}
        if outcome == "info_request":
            return {"type": "info_request", "text": "Could you please send us an updated statement of account?"}
        if outcome == "partial":
            amount = max(1, invoice["amount"] // 2)
            return {"type": "partial", "amount": amount, "text": f"We have remitted {amount:,} NGN now and will follow up on the balance."}
        return {"type": "silent", "text": ""}
