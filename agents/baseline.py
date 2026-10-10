"""Small single-agent collections loop with cached stage-specific drafts."""

from __future__ import annotations

import os
from functools import lru_cache

STAGE_GUIDANCE = {
    0: "friendly first reminder",
    1: "polite follow-up with a request for payment timing",
    2: "firm overdue reminder asking for a clear resolution date",
    3: "final escalation notice requesting immediate contact",
}


@lru_cache(maxsize=4)
def draft_message(stage: int) -> str:
    """Draft once per stage; cached drafts reduce calls and spend."""
    guidance = STAGE_GUIDANCE[stage]
    api_key = os.getenv("LITELLM_API_KEY")
    if not api_key:
        return (
            f"Hello, this is a {guidance} about invoice {{invoice_id}} for "
            f"{{amount}} {{currency}}, due {{due_date}}. Please let us know "
            "when payment will be made or if you need any documents."
        )

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LITELLM_BASE_URL", "https://litellm.ai/neatlogs/v1"),
    )
    response = client.chat.completions.create(
        model=os.getenv("LITELLM_MODEL", "anthropic/claude-3-5-haiku-latest"),
        temperature=0.2,
        max_tokens=110,
        messages=[
            {"role": "system", "content": "Write concise, respectful B2B invoice collection messages. Preserve placeholders exactly. Never threaten or invent facts."},
            {"role": "user", "content": f"Write one message for a {guidance}. Include {{invoice_id}}, {{amount}}, {{currency}}, and {{due_date}} exactly as placeholders."},
        ],
    )
    return response.choices[0].message.content.strip()


def format_message(invoice: dict) -> str:
    template = draft_message(int(invoice["stage"]))
    return template.format(
        invoice_id=invoice["id"],
        amount=f"{invoice['amount']:,}",
        currency=invoice["currency"],
        due_date=invoice["due_date"],
    )
