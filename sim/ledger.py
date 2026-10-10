"""Generate a reproducible synthetic Nigerian healthcare invoice ledger."""

from __future__ import annotations

import random
import json
from datetime import date, timedelta
from pathlib import Path

SEED = 42
AS_OF = date(2026, 10, 10)
PAYERS = [
    "Lagos Central Pharmacy", "Ikeja Family Clinic", "Unity Diagnostics Lab", "Garden City Pharmacy",
    "Surulere Medical Clinic", "Northstar Pathology Lab", "Kano Wellness Pharmacy", "Riverside Women's Clinic",
    "Beacon Clinical Laboratory", "Yaba Community Pharmacy", "Ibadan Hope Clinic", "PrimeCare Diagnostics",
    "Abuja HealthPlus Pharmacy", "Lekki Specialist Clinic", "Kaduna Reference Lab", "Enugu City Pharmacy",
    "Mainland Paediatric Clinic", "Cedar Medical Testing Lab", "Jos Sunrise Pharmacy", "Abeokuta General Clinic",
]


def generate_ledger(seed: int = SEED, as_of: date = AS_OF) -> list[dict]:
    rng = random.Random(seed)
    invoices = []
    for index, payer in enumerate(PAYERS, start=1):
        age_days = rng.randint(0, 60)
        invoices.append({
            "id": f"INV-{index:03d}",
            "payer": payer,
            "amount": rng.randrange(250_000, 3_500_000, 5_000),
            "currency": "NGN",
            "due_date": (as_of - timedelta(days=age_days)).isoformat(),
            "status": "open",
            "stage": min(3, age_days // 15),
            "history": [],
        })
    return invoices


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "data" / "ledger.json"
    target.write_text(json.dumps(generate_ledger(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {target}")
