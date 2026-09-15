# ITXN Full-System Codespaces Lab

This layer is for browser/mobile bring-up of the complete architecture. It does not replace the core architecture.

## One-time Codespaces configuration

Create a Codespaces secret named `OPENROUTER_API_KEY` in the repository (recommended) and choose an OpenRouter model that supports the chat-completions/tool-calling features used by the project. Optional:

- `OPENROUTER_MODEL` — default `openai/gpt-4o-mini`
- `OPENROUTER_BASE_URL` — default `https://openrouter.ai/api/v1`

## Start

```bash
bash scripts/codespace_up.sh
```

Open forwarded port 8000 from the Codespaces **Ports** tab.

## Deterministic verdict

```bash
python scripts/full_system_verdict.py
```

## Full live verdict

This performs one real LLM-backed query and then exercises the downstream chain:

```text
User question
  -> Intent / Text-to-SQL
  -> SQL review + validation
  -> DuckDB star schema
  -> baseline enrichment
  -> BA + CEO synthesis
  -> memory persistence
  -> Sidecar follow-up / investigation hooks
  -> Alert Agent
  -> SML correlation
  -> Evidence
  -> Hypothesis
  -> Council
  -> Governance proposal
  -> human approval gate (never auto-approved)
```

Run:

```bash
python scripts/full_system_verdict.py --live
```

## Important boundary

The primary query path must remain fast. Sidecar/SML/Evolution are allowed to run asynchronously or as post-query verification work. Governance is a human gate and never mutates production automatically.
