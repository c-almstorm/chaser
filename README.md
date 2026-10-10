# Chaser

Chaser follows up on unpaid invoices through a single-agent baseline loop.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m sim.baseline
python -m eval.score
```

Set `NEATLOGS_API_KEY` for exported traces. Set `LITELLM_API_KEY` and optionally `LITELLM_BASE_URL` (defaults to `https://litellm.ai/neatlogs/v1`) for Claude drafting through the LiteLLM OpenAI-compatible API. The baseline has a local template fallback when no LLM key is configured.

## Invoice schema

Each invoice has `id`, `payer`, `amount`, `currency`, `due_date`, `status` (`open`, `promised`, `disputed`, `partial`, or `paid`), `stage` (0–3), and `history` (timestamped message and event entries).

## Baseline

The baseline selects an open invoice, drafts a stage-specific reminder, sends it through the payer simulator, and updates the invoice from the simulated reply. Run it once with `python -m sim.baseline`. `python -m eval.score` reports resolved invoices, recovered NGN, and estimated cost per invoice.

## Run record

- Neatlogs trace: not exported. `NEATLOGS_API_KEY` was unavailable during this run, so the SDK initialized locally but no dashboard trace URL was produced.
- Baseline run: 2026-10-10; 20 invoices processed; 7 fully resolved; NGN 8,960,000 recovered (includes partial payments); 0 LLM calls; estimated cost USD 0.000000 per invoice.
- Machine-readable run record: [`state/last_run.json`](state/last_run.json).

To export and save a dashboard trace link, configure `NEATLOGS_API_KEY` and rerun `python -m sim.baseline`; the simulator seed is fixed for repeatable outcomes.

## Checkpoints

- Scaffold checkpoint: repository structure, schema, and synthetic ledger.
- Baseline checkpoint: payer simulator, agent loop, score, and run record.
