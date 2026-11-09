# Closed-Market Testing

Markets do not need to be open to test schemas, deterministic rules, mock
reasoning, persistence, dashboard pages, authentication or HTTP ingestion.
Synthetic tests cannot prove actual TradingView delivery or trading performance.

## Isolated Local Preview

From the repository root:

```bash
backend/.venv/bin/python backend/scripts/preview_mvp.py --port 8012 --scenario approved
```

Open `http://127.0.0.1:8012/dashboard`. The history contains four DELIVERY TEST
fixtures. Their prices and SMC features are made-up examples, not market readings.
Choose `approved`, `blackout`, `stale` or `gold` with `--scenario` to make that case
latest. The expected outcomes are BUY for the synthetic approved case and
NO_TRADE for the other three. Detail pages also label tests explicitly.

The helper binds only to 127.0.0.1, uses a disposable temporary SQLite database,
forces mock reasoning, disables notification/decision workers, and ignores all
`.env` files. It clears inherited external credentials in its own process only;
it does not edit environment files or the calling shell. No TradingView, broker,
OpenAI, Telegram or calendar-provider calls occur. It does not write production.
Stop with Ctrl-C; its temporary directory is removed on normal shutdown.

The preview is deliberately not armed: no live worker or TradingView observation
is faked. "Not confirmed ready" is expected. It is an unauthenticated local demo;
do not tunnel or deploy it publicly. Use a different port if 8012 is occupied.

## Gold Is Not a Weekend Shortcut

Current Pine `strict_v1` supports ES/NQ and their paired SMT logic only. XAUUSD
fails its supported-chart gate. Backend preflight now independently rejects
UNKNOWN instruments, and calendar coverage for unsupported roots is UNKNOWN.
The gold fixture proves rejection and UI rendering, not gold signal support.

Ordinary spot-gold feeds are not 24/7. For example,
[OANDA's XAU/USD schedule](https://www.oanda.com/ca-en/trading/hours-of-operation/)
opens Sunday at 18:05 New York time and closes Friday at 16:59, with daily breaks.
For November 8, 2026, 18:05 New York is 23:05 London/UTC. Other providers may differ;
separate weekend-gold products are not interchangeable with standard XAUUSD.

[TradingView's Pine alert documentation](https://www.tradingview.com/pine-script-docs/concepts/alerts/)
requires realtime execution for alert delivery; once-per-bar-close requires a
realtime closing bar. Reloading a closed chart or viewing historical bars does
not produce a new real webhook. Existing historical drawings can still be
inspected. No replay/trade tools are used or needed for the local preview.

Gold support would be a separate change: select the exact feed, validate the
SMT companion, volume semantics, sessions, tick/price rules and news scope, then
perform instrument-specific historical and live checks. Do not rename ES/NQ
payloads and interpret their decisions as gold analysis.

## Checks Performed

- Real local dashboard and setup details loaded with mock fixture decisions.
- Desktop 1280px and mobile 390px views had no document-level horizontal overflow.
- Unsupported gold showed NO_TRADE and the explicit ES/NQ-only rejection.
- No production alerts, Pine code, credentials or data were changed.
- Preview screenshots: `/tmp/smc-preview-desktop.png`, `/tmp/smc-preview-mobile.png`.
