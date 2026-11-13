# Automatic Paper Outcomes

This is observation only. It never places an order, calls a broker, changes an
approval, calls the LLM for price data, or sends extra trading notifications.
News freshness and blackout gates remain mandatory. Automatic tracking refuses
configuration with `REQUIRE_VERIFIED_NEWS=false`.

## Price Source And Approved Configuration

The existing setup webhook contains a snapshot, not subsequent prices. A separate
Pine indicator supplies completed one-minute OHLC bars in five-minute batches.
This uses the existing TradingView account, not a paid external data API. It
adds hosting requests/storage; free-service quotas and uptime are not guaranteed.

- Indicator: `pine/smc_paper_price_feed.pine` / SMC Paper Price Feed.
- Alert name: SMC Paper Price Feed NQ.
- Chart: CME_MINI_DL:NQ1!, standard candles, 5m.
- Condition: SMC Paper Price Feed -> Any alert() function call.
- Enable paper price feed: true; feed ID: `nq-paper-v1`.
- Script-generated message, once at a confirmed real-time 5m close.
- Evidence: standard unadjusted extended-session 1m bars, underlying contract
  identifiers, last 20 bars replayed as a bounded repair buffer.
- Webhook only, no app/email notifications:
  `https://<existing-backend>/webhooks/tradingview/prices?secret=<existing-secret>`.
- Expiry: January 7, 2027 at 18:00 UTC.
- Existing SMC alert `6067103295` remains unchanged. Intended total: one SMC
  candidate alert plus one data-only price alert, not duplicate signal alerts.

Pine defaults to OFF and requires a standard ES/NQ 5m chart. Changing a chart
does not change the server-side alert snapshot. TradingView's documentation:
[alert snapshots](https://www.tradingview.com/pine-script-docs/faq/alerts/),
[webhook delivery](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/),
[continuous-contract adjustments](https://www.tradingview.com/support/solutions/43000685266-how-can-i-enable-backadjustment-for-continuous-futures/).

The user delegated the free-feed approach and approved the exact proposed
deployment/activation configuration on November 13. Actual activation and live
receipt proof must be recorded in the PR/deployment close-out, not inferred from
the existence of this document or a successful static compile. See
[activation evidence](automatic_outcome_activation.md) for the deployed alert
IDs, first successful real delivery and remaining validation limits.

## Backend Configuration

```dotenv
OUTCOME_TRACKING_ENABLED=true
OUTCOME_FEED_ID=nq-paper-v1
OUTCOME_FEED_SYMBOL=CME_MINI_DL:NQ1!
REQUIRE_VERIFIED_NEWS=true
```

Defaults are disabled. Do not put the webhook secret in Pine, docs or commits.
The existing `WEBHOOK_SECRET` protects the price endpoint via header or query.
PriceBatch/PriceBar Pydantic models reject extra fields, invalid OHLC envelopes,
unconfirmed/future bars, wrong symbol/feed/contract root, unordered/duplicate
bars, incorrect minute intervals, oversized requests and stale emissions.
Only the approved exact feed symbol is accepted; no ES/NQ, CFD, ETF or real-time
versus delayed price substitution.

## Conservative Evaluation

Only eligible current-cohort, live-provider, non-test, approved BUY/SELL decisions
are considered. Original decisions and manual annotations are not overwritten.

1. Require an anchor minute ending exactly at the setup's recorded bar close,
   with the same close price. Without this, return UNKNOWN rather than compare
   potentially adjusted or wrong-feed levels.
2. Require continuous minute coverage from the anchor through the decision and
   observed outcome, with the same underlying contract. Missing minutes and
   contract rolls remain UNKNOWN, including legitimate session/holiday gaps.
3. Observe entry only after the stored decision timestamp and before expiry.
   A bar straddling a decision/expiry boundary that touches entry is ambiguous.
4. After an entry-range touch, TP1 before SL is a paper WIN, SL before TP1 a
   paper LOSS. Both exits in one bar is UNKNOWN. Entry and exit in one bar is
   UNKNOWN unless entry equals that complete bar's opening price; no assumed
   high/low traversal order is used.
5. EXPIRED requires continuous evidence of no entry touch through expiry.
   No expiry or missing evidence is UNKNOWN, never an invented expiry/loss.
6. Follow entered observations for at most 24 hours from the decision. Unresolved
   observations remain UNKNOWN. Late data may resolve missing coverage; repeated
   identical evidence is idempotent. A conflicting revision preserves original
   bars and records UNKNOWN instead of silently changing prices.

These are OHLC range-touch labels, not tick-level touch proof, limit/market order
fills, execution prices, fees/slippage, P&L or calibrated win probabilities.
Historical movement before the decision cannot count as an achievable outcome.
Delayed data adds observation delay. Data may arrive after an outcome's price
event; event timestamps, not receipt order, determine the paper sequence.

## Automation And Audit

- Price ingestion commits quickly and wakes the existing worker; evaluation
  runs separately from the HTTP acknowledgement and after queued decisions and
  notifications. Enabled workers also recover every five minutes after restart.
- Bounded scope: newest 500 decisions created within 72 hours. This is not a
  retroactive score of older setups; earlier results remain stored. The current
  single NQ 4h alert fits comfortably within that bound.
- `outcome_price_bars`: unique feed/symbol/minute, original price JSON plus first
  conflicting version, receipt/update times. No destructive retention job added.
- `automatic_outcome_evaluations`: append-only per-decision evidence hashes,
  input levels/timing, result/reason, underlying bar evidence and data version.
  Concurrent identical evaluations deduplicate; newer source evidence outranks
  an older computation finishing late.
- Dashboard/ledger show automatic and manual results separately. Automated
  counts are explicitly paper outcomes; accuracy remains NOT_ESTABLISHED.
- Authenticated `GET /forward-testing/decisions/{id}/automatic?offset=0` exposes
  the evaluation audit trail, paginated in groups of 100.
- `/status` and the forward ledger show DISABLED, WAITING_FOR_FEED, RECEIVING or
  STALE_OR_MARKET_CLOSED. Feed status is separate from candidate/news readiness.
- No automatic message is sent for these outcomes. Telegram's existing final
  approval notifications and send-time news gates are unchanged.

## Limits And Monitoring

Webhook authentication proves possession of the secret, not an independently
verified TradingView origin. Records label this WEBHOOK_AUTH_ONLY; do not turn
these paper counts into a proven-performance claim. The setup contract is
inferred from a matching closing-price anchor, not added to the original alert.

Inspect feed latest-bar time, delivery errors and UNKNOWN reasons. Long outages,
missing sessions, price/contract mismatches and ambiguous candles are expected
to reduce coverage. Do not relax those checks to improve displayed win counts.
NQ is configured first because that is the only active candidate alert. ES needs
its own explicitly approved feed/configuration; gold remains unsupported.

To pause, set `OUTCOME_TRACKING_ENABLED=false` and stop the data-only alert after
approval. Leave the SMC alert, credentials, news gates and audit tables intact.
No existing real setup is replayed or fabricated to demonstrate a WIN.
