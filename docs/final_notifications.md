# Final Decision Notifications

TradingView app/toast messages announce provisional Pine candidates. The backend
can separately send an approved candidate through Telegram or an HTTPS webhook.
It never places an order. Telegram sentiment ingestion is still mocked; it is
not enabled by configuring an outgoing bot.

## Recommended Private Channel

Use a private Telegram bot/chat for this single-operator MVP. Follow Telegram's
[BotFather instructions](https://core.telegram.org/bots/features#botfather) to
create the bot yourself. Start a private conversation with that bot and obtain
your own chat ID privately using Telegram's official bot tools. Do not paste a
bot token, chat identifier, dashboard password or other credential into Codex,
repository files, screenshots, shell history or public issue comments.

Add these variables privately in the existing hosting service environment:

```dotenv
ENABLE_NOTIFICATIONS=false
TELEGRAM_BOT_TOKEN=<private bot token>
TELEGRAM_CHAT_ID=<approved private chat ID>
NOTIFICATION_WEBHOOK_URL=
```

An HTTPS notification webhook takes precedence when configured. Leave it empty
for Telegram. Before enabling delivery, explicitly approve the recipient and
the category of recurring messages: final backend-approved BUY/SELL candidates
with symbol, timeframe, setup quality, entry, SL, TP, RR and reason. Set
`ENABLE_NOTIFICATIONS=true` only after that approval and deploy/restart.
The initial November 13 implementation left delivery disabled. See the
[private Telegram activation report](private_telegram_activation_2026_11_13.md)
for the separately approved connection and test.

## Hosted Diagnostic Test

After privately configuring the bot token and private chat ID, keep
`ENABLE_NOTIFICATIONS=false` until a diagnostic message is verified. The
authenticated `POST /notifications/test` accepts only:

```json
{"test_id": "<a newly generated UUID>"}
```

Use the dashboard-authenticated `/docs` page to execute it. It sends a fixed
`SMC NOTIFICATION DELIVERY TEST` message to the configured private Telegram
chat, not a BUY/SELL or fabricated approval. It never calls OpenAI, creates a
setup/decision, or changes calendar coverage. Verified-news blocking must stay
configured, even for this transport-only diagnostic. Current stale/blackout
coverage still blocks trade candidates, but need not block an informational
connectivity check.

The result is persisted separately in `notification_probes` and available at
`GET /notifications/tests/{test_id}`. Reusing a test ID never resends; there is
also a database-enforced limit of one new test per UTC minute. `UNKNOWN` means
an ambiguous attempt, including a crash or timeout, and must be reconciled
before attempting another test. `SENT` means Telegram accepted the message;
verify the message in the actual private chat as well.

No arbitrary message text, chat ID, token or destination is accepted by this
endpoint. Dashboard credentials are mandatory even in local development.
The API refuses groups/channels, alternate notification webhooks, missing
credentials and disabled verified-news policy. Application HTTP logs redact
Telegram bot tokens, which appear in Telegram API URL paths.

## Safety And Delivery Semantics

- Only approved, non-test, non-fallback BUY/SELL decisions can enter the outbox.
- Before sending, the sender validates stored payloads, matching decision/setup,
  freshness, expiry, unchanged destination and current verified-news coverage.
- Manual, ForexFactory and ShowMyTrades calendars use the same provider-matched
  gate. Missing, stale, expired, mismatched or blackout coverage suppresses the
  message. A successful fetch is not itself proof of fresh coverage.
- The message identifies entry as unfilled and quality as not a win probability.
- Destination success becomes `SENT`; HTTP 429/5xx retry at most three attempts.
  Timeout/ambiguous delivery becomes `UNKNOWN` and is not blindly replayed.
- Inspect authenticated `/notifications`, setup delivery evidence and the actual
  private chat. An API success is not proof of phone receipt or reading.
- Never replay an old BUY/SELL or enable Pine test mode just to force a push.
  The blocked HTTP probe intentionally cannot exercise an approved live push.

Set `ENABLE_NOTIFICATIONS=false` to stop sending. Queued records are suppressed
when consumed; retain records for auditing rather than deleting delivery history.

Tests use synthetic calendars, decisions and HTTP transports. They establish
code behavior, not a live Telegram delivery. Telegram API behavior is documented
in [sendMessage](https://core.telegram.org/bots/api#sendmessage).
