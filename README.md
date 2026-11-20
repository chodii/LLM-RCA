# Running an experiment campaign

Use a Python environment with the project dependencies installed. Configure
PostgreSQL and prepare a chunked incident JSON file before starting.

Set `OPENAI_API_KEY` in your shell to use OpenAI directly:

```bash
export OPENAI_API_KEY='your-api-key'
```

OpenRouter remains the default provider and uses `OPENROUTER`.

From the public copy's root (the directory containing `src/`), run a small
GPT-4o mini campaign with all three prompt presets and three held-out incidents
per preset:

```bash
PYTHONPATH=src python -m rca.ai_agent.experiments.campaign \
  --name smoke-openai-4o-mini --incidents /path/to/chunked_incidents.json \
  --provider openai --model gpt-4o-mini \
  --repetitions 1 --incident-limit 3 --budget-usd 2
```

Results go to `out/campaigns/smoke-openai-4o-mini/`. Repeat the same command
to resume. The budget threshold is checked between runs.
