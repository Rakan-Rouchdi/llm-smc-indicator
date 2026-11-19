# Unified Indicator and Live Testing Audit

Historical audit. The proposed migration below was approved and completed on
November 19; see [activation evidence](unified_nq5m_activation_2026_11_19.md).
Statements about unchanged legacy alerts describe November 17, not current wiring.

Checked November 17, 2026, approximately 17:20-17:36 UTC. The hosted service and
price delivery are working, but the current forward-testing cohort has no
eligible approved setups and therefore no measured WIN/LOSS results. The active
signal alert is NQ 4h, not the PRD's primary 5m/15m configuration.

## Production Evidence

| Check | Observed result |
| --- | --- |
| Authenticated hosted dashboard | Loaded successfully using existing credentials; no password change |
| Worker | RUNNING; zero failed jobs; oldest pending age zero |
| Configured reasoning provider | OpenAI; not called for the latest rejected preflight test |
| News | ES and NQ CLEAR; automatic source fetched/published at 17:20:43 UTC; zero consecutive failures |
| News safety | Verified coverage, freshness and blackout gates remain required |
| Latest natural setup receipt | October 16, 2026 at 14:10:06.570550 UTC |
| Latest setup receipt | November 13 at 17:14:21.539382 UTC; DELIVERY TEST |
| Latest decision | NO_TRADE, REJECTED, model deterministic-preflight; blackout and consolidation rejection |
| Current forward cohort | One receipt, excluded as DELIVERY_TEST; zero eligible live-approved candidates |
| Eligible outcome totals | WIN 0, LOSS 0, EXPIRED 0, UNKNOWN 0; no paper performance established |
| Price evidence | RECEIVING; latest stored minute close was 17:15 UTC at dashboard inspection |
| TradingView price delivery | Successful webhook delivery visible through 17:35 UTC |
| Final decision notifications | Configured; zero sent / zero needing review; the earlier labelled transport test is not a final decision |

The excluded delivery-test row has an UNKNOWN/NOT_ELIGIBLE placeholder. That is
not an eligible UNKNOWN outcome and is not counted in the totals above. Five
historical delivery tests are excluded from the broader evaluation summary.

The dashboard's alert observation is UNKNOWN because its last operator check
was November 13 at 17:10:58 UTC, beyond the 24-hour freshness limit. The live
TradingView check below confirms active alerts. These are different facts:
the dashboard is not continuously polling TradingView. No operator observation,
Render configuration, credential, news gate or production record was changed
in this audit.

## Existing Alerts Were Not Changed

| Purpose | ID | Snapshot | Status at final check |
| --- | --- | --- | --- |
| SMC candidate | 6067103295 | CME_MINI_DL:NQ1!, 4h, main script revision 19 | ACTIVE, last_fired null |
| Outcome prices | 6067783354 | CME_MINI_DL:NQ1!, 5m, legacy price script revision 1 | ACTIVE, last fired 17:35:00 UTC |

Both remain on their original endpoints and January 7, 2027 expiries (18:00:14
and 18:00:41 UTC respectively). JSON is enabled and test mode is off for the
candidate snapshot. No duplicate alert was created. This audit did not inspect
or replace the private webhook URLs; successful current price delivery does
not itself prove the candidate endpoint's next delivery will succeed.

## Why the Main Alert Has Not Fired

The new Funnel panel counts progressively surviving gates over the last 100
loaded chart bars. The open bar is excluded, leaving 99 confirmed observations
in these snapshots. Counts were collected on the same NQ feed with score 75,
confirmation age 6 and unchanged signal logic:

| Cumulative gate | 4h | 1h | 15m | 5m |
| --- | ---: | ---: | ---: | ---: |
| Closed bars | 99 | 99 | 99 | 99 |
| Data ready | 99 | 99 | 99 | 99 |
| Valid FVG retest | 21 | 14 | 13 | 11 |
| Sequence / age | 10 | 7 | 6 | 1 |
| BOS + HTF | 0 | 4 | 2 | 1 |
| Liquidity | 0 | 2 | 1 | 1 |
| Not consolidated | 0 | 2 | 1 | 1 |
| Volume | 0 | 2 | 1 | 1 |
| Score at least 75 | 0 | 1 | 1 | 1 |
| Valid risk / candidate | 0 | 1 | 0 | 1 |
| Unique candidates | 0 | 1 | 0 | 1 |
| Neutral HTF bars (independent count) | 93 | 51 | 0 | 0 |

On 4h the automatic higher-timeframe filter uses daily EMA 50/200. It was
neutral on 93 of the 99 examined closed bars; none of the ten sequence-valid
retests passed BOS plus aligned HTF. The script therefore had nothing to send.
This is evidence of signal scarcity in this window, not a webhook outage or
proof that every historical quiet period has the same cause.

The rules also require liquidity before BOS, an FVG at/soon after BOS, a later
retest within the confirmation window, sufficient volume/score and valid risk
geometry. A visible FVG alone is not a candidate. The 15m window had one setup
reach score eligibility but fail the final risk check.

These windows span different wall-clock periods. They are not comparable
signal-rate estimates, a backtest, or evidence of profitability. The historical
5m SELL label is not a delivered webhook, backend-approved signal or recorded
win. There is currently no 5m candidate alert. The account feed is visibly
ten minutes delayed, which remains a limitation for timely decision support.

## One Canonical Indicator

`pine/smc_llm_candidate_detector.pine` now contains both jobs. The standalone
`pine/smc_paper_price_feed.pine` source is removed; its history is retained in
Git. Its chart study was removed from the inspected 5m layout, leaving the main
custom indicator plus TradingView's built-in Volume study. The legacy server
alert continues operating until the migration is approved.

- Default **Alert stream = SMC setups**: existing signal/test payload behavior.
- **Alert stream = Outcome prices**: only bounded price batches, never setup or
  test messages. It requires a standard ES/NQ 5m chart and a valid feed ID.
- Price batches retain `paper_ohlcv_v1`, `standard_unadjusted`, the underlying
  contract and a maximum 20 completed one-minute bars for gap repair.
- Price mode suppresses candidate labels, proof markers, zones and consolidation
  shading. Its panel reports chart support, output enablement and buffer state.
- New **Panel mode = Funnel** records closed-bar gates before FVG mitigation.
  It is centered at the right to avoid the symbol/OHLC header. Compact remains
  the default chart view.
- Existing input indexes, session calculations, SMC eligibility and setup JSON
  are preserved. No threshold was reduced to manufacture signals.

One script does not mean one server alert in this implementation. Two mutually
exclusive snapshots keep the setup and price endpoints separate and avoid
price-message spam in the signal channel. Both can be created from one chart
instance; restore its visible stream to SMC setups after creation.
TradingView keeps each alert's script and inputs as a snapshot, so saving a
chart/script does not update an existing alert:
[TradingView alert documentation](https://www.tradingview.com/pine-script-docs/faq/alerts/).

## Validation

- Baseline backend suite: 321 passed, zero failed.
- Seven new source-contract tests pin the approved session/detection/payload
  blocks and check stream isolation, price bounds, visuals and funnel ordering.
- Final full backend suite: 328 passed, zero failed; one pre-existing
  Starlette/httpx deprecation warning.
- Final Pine source: saved revision 24, 765 lines; server compile zero errors,
  zero warnings, chart editor zero errors.
- Runtime funnel inspected on NQ 5m, 15m, 1h and 4h.
- Price mode tested with output disabled: 5m populated 20 minute bars; 4h
  showed UNSUPPORTED and an empty buffer. Setup/test output remained disabled.
- Restored visible chart to NQ 5m, SMC setups, JSON on, test off.
- No live delivery from the new price-mode snapshot has been claimed: no new
  snapshot has been created. Existing legacy price delivery remains healthy.
- No new ES runtime audit or mobile chart check was performed in this change.
- Source-contract tests and compilation are not a full Pine strategy simulation.

Screenshots, captured after the final panel-position fix:

- [NQ 4h funnel](screenshots/smc_unified_nq4h_funnel_20261117.png)
- [NQ 5m funnel](screenshots/smc_unified_nq5m_funnel_20261117.png)

## Proposed Alert Migration Awaiting Approval

Use a controlled 5m forward test, consistent with the PRD's primary 5m/15m
scope, rather than leaving the only candidate alert on 4h. This changes the
observation timeframe, not the safety filters, and does not promise more
approved trades or better results.

| Setting | Candidate snapshot | Background price snapshot |
| --- | --- | --- |
| Replace existing ID | 6067103295 | 6067783354 |
| Name | SMC LLM Candidate Detector webhook | SMC LLM Outcome Prices NQ |
| Script | SMC LLM Candidate Detector, saved revision 24 | Same script, revision 24 |
| Symbol / chart | CME_MINI_DL:NQ1!, standard candles, extended session, unadjusted | Same |
| Interval | 5m (changes from 4h) | 5m (unchanged) |
| Condition | SMC LLM Candidate Detector -> Any alert() function call | Same |
| Alert stream | SMC setups | Outcome prices |
| Enable alert() JSON payloads | true | true |
| Enable test webhook alert | false | false |
| Outcome feed ID | nq-paper-v1 (unused in setup mode) | nq-paper-v1 |
| Message | Script-generated JSON; no static JSON | Script-generated JSON; no static JSON |
| Frequency | Confirmed bar close; unique qualifying FVG | Confirmed 5m close; max 20 closed 1m bars |
| Notifications | Existing app/toast plus webhook; candidate only | Webhook only; no app/toast/email/sound |
| Expiry | January 7, 2027 at 18:00 UTC | January 7, 2027 at 18:00 UTC |
| Webhook | https://<production-host>/webhooks/tradingview?secret=<existing-secret> | https://<production-host>/webhooks/tradingview/prices?secret=<existing-secret> |

All signal inputs retain current values: automatic ES companion; pivots 3/3;
BOS/FVG minimum 2 ticks; sweep buffer 1 tick; equal-pool tolerance 4 ticks; SMT
lookback 20; RVOL 50 with thin/strong thresholds 0.70/1.50; ATR 14;
displacement 1.0 ATR; consolidation lookback 20, range 2.0 ATR, efficiency 0.30;
HTF input 60 with EMA 50/200; expiry 30 bars; minimum RR 1.50, default TP 2R;
stop buffer 2 ticks; minimum score 75; confirmation age 6. Diagnostics on,
Compact panel, zones/proof off, candidate labels on.

After explicit approval, verify destinations privately, replace one snapshot at
a time without duplicate active alerts, and confirm exactly one candidate plus
one price alert. Observe the next real price delivery and natural candidate
when available; do not generate a fake approval. Record the activation timestamp
and separate subsequent 5m results from the old 4h window. Do not reset/delete
the existing fixed-cohort audit history or mix timeframes into a performance
claim. The current ledger retains each setup's timeframe for that review.

Keep `REQUIRE_VERIFIED_NEWS=true`, deterministic validation, safe fallback and
UNKNOWN handling unchanged. Updating the operator alert observation and the
dated tester manual belongs to the activation close-out. No Render deployment
is required for these Pine-only changes. No trades, replay, broker connection,
secret changes or synthetic production requests were made in this audit.
