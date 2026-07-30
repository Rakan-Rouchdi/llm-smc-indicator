# Live OpenAI Integration

Phase 5B adds an optional OpenAI provider behind the existing LLM provider
interface. Mock mode remains the default. This system is decision support only:
it does not place trades, connect to a broker, or provide position sizing or
financial advice.

## Provider Behavior

`LLM_PROVIDER=mock` uses the deterministic local provider and makes no OpenAI
request.

`LLM_PROVIDER=openai` uses the OpenAI Responses API only when
`OPENAI_API_KEY` is also configured. The request contains:

- the structured TradingView setup
- news context
- Telegram context
- deterministic risk policy
- instructions to return `BUY`, `SELL`, or `NO_TRADE`

The provider requests a strict Structured Output, then independently validates
the returned JSON against `schemas/llm_trade_decision.schema.json` and the
Pydantic `LLMTradeDecision` model. The deterministic validator still runs after
the LLM and can convert a proposed trade to `NO_TRADE`.

The API request uses `store=false`. OpenAI documents the Responses API and
Structured Outputs here:

- <https://developers.openai.com/api/docs/guides/text>
- <https://developers.openai.com/api/docs/guides/structured-outputs>

## Enable OpenAI Manually

Do not paste the API key into Codex, source code, Pine, documentation, or a
committed file.

From the project root, create the local configuration if it does not exist:

```bash
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

Open `backend/.env` locally in your editor and set:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=<add your key manually>
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20
LLM_MAX_RETRIES=2
```

Also replace the placeholder `WEBHOOK_SECRET` with the secret used by the
existing TradingView alert. Do not rotate it unless the existing alert webhook
URL is updated as the same operation.

`backend/.env` is gitignored. Confirm before starting:

```bash
git check-ignore -v backend/.env
```

Restart the backend:

```bash
export MVP_PORT=8003
scripts/start_backend.sh
```

Mock remains the application default, but the start script allows an explicit
`LLM_PROVIDER=openai` value from `backend/.env`.

## Controlled Test

Keep TradingView test mode disabled. Send a local sample:

```bash
scripts/send_sample_webhook.sh
scripts/check_latest_decision.sh
```

Inspect the stored `model` field:

- the configured OpenAI model means the live provider succeeded
- `mock-llm-deterministic-openai-fallback` means OpenAI failed and mock fallback
  completed the workflow
- `mock-llm-deterministic` means mock mode was selected or no API key was
  available

The sample sender refreshes its setup timestamp and ID, so it can be run more
than once.

## Failure Handling

The backend falls back to the deterministic mock provider for:

- request timeout
- API/network failure
- incomplete or empty response
- malformed JSON
- JSON Schema mismatch
- Pydantic validation failure
- response `setup_id` mismatch

Fallback details never include the API key or raw provider exception. The
stored model name and validation notes identify that fallback occurred.

If `LLM_PROVIDER=openai` is set without `OPENAI_API_KEY`, startup and webhooks
continue in mock mode.

## Return to Mock Mode

Edit `backend/.env`:

```dotenv
LLM_PROVIDER=mock
OPENAI_API_KEY=
```

Restart the backend. No TradingView alert or Pine change is required.

## Operational Boundaries

- Keep exactly one TradingView webhook alert.
- Do not expose the dashboard without an authentication boundary.
- Treat LLM output as untrusted until schema and deterministic validation pass.
- Confidence is setup-quality metadata, not certainty or win probability.
- Never use this workflow for automatic order execution.
