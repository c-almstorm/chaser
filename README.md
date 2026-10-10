# Chaser

Chaser follows up on unpaid invoices through a single-agent collections loop.

## Run

```powershell
python -m pip install -r requirements.txt
python -m sim.ledger                    # regenerate data/ledger.json using seed 42
python -m eval.no_followup              # seeded zero-contact control
python -m sim.baseline --offline        # fast template baseline (still requires Neatlogs)
python -m sim.baseline                  # real LiteLLM calls; requires both API keys
python -m eval.score state/last_run.json
```

Configure `NEATLOGS_API_KEY` for every run. Runs fail immediately if the key is absent so they cannot silently produce an untraced result. Configure `LITELLM_API_KEY` for the real baseline. `LITELLM_BASE_URL` defaults to `https://litellm.ai/neatlogs/v1`. Drafting uses Claude Sonnet 5; reply classification uses the cheaper Claude Haiku 5.5. Default rates are $2/$10 per million draft input/output tokens and $0.10/$0.50 per million classification input/output tokens; override model names and rates through environment variables when your LiteLLM route differs. A persistent $12 cumulative spend guard reserves estimated request cost before each call and stops the loop before another call can exceed the cap; the remaining $8 stays in reserve. Cumulative usage is stored in `state/llm_spend.json`.

LLM responses are cached by model and prompt SHA-256 in `state/llm_cache.json`; repeated requests have zero additional tokens and cost. `--offline` activates local template drafting and deterministic local classification.

## Invoice schema

Invoices contain `id`, `payer`, `amount`, `currency`, `due_date`, `status` (`open`, `promised`, `disputed`, `partial`, or `paid`), `stage` (0–3), and timestamped `history`. The fixed seed and as-of date in `sim/ledger.py` make both the 20-invoice ledger and payer responses comparable across runs.

## Results

Same seed: `42`. Amount recovered includes partial payments; resolved counts fully paid invoices. LLM cost is accumulated from actual input/output token usage and the configured model rates.

| Run | Resolved | Amount recovered (NGN) | Cost per invoice (USD) |
|---|---:|---:|---:|
| No follow-up | pending live traced run | pending | pending |
| Offline baseline | pending live traced run | pending | pending |
| LLM baseline | pending live run | pending | pending |

Latest LLM baseline trace: pending live run.

Run records: `state/no_followup.json`, `state/offline_baseline.json`, and `state/llm_baseline.json`. The full per-invoice token/cost breakdown for the latest LLM run is in `state/last_run.json`; the final invoice ledger is in `state/llm_baseline_ledger.json`.

## Checkpoints

- `e551245` Scaffold checkpoint.
- `2d552e3` Single-agent baseline checkpoint.
- `c97b72b` Seeded ledger, cached LLM baseline, and no-follow-up control checkpoint.
