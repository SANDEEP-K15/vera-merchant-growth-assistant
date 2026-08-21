# Vera — magicpin AI Challenge Backend

## Run

```bash
python -m pip install -r requirements.txt
uvicorn vera.main:app --host 0.0.0.0 --port 8080
```

The API exposes:

- `GET /v1/healthz`
- `GET /v1/metadata`
- `POST /v1/context`
- `POST /v1/tick`
- `POST /v1/reply`

## Design

The engine is deterministic first and LLM-assisted second:

1. Contexts are versioned and stored atomically in memory.
2. Trigger candidates are validated and ranked deterministically.
3. Category + merchant + trigger + optional customer context is reduced to a grounded decision.
4. A deterministic renderer produces a safe baseline message.
5. If `LLM_PROVIDER` and `LLM_API_KEY` are configured, the LLM may improve wording.
6. LLM output is validated; invalid or hallucinated output falls back to the deterministic renderer.
7. Suppression keys prevent duplicate sends.
8. `/v1/reply` handles explicit positive intent, opt-out/hostility, and WhatsApp auto-replies without re-qualifying the merchant.

## Optional LLM

Copy `.env.example` to your environment and set, for example:

```text
LLM_PROVIDER=gemini
LLM_API_KEY=...
LLM_MODEL=gemini-2.0-flash
```

If no LLM credentials are configured, Vera still runs using the deterministic engine.

## Challenge dataset

The supplied generator has a path assumption in the original challenge package. The local preparation used the seed files and generated the expanded dataset under `expanded/`.

## Local evaluation

The package includes a local regression harness:

```bash
PYTHONPATH=. python tools/evaluate.py --pairs --show
PYTHONPATH=. python tools/evaluate.py --all
PYTHONPATH=. pytest -q tests/test_api.py
```

`tools/evaluate.py` is a **heuristic regression tool**, not the official LLM judge. It is useful for catching regressions in specificity, trigger grounding, merchant fit, category vocabulary, and CTA behavior.

The official challenge judge remains the source of truth for the final score.
