# LLM-Powered Smart Money Concepts TradingView Indicator — Complete PRD and MVP Build Specification

**Version:** 1.0  
**Date:** 2026-07-05  
**Status:** Build-ready MVP specification  
**Source concept:** `ml-trading-indicator-concept.md`  
**Primary build target:** Codex Agent + human TradingView QA  
**Core change from source concept:** Replace “traditional machine learning model” with an **LLM-powered reasoning wrapper** that reviews structured chart/news/context data and returns a buy/sell/no-trade decision in a strict JSON schema.

---

## 1. Executive Summary

### 1.1 Product Name

**SMC LLM Trade Setup Validator**

### 1.2 One-Line Pitch

An LLM-assisted Smart Money Concepts TradingView workflow that detects ES/NQ trade setups on-chart, sends structured setup context to a backend, enriches it with news and optional Telegram context, and returns an explainable **BUY / SELL / NO_TRADE** decision with confidence, entry zone, stop-loss, take-profit, and rationale.

### 1.3 Product Concept

The product is not a traditional trained ML model. It is a hybrid system:

1. **TradingView Pine Script indicator** detects objective market-structure features:
   - BOS / structure break
   - FVG / IFVG zones
   - order block fallback zones
   - liquidity sweeps
   - SMT divergence between ES and NQ
   - session context
   - relative volume
   - consolidation filter
   - higher-timeframe bias
   - displacement

2. **Backend service** receives TradingView alert webhooks, enriches them with:
   - scheduled high-impact news blackout data
   - optional headline context
   - optional Telegram signal aggregation
   - prompt/version metadata

3. **LLM decision layer** reviews the structured setup and returns:
   - action: `BUY`, `SELL`, or `NO_TRADE`
   - confidence score
   - bias
   - entry range
   - stop-loss
   - take-profit
   - reason summary
   - blocking conditions
   - human-review flag

4. **Dashboard and notifications** show the final LLM-reviewed decision. The Pine Script chart shows provisional rule-based setup markers and diagnostics.

### 1.4 Critical Buildability Constraint

TradingView can send alert webhooks outward, but a normal Pine Script indicator cannot make arbitrary real-time HTTP calls to fetch an LLM response and repaint the chart with that response. Therefore, the MVP uses this practical architecture:

- **TradingView chart:** rule-based/provisional setup detection, diagnostic panel, entry/SL/TP preview, alert JSON emission.
- **Backend dashboard / notification channel:** final LLM-approved or rejected decision.
- **Optional manual overlay mode:** the user may paste an approved decision into Pine input fields to show the final LLM decision on-chart, but this is not automatic in MVP.

This is the only reliable MVP path that a Codex Agent can build without private TradingView platform integration or a proprietary market-data feed.

### 1.5 MVP Outcome

At the end of the MVP build, a user can:

1. Add the Pine Script indicator to ES or NQ in TradingView.
2. See SMC diagnostic states on chart.
3. Receive provisional setup markers and local entry/SL/TP preview.
4. Configure a TradingView alert that sends a JSON payload to the backend.
5. See the backend accept the webhook, enrich context, call an LLM, validate the response, and store the decision.
6. View final decisions in a local web dashboard and optional notification channel.
7. Record manual trade outcomes to evaluate whether the workflow is useful.

---

## 2. Goals, Non-Goals, and Assumptions

### 2.1 Goals

| ID | Goal | Description |
|---|---|---|
| G1 | Build a usable Pine Script MVP | Detect SMC confluences and emit structured alerts from TradingView. |
| G2 | Replace traditional ML with LLM reasoning | Use an LLM as a setup reviewer, not as a trained statistical model. |
| G3 | Keep chart facts deterministic | Pine Script produces objective facts; the LLM must not invent chart conditions. |
| G4 | Use strict JSON contracts | All webhook input and LLM output must be schema-validated. |
| G5 | Prevent unsafe auto-trading | MVP is decision support only. No broker execution. |
| G6 | Make it Codex-buildable | Include repo structure, APIs, schemas, tests, and acceptance criteria. |
| G7 | Preserve future ML path | Log all setup/decision/outcome data so a future traditional ML model can be trained later if desired. |

### 2.2 Non-Goals for MVP

The MVP must **not** include:

- Broker execution or auto-order placement.
- A trained traditional ML model.
- Automatic round-trip plotting of LLM decisions inside TradingView.
- Paid order-flow / footprint / volume-delta integration.
- Fully automated Telegram channel scraping requiring real user credentials.
- Monetization, subscription billing, or licensing enforcement.
- Claims of profitability, guaranteed win rate, or investment advice.

### 2.3 Assumptions Locked for MVP

| Area | MVP Assumption |
|---|---|
| Instruments | ES and NQ futures continuous contracts: `CME_MINI:ES1!`, `CME_MINI:NQ1!`. |
| Primary chart timeframes | 5m and 15m. Script should also compile on 1m, 30m, and 1h. |
| Session timezone | New York time for session labels and economic-event interpretation. |
| User timezone | User-facing docs may note Asia/Dubai, but trading sessions use New York market time. |
| LLM provider | Default implementation uses an OpenAI-compatible API client. Provider can be swapped later. |
| Backend language | Python 3.11+ with FastAPI, Pydantic, SQLite for MVP. |
| Frontend/dashboard | FastAPI Jinja2/HTML dashboard or minimal static HTML served by FastAPI. No complex React app required for MVP. |
| Database | SQLite local file for MVP. Postgres-ready schema design. |
| Notification | Optional generic webhook and optional Telegram Bot API module. Must be disabled by default unless configured. |
| News source | Manual JSON/CSV event calendar for MVP; live news API later. |
| Telegram signal source | Manual normalized endpoint for MVP; actual scraping/integration later. |

---

## 3. Personas and User Stories

### 3.1 Primary Persona: Discretionary ES/NQ Intraday Trader

A trader already uses TradingView and understands SMC/ICT concepts. They want fewer, cleaner setup alerts and an explanation layer that combines chart context with news risk.

**User stories:**

- As a trader, I want the indicator to identify liquidity sweeps, BOS, FVGs, and SMT divergence so that I do not manually scan every candle.
- As a trader, I want signals paused during consolidation so that I avoid range chop.
- As a trader, I want a final BUY/SELL/NO_TRADE decision with confidence and rationale so that I can quickly filter low-quality setups.
- As a trader, I want news blackouts respected so that I do not receive new entries around high-impact events.
- As a trader, I want to log whether a setup won or lost so that I can evaluate the system honestly.

### 3.2 Secondary Persona: Product Builder / Developer

A developer or Codex Agent needs an unambiguous specification to generate the Pine Script, backend service, schemas, tests, and minimal dashboard.

**User stories:**

- As a developer, I need exact feature definitions so that BOS, FVG, sweep, SMT, and consolidation logic are implemented consistently.
- As a developer, I need JSON schemas so webhook payloads and LLM output can be validated.
- As a developer, I need acceptance criteria so I know when the MVP is complete.

---

## 4. Product Workflow

### 4.1 End-to-End MVP Flow

1. Trader opens ES or NQ chart in TradingView.
2. Trader applies `SMC LLM Candidate Detector` Pine Script.
3. Pine Script calculates chart confluences on confirmed bars.
4. Pine Script displays:
   - diagnostic panel
   - FVG/OB boxes
   - sweep labels
   - SMT labels
   - provisional setup marker
   - provisional entry/SL/TP lines
5. Pine Script calls `alert()` with a JSON payload when a valid setup candidate touches the entry zone.
6. TradingView alert sends webhook to backend endpoint: `POST /webhooks/tradingview`.
7. Backend immediately validates and stores the alert, then returns an acknowledgement quickly.
8. Backend background worker enriches the setup with:
   - active news blackout state
   - latest manually entered news headlines
   - optional Telegram aggregation summary
   - system configuration
9. Backend calls LLM using strict structured output.
10. Backend validates LLM decision deterministically.
11. Final decision is stored.
12. Dashboard and optional notification display the decision.
13. User later records outcome manually or via a future market-data monitor.

### 4.2 Required User-Facing States

| State | Meaning | UI Behavior |
|---|---|---|
| `NO_SETUP` | No valid chart candidate exists. | Diagnostic panel only. |
| `PROVISIONAL_SETUP` | Pine detected setup before LLM review. | Chart marker + local entry/SL/TP preview. |
| `LLM_APPROVED` | Backend LLM approved BUY/SELL. | Dashboard/notification shows trade idea. Optional manual chart overlay. |
| `LLM_REJECTED` | LLM chose NO_TRADE or validator rejected. | Dashboard/notification shows reason. |
| `BLOCKED_CONSOLIDATION` | Chart is consolidating. | Pine suppresses alerts and shows consolidation shading. |
| `BLOCKED_NEWS` | Backend detects high-impact event window. | Backend forces NO_TRADE. |
| `ERROR` | Payload, schema, LLM, or notification failed. | Dashboard shows error and logs details. |

---

## 5. Functional Requirements

### 5.1 TradingView Pine Script Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| TV-001 | Indicator compiles in TradingView | Script compiles without errors in Pine Script v5 or v6. MVP target is v5 unless Codex chooses v6 consistently. |
| TV-002 | Instrument support | Works on `CME_MINI:ES1!` and `CME_MINI:NQ1!`; warns if loaded on another instrument. |
| TV-003 | Companion symbol selection | If chart is ES, companion defaults to NQ. If chart is NQ, companion defaults to ES. User can override. |
| TV-004 | Confirmed-bar logic | Signals and alerts only fire on confirmed bars using `barstate.isconfirmed`. |
| TV-005 | Swing structure | Detect confirmed swing highs/lows using configurable pivot left/right bars. |
| TV-006 | BOS detection | Detect bullish close above last confirmed swing high and bearish close below last confirmed swing low. |
| TV-007 | FVG detection | Detect bullish and bearish FVG zones with configurable minimum gap size. |
| TV-008 | OB fallback | Detect simple order block fallback zone from the last opposite candle before a BOS. |
| TV-009 | Liquidity sweep detection | Detect wick sweep and close back inside prior day high/low, session high/low, or equal high/low pool. |
| TV-010 | SMT divergence | Use `request.security()` to compare ES/NQ rolling highs/lows and mark bullish/bearish SMT divergence. |
| TV-011 | Relative volume | Compute current volume divided by rolling SMA volume; flag thin/neutral/strong. |
| TV-012 | Consolidation filter | Suppress signals when range compression and low directional efficiency are both active. |
| TV-013 | Session context | Identify Asia, London, NY AM, NY PM, and off-hours. Track session highs/lows. |
| TV-014 | Diagnostic panel | Display live state rows for all major confluences. |
| TV-015 | Visual proof markers | Draw visible labels/boxes/lines for BOS, FVG, OB, sweep, SMT, consolidation, and provisional trade levels. |
| TV-016 | Alert JSON | Emit valid JSON through `alert()` when a candidate setup triggers. |
| TV-017 | De-duplication | Do not emit duplicate alerts for the same setup ID. |
| TV-018 | Manual LLM overlay | Optional inputs allow a user to manually paste final LLM action/entry/SL/TP to display on chart. |

### 5.2 Backend Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| BE-001 | FastAPI app | Runs locally with `uvicorn app.main:app --reload`. |
| BE-002 | Health endpoint | `GET /health` returns `{ "status": "ok" }`. |
| BE-003 | TradingView webhook endpoint | `POST /webhooks/tradingview` accepts alert JSON and returns quick acknowledgement. |
| BE-004 | Authentication | Webhook requires shared secret in header `X-Webhook-Secret` or query parameter `secret`. |
| BE-005 | Schema validation | Reject malformed alerts with HTTP 422 or 401 for auth failure. |
| BE-006 | Idempotency | Same `setup_id` cannot create duplicate decision jobs. |
| BE-007 | Queue/background worker | Webhook returns before LLM processing completes; LLM job runs in background. |
| BE-008 | Database persistence | Store setup alerts, LLM decisions, context, errors, prompt version, and outcome fields. |
| BE-009 | LLM call wrapper | Calls an OpenAI-compatible client with strict structured output and timeout handling. |
| BE-010 | Deterministic decision validator | Validates LLM action, confidence, RR, entry/SL/TP ordering, news blackout, and stale setup rules. |
| BE-011 | News blackout handling | Force `NO_TRADE` during high-impact event blackout window. |
| BE-012 | Manual news context | Accept manual news headlines/events via API or JSON file. |
| BE-013 | Telegram context stub | Accept normalized Telegram signal summaries via API, but do not scrape Telegram in MVP. |
| BE-014 | Dashboard | Show recent setups, final decisions, errors, and filtering by symbol/action/status. |
| BE-015 | Notification output | Optional notification module sends approved/rejected decisions to a configured webhook/Telegram bot. |
| BE-016 | Manual outcome recording | API allows user to mark a decision as win/loss/breakeven/ignored with notes. |
| BE-017 | Tests | Pytest suite covers schemas, validation, idempotency, blackout logic, and LLM mock responses. |

### 5.3 LLM Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| LLM-001 | Structured-only output | LLM must return JSON matching `LLMTradeDecision` schema. |
| LLM-002 | No invented chart facts | Prompt instructs model to use only supplied setup data. |
| LLM-003 | Must allow NO_TRADE | LLM must choose `NO_TRADE` when conditions are weak, contradictory, missing, stale, or blocked. |
| LLM-004 | Confidence is not probability | Prompt and UI label confidence as “setup quality score,” not guaranteed win probability. |
| LLM-005 | Safety constraints | LLM must not recommend position size, leverage, account risk, or guaranteed outcomes. |
| LLM-006 | Decision caps | Backend caps/overrides model confidence when blocking conditions exist. |
| LLM-007 | Auditability | Store prompt version, model name, raw input, raw structured output, validator result, and final decision. |

---

## 6. Technical Architecture

### 6.1 Component Diagram

```text
TradingView Chart
  |
  | Pine Script indicator detects SMC features
  | alert() emits JSON
  v
TradingView Webhook
  |
  | HTTP POST
  v
FastAPI Backend
  |-- validates payload
  |-- stores setup
  |-- enriches with news / Telegram context
  |-- queues LLM job
  |-- validates LLM output
  |-- stores final decision
  |
  |--> Dashboard: recent setups + decisions
  |--> Notification: optional Telegram / webhook / console
  |--> Outcome logger: manual win/loss/breakeven
```

### 6.2 Repository Structure for Codex

Codex Agent should create the following repository structure:

```text
smc-llm-trade-validator/
  README.md
  AGENTS.md
  .gitignore
  docs/
    PRD.md
    pine_manual_qa.md
    api.md
    deployment.md
  pine/
    smc_llm_candidate_detector.pine
  backend/
    pyproject.toml
    .env.example
    app/
      __init__.py
      main.py
      config.py
      database.py
      models.py
      schemas.py
      validators.py
      llm_client.py
      llm_prompt.py
      context.py
      notifier.py
      dashboard.py
      seed_data/
        news_events.example.json
    templates/
      index.html
      setup_detail.html
    static/
      app.css
    tests/
      test_schemas.py
      test_webhook_auth.py
      test_decision_validator.py
      test_news_blackout.py
      test_idempotency.py
      test_llm_mock.py
  schemas/
    setup_alert.schema.json
    llm_trade_decision.schema.json
  examples/
    tradingview_webhook_example.json
    llm_decision_buy_example.json
    llm_decision_no_trade_example.json
```

### 6.3 Backend Technology Choices

| Layer | MVP Choice | Reason |
|---|---|---|
| API framework | FastAPI | Fast, typed, simple, Pydantic-native. |
| Validation | Pydantic v2 | Strong schema validation. |
| DB | SQLite via SQLAlchemy | Local MVP simplicity; migratable to Postgres. |
| LLM client | OpenAI-compatible Python client | Structured output support and provider flexibility. |
| Background jobs | FastAPI `BackgroundTasks` for MVP | Simple; upgrade to Celery/RQ later. |
| Dashboard | Jinja2 templates | Low complexity; Codex can build quickly. |
| Tests | pytest | Standard Python testing. |
| Config | `.env` via Pydantic settings | Clear secrets/config management. |

---

## 7. Pine Script Feature Specification

### 7.1 Indicator Metadata

Name: `SMC LLM Candidate Detector`  
Overlay: `true`  
Max labels/boxes/lines: configure high enough for diagnostics but keep cleanup logic to avoid TradingView limits.

Suggested declaration:

```pinescript
//@version=5
indicator("SMC LLM Candidate Detector", overlay=true, max_labels_count=500, max_boxes_count=200, max_lines_count=200)
```

### 7.2 Inputs

| Input | Type | Default | Description |
|---|---:|---:|---|
| `companionSymbol` | string | Auto ES/NQ | Companion instrument for SMT. |
| `pivotLeft` | int | 3 | Left bars for confirmed pivots. |
| `pivotRight` | int | 3 | Right bars for confirmed pivots. |
| `minBreakTicks` | int | 2 | Minimum close beyond structure for BOS. |
| `minFvgTicks` | int | 2 | Minimum FVG gap. |
| `sweepBufferTicks` | int | 1 | Required wick beyond liquidity level. |
| `equalHighLowToleranceTicks` | int | 4 | Max distance for equal highs/lows. |
| `rvolLength` | int | 50 | Relative volume moving average length. |
| `thinVolumeThreshold` | float | 0.70 | Below this, block FVG/OB quality. |
| `strongVolumeThreshold` | float | 1.50 | At/above this, add confluence. |
| `atrLength` | int | 14 | ATR length. |
| `displacementAtrMult` | float | 1.00 | Body size threshold for displacement. |
| `consolidationLookback` | int | 20 | Lookback bars for consolidation. |
| `consolidationAtrMult` | float | 2.00 | Range compression threshold. |
| `directionalEfficiencyMax` | float | 0.30 | Efficiency threshold for consolidation. |
| `setupExpiryBars` | int | 30 | Setup expires after this many bars. |
| `minRR` | float | 1.50 | Minimum risk/reward for candidate alert. |
| `defaultRR` | float | 2.00 | Default TP multiple. |
| `showDiagnostics` | bool | true | Show diagnostic table. |
| `showZones` | bool | true | Show FVG/OB zones. |
| `showProvisionalTrades` | bool | true | Show provisional entry/SL/TP. |
| `enableAlerts` | bool | true | Enable dynamic alert() calls. |
| `manualLlmAction` | string | `NONE` | Optional manual overlay: NONE/BUY/SELL/NO_TRADE. |
| `manualEntry` | float | na | Optional manual LLM entry. |
| `manualSL` | float | na | Optional manual LLM stop. |
| `manualTP` | float | na | Optional manual LLM take-profit. |

### 7.3 Session Definitions

All session calculations should use New York market time.

| Session | Time Range ET | Purpose |
|---|---|---|
| Asia | 18:00–00:00 | Track range that may be swept later. |
| London | 02:00–05:00 | Watch for sweeps/continuation before NY. |
| NY AM | 08:30–11:30 | Primary ES/NQ active setup window. |
| NY PM | 13:30–16:00 | Secondary setup window. |
| Off-hours | All other times | Lower priority; still diagnostic. |

Implementation notes:

- Track current session high/low.
- Store completed session high/low for future sweep detection.
- Track prior day high/low using daily `request.security()` or rolling day logic.

### 7.4 Swing and BOS Detection

**Confirmed swing high:**

```pinescript
ta.pivothigh(high, pivotLeft, pivotRight)
```

**Confirmed swing low:**

```pinescript
ta.pivotlow(low, pivotLeft, pivotRight)
```

Because pivots confirm after `pivotRight` bars, plot markers at `bar_index - pivotRight`.

**Bullish BOS:**

A bullish BOS occurs when:

```text
close > lastConfirmedSwingHigh + minBreakTicks * syminfo.mintick
```

**Bearish BOS:**

A bearish BOS occurs when:

```text
close < lastConfirmedSwingLow - minBreakTicks * syminfo.mintick
```

BOS must be detected only on confirmed bars.

### 7.5 FVG Detection

**Bullish FVG:**

```text
low > high[2]
gapSize = low - high[2]
gapSize >= minFvgTicks * syminfo.mintick
```

Zone boundaries:

```text
zone_low = high[2]
zone_high = low
entry_preferred = midpoint(zone_low, zone_high)
```

**Bearish FVG:**

```text
high < low[2]
gapSize = low[2] - high
gapSize >= minFvgTicks * syminfo.mintick
```

Zone boundaries:

```text
zone_low = high
zone_high = low[2]
entry_preferred = midpoint(zone_low, zone_high)
```

**FVG active state:**

- Active until price fills at least 50% of the gap or until invalidated.
- For MVP, trigger candidate on first retest/touch of the entry zone after creation.
- Expire after `setupExpiryBars` bars.

### 7.6 IFVG Detection

IFVG is included as a diagnostic feature but not required as a candidate trigger in MVP.

**Bullish FVG inversion to bearish IFVG:**

- Existing bullish FVG is fully filled.
- Price closes below the bullish FVG lower boundary.
- The old FVG may become bearish resistance.

**Bearish FVG inversion to bullish IFVG:**

- Existing bearish FVG is fully filled.
- Price closes above the bearish FVG upper boundary.
- The old FVG may become bullish support.

MVP acceptance: mark IFVG state in diagnostic panel if implemented; do not block completion if only FVG is implemented cleanly.

### 7.7 Order Block Fallback

Order block is fallback when FVG is missing or invalid.

**Bullish OB:**

- On bullish BOS, find the most recent bearish candle within the previous 10 bars.
- Zone lower boundary: candle low.
- Zone upper boundary: candle open.
- Invalidate if close below zone low.

**Bearish OB:**

- On bearish BOS, find the most recent bullish candle within previous 10 bars.
- Zone lower boundary: candle open.
- Zone upper boundary: candle high.
- Invalidate if close above zone high.

### 7.8 Liquidity Sweep Detection

Liquidity pools to watch:

1. Prior day high.
2. Prior day low.
3. Completed session high.
4. Completed session low.
5. Equal highs/lows from confirmed pivots.

**Bearish sweep:**

```text
high > watchedHigh + sweepBufferTicks * syminfo.mintick
close < watchedHigh
```

Meaning: price wicked above liquidity, then closed back below.

**Bullish sweep:**

```text
low < watchedLow - sweepBufferTicks * syminfo.mintick
close > watchedLow
```

Meaning: price wicked below liquidity, then closed back above.

**Equal highs/equal lows:**

- Use confirmed pivots.
- Two recent swing highs are equal if absolute difference <= `equalHighLowToleranceTicks * syminfo.mintick`.
- Two recent swing lows are equal if absolute difference <= tolerance.

### 7.9 SMT Divergence: ES vs NQ

MVP uses rolling-window SMT approximation.

Inputs:

- `smtLookback = 20` bars default.
- `companionSymbol`: default auto ES/NQ pair.

Fetch companion highs/lows:

```pinescript
compHigh = request.security(companionSymbol, timeframe.period, high)
compLow  = request.security(companionSymbol, timeframe.period, low)
```

**Bearish SMT:**

```text
current instrument makes a new rolling high over smtLookback
companion instrument does not make a corresponding new rolling high
```

**Bullish SMT:**

```text
current instrument makes a new rolling low over smtLookback
companion instrument does not make a corresponding new rolling low
```

This is not pivot-perfect SMT; it is a documented approximation. Future version can align confirmed pivots between instruments.

### 7.10 Relative Volume

```text
rvol = volume / ta.sma(volume, rvolLength)
```

States:

| State | Condition | Effect |
|---|---|---|
| Thin | `rvol < 0.70` | Blocks FVG/OB candidate quality. |
| Neutral | `0.70 <= rvol < 1.50` | No bonus. |
| Strong | `rvol >= 1.50` | Adds confluence. |

### 7.11 Displacement

Candle body:

```text
body = abs(close - open)
atr = ta.atr(atrLength)
```

**Bullish displacement:**

```text
body >= displacementAtrMult * atr
close > open
close is in top 25% of candle range
```

**Bearish displacement:**

```text
body >= displacementAtrMult * atr
close < open
close is in bottom 25% of candle range
```

### 7.12 Consolidation Detection

Two conditions must both be true:

```text
rangeCompression = (highest(high, lookback) - lowest(low, lookback)) <= consolidationAtrMult * atr
path = sum(abs(close - close[1]), lookback)
directionalEfficiency = abs(close - close[lookback]) / path
lowEfficiency = directionalEfficiency < directionalEfficiencyMax
consolidation = rangeCompression and lowEfficiency
```

If `path == 0`, set `directionalEfficiency = 0`.

During consolidation:

- No candidate alerts.
- No new provisional buy/sell markers.
- Chart background is lightly shaded.
- Diagnostic row shows `BLOCKING`.

### 7.13 Higher-Timeframe Bias

MVP default uses EMA trend filter on a higher timeframe.

Inputs:

- `htfTimeframe = "60"`
- `htfFastEma = 50`
- `htfSlowEma = 200`

**Bullish HTF bias:**

```text
HTF close > HTF EMA50 and HTF EMA50 > HTF EMA200
```

**Bearish HTF bias:**

```text
HTF close < HTF EMA50 and HTF EMA50 < HTF EMA200
```

Otherwise neutral.

### 7.14 Candidate Setup Logic

A candidate setup is eligible only when:

1. Bar is confirmed.
2. Consolidation is false.
3. Volume is not thin for the relevant FVG/OB zone.
4. A valid directional setup exists:
   - bullish setup: bullish sweep or bullish BOS, plus bullish FVG or bullish OB
   - bearish setup: bearish sweep or bearish BOS, plus bearish FVG or bearish OB
5. Price retests/touches the entry zone.
6. Risk/reward to default TP is >= `minRR`.
7. Setup has not already alerted.

Recommended stronger MVP candidate rule:

```text
Bullish candidate requires:
- bullish sweep within last setupExpiryBars OR bullish SMT within last setupExpiryBars
- bullish BOS after that sweep/SMT OR HTF bullish bias
- bullish FVG or bullish OB active
- not consolidation
- rvol >= thinVolumeThreshold
- price touches entry zone

Bearish candidate requires:
- bearish sweep within last setupExpiryBars OR bearish SMT within last setupExpiryBars
- bearish BOS after that sweep/SMT OR HTF bearish bias
- bearish FVG or bearish OB active
- not consolidation
- rvol >= thinVolumeThreshold
- price touches entry zone
```

### 7.15 Provisional Risk Levels

**Bullish:**

```text
entry_low = zone_low
entry_high = zone_high
entry_preferred = midpoint(zone_low, zone_high)
stop_loss = min(sweptLow if exists, zone_low) - stopBufferTicks * mintick
take_profit_1 = entry_preferred + defaultRR * (entry_preferred - stop_loss)
```

**Bearish:**

```text
entry_low = zone_low
entry_high = zone_high
entry_preferred = midpoint(zone_low, zone_high)
stop_loss = max(sweptHigh if exists, zone_high) + stopBufferTicks * mintick
take_profit_1 = entry_preferred - defaultRR * (stop_loss - entry_preferred)
```

### 7.16 Local Rule Score

Pine sends a preliminary `rule_score` to the backend. It is not the final LLM confidence.

| Confluence | Score |
|---|---:|
| Valid direction + zone | +40 |
| Liquidity sweep aligned | +15 |
| BOS aligned | +15 |
| SMT aligned | +15 |
| Strong RVOL | +10 |
| HTF bias aligned | +10 |
| Displacement aligned | +10 |
| S/R proximity aligned | +5 |
| HTF bias opposite | -15 |
| No sweep and no SMT | -10 |
| Thin volume | hard block |
| Consolidation | hard block |

Candidate alert threshold default: `rule_score >= 60`.

### 7.17 Alert Payload

Pine must use dynamic `alert()` rather than only `alertcondition()` so it can emit a dynamic JSON string.

User must create TradingView alert using:

```text
Condition: SMC LLM Candidate Detector → Any alert() function call
Frequency: Once Per Bar Close
Webhook URL: https://your-backend-domain/webhooks/tradingview?secret=YOUR_SECRET
```

Pine should emit a payload matching `SetupAlert` schema.

Required payload fields are defined in Section 10 and the standalone schema file.

---

## 8. Backend API Specification

### 8.1 Environment Variables

Create `.env.example`:

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=sqlite:///./smc_llm.db
WEBHOOK_SECRET=change-me
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20
LLM_CONFIDENCE_APPROVE_THRESHOLD=70
LLM_CONFIDENCE_WATCHLIST_THRESHOLD=55
MAX_SETUP_AGE_MINUTES=15
DEFAULT_BLACKOUT_MINUTES_BEFORE=30
DEFAULT_BLACKOUT_MINUTES_AFTER=30
NOTIFICATION_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ENABLE_NOTIFICATIONS=false
TIMEZONE=America/New_York
```

### 8.2 API Endpoints

#### `GET /health`

Response:

```json
{ "status": "ok" }
```

#### `POST /webhooks/tradingview`

Auth:

- Accept `X-Webhook-Secret` header or `?secret=` query param.
- Reject if missing or invalid.

Behavior:

1. Validate JSON against `SetupAlert` Pydantic model.
2. Create or retrieve setup by `setup_id`.
3. Queue decision job if new.
4. Return acknowledgement immediately.

Response:

```json
{
  "status": "accepted",
  "setup_id": "CME_MINI_ES1_5_2026-07-05T13:45:00Z_12345",
  "duplicate": false
}
```

Duplicate response:

```json
{
  "status": "duplicate",
  "setup_id": "...",
  "duplicate": true
}
```

#### `GET /setups`

Query params:

- `symbol` optional
- `status` optional
- `limit` default 50

Returns list of setup summaries.

#### `GET /setups/{setup_id}`

Returns setup payload, context, LLM decision, validator output, and outcome.

#### `GET /decisions/latest`

Query params:

- `symbol` optional
- `limit` default 20

Returns latest final decisions.

#### `POST /context/news-events`

Create/update high-impact news event.

Input:

```json
{
  "event_id": "FOMC_2026_07_29",
  "title": "FOMC Rate Decision",
  "event_time": "2026-07-29T14:00:00-04:00",
  "impact": "HIGH",
  "symbols": ["ES", "NQ"],
  "blackout_minutes_before": 30,
  "blackout_minutes_after": 30
}
```

#### `POST /context/headlines`

Add manual headline context.

```json
{
  "headline_id": "manual_001",
  "timestamp": "2026-07-05T09:31:00-04:00",
  "headline": "US equities rise after softer inflation print",
  "source": "manual",
  "impact": "MEDIUM",
  "bias": "BULLISH",
  "symbols": ["ES", "NQ"]
}
```

#### `POST /context/telegram-summary`

Accept normalized Telegram aggregation summary. This is a stub; it does not scrape Telegram.

```json
{
  "timestamp": "2026-07-05T09:31:00-04:00",
  "window_minutes": 30,
  "source_count": 5,
  "buy_count": 3,
  "sell_count": 1,
  "neutral_count": 1,
  "dominant_bias": "BULLISH",
  "confidence": 62,
  "summary": "Most tracked channels are leaning long ES after NY open."
}
```

#### `POST /decisions/{setup_id}/outcome`

Manual outcome logging.

```json
{
  "outcome": "WIN",
  "hit_target": "TP1",
  "max_favorable_excursion_points": 10.25,
  "max_adverse_excursion_points": 2.0,
  "notes": "Reached TP1 during NY AM."
}
```

Allowed outcomes:

- `WIN`
- `LOSS`
- `BREAKEVEN`
- `EXPIRED`
- `IGNORED`
- `MANUAL_EXIT`

---

## 9. Database Specification

### 9.1 Tables

#### `setup_alerts`

| Field | Type | Notes |
|---|---|---|
| `id` | integer PK | Internal DB ID. |
| `setup_id` | string unique | Idempotency key from Pine. |
| `received_at` | datetime | Server time. |
| `symbol` | string | ES/NQ chart symbol. |
| `timeframe` | string | TradingView timeframe. |
| `bar_time` | datetime | Source bar timestamp. |
| `direction` | string | BULLISH/BEARISH. |
| `rule_score` | integer | Pine preliminary score. |
| `payload_json` | JSON/text | Full alert payload. |
| `status` | string | ACCEPTED/DUPLICATE/ERROR/PROCESSED. |

#### `llm_decisions`

| Field | Type | Notes |
|---|---|---|
| `id` | integer PK | Internal DB ID. |
| `setup_id` | string FK | Links to setup alert. |
| `created_at` | datetime | Decision time. |
| `model` | string | LLM model used. |
| `prompt_version` | string | Prompt version. |
| `raw_input_json` | JSON/text | Full LLM input. |
| `raw_output_json` | JSON/text | Structured model output. |
| `validator_status` | string | APPROVED/REJECTED/ERROR. |
| `final_action` | string | BUY/SELL/NO_TRADE. |
| `confidence` | integer | Final validated score. |
| `entry_preferred` | float nullable | Final entry. |
| `stop_loss` | float nullable | Final SL. |
| `take_profit_1` | float nullable | Final TP1. |
| `reason_summary` | string | Short explanation. |
| `blocking_conditions_json` | JSON/text | Model + validator blockers. |

#### `news_events`

| Field | Type | Notes |
|---|---|---|
| `event_id` | string PK | Human-readable ID. |
| `title` | string | Event name. |
| `event_time` | datetime | Time with timezone. |
| `impact` | string | LOW/MEDIUM/HIGH. |
| `symbols_json` | JSON/text | Affected symbols. |
| `blackout_minutes_before` | integer | Default 30. |
| `blackout_minutes_after` | integer | Default 30. |

#### `headlines`

| Field | Type | Notes |
|---|---|---|
| `headline_id` | string PK | Manual/source ID. |
| `timestamp` | datetime | Headline time. |
| `headline` | string | Text. |
| `source` | string | manual/API later. |
| `impact` | string | LOW/MEDIUM/HIGH. |
| `bias` | string | BULLISH/BEARISH/NEUTRAL/MIXED. |
| `symbols_json` | JSON/text | Affected symbols. |

#### `telegram_summaries`

| Field | Type | Notes |
|---|---|---|
| `id` | integer PK | Internal ID. |
| `timestamp` | datetime | Summary window end. |
| `window_minutes` | integer | Window size. |
| `source_count` | integer | Number of channels/sources. |
| `buy_count` | integer | Buy calls. |
| `sell_count` | integer | Sell calls. |
| `neutral_count` | integer | Neutral/ignored. |
| `dominant_bias` | string | BULLISH/BEARISH/NEUTRAL/MIXED. |
| `confidence` | integer | 0-100 aggregation score. |
| `summary` | string | Short text summary. |

#### `outcomes`

| Field | Type | Notes |
|---|---|---|
| `id` | integer PK | Internal ID. |
| `setup_id` | string FK | Links to setup. |
| `recorded_at` | datetime | Time outcome saved. |
| `outcome` | string | WIN/LOSS/etc. |
| `hit_target` | string nullable | TP1/TP2/SL/etc. |
| `mfe_points` | float nullable | Max favorable excursion. |
| `mae_points` | float nullable | Max adverse excursion. |
| `notes` | string nullable | User notes. |

---

## 10. JSON Schemas

The standalone package includes these schema files:

- `schemas/setup_alert.schema.json`
- `schemas/llm_trade_decision.schema.json`

### 10.1 SetupAlert Schema Summary

Pine webhook payload must include:

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | yes | `1.0`. |
| `setup_id` | string | yes | Unique idempotency key. |
| `source` | string | yes | `tradingview_pine`. |
| `symbol` | string | yes | Chart symbol. |
| `root_symbol` | string | yes | ES/NQ normalized. |
| `companion_symbol` | string | yes | SMT comparison symbol. |
| `timeframe` | string | yes | Chart timeframe. |
| `bar_time` | string datetime | yes | Bar timestamp. |
| `bar_index` | integer | yes | Pine bar index. |
| `direction` | enum | yes | BULLISH/BEARISH. |
| `rule_score` | integer | yes | Local score 0-100. |
| `price` | number | yes | Current close. |
| `entry` | object | yes | Zone low/high/preferred. |
| `risk` | object | yes | SL, TP1, RR. |
| `features` | object | yes | Detected confluences. |
| `session` | object | yes | Session name and ranges. |
| `diagnostics` | object | yes | Debug values. |

### 10.2 LLMTradeDecision Schema Summary

LLM output must include:

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | yes | `1.0`. |
| `setup_id` | string | yes | Echo setup id. |
| `action` | enum | yes | BUY/SELL/NO_TRADE. |
| `bias` | enum | yes | BULLISH/BEARISH/NEUTRAL. |
| `confidence` | integer | yes | 0-100 setup quality score. |
| `entry` | object | yes | Final entry range/preferred, nullable if no trade. |
| `stop_loss` | number/null | yes | Final SL. |
| `take_profit` | object | yes | TP1/TP2, nullable if no trade. |
| `risk_reward` | number/null | yes | Final RR. |
| `expires_at` | string/null | yes | Decision expiry. |
| `headline_driver` | string | yes | News/context driver or `None`. |
| `reason_summary` | string | yes | Short human-readable explanation. |
| `confluence_notes` | array | yes | Key supporting facts. |
| `blocking_conditions` | array | yes | Reasons for no-trade or caution. |
| `validation_notes` | array | yes | Any assumptions/issues. |
| `requires_human_review` | boolean | yes | True when uncertain or conflicting. |

---

## 11. LLM Decision Layer Specification

### 11.1 LLM Responsibility

The LLM is a **reasoning and classification layer**, not a raw predictor. It must answer:

> Given this already-detected setup and external context, should this setup be treated as BUY, SELL, or NO_TRADE?

The LLM must not be asked:

> Will ES/NQ definitely go up or down?

### 11.2 LLM Input Object

Backend constructs an object:

```json
{
  "schema_version": "1.0",
  "prompt_version": "smc_llm_v1",
  "setup_alert": { "...": "original TradingView payload" },
  "context": {
    "news_blackout_active": false,
    "active_news_events": [],
    "recent_headlines": [],
    "telegram_summary": null,
    "current_time": "2026-07-05T09:45:03-04:00"
  },
  "risk_policy": {
    "min_confidence_for_trade": 70,
    "min_risk_reward": 1.5,
    "max_setup_age_minutes": 15,
    "no_trade_during_blackout": true,
    "no_trade_when_consolidation": true
  }
}
```

### 11.3 System Prompt

Codex must implement the prompt below in `backend/app/llm_prompt.py`.

```text
You are an LLM-powered trade setup reviewer for an ES/NQ Smart Money Concepts indicator.

Your task is to classify a pre-detected trading setup as BUY, SELL, or NO_TRADE using only the structured data provided.

Rules:
1. Do not invent chart facts, news, prices, levels, candles, or signals not present in the input.
2. You are not a broker and must not provide position sizing, leverage advice, account-risk advice, or guarantees.
3. Confidence is a setup-quality score from 0 to 100, not a guaranteed probability of profit.
4. Prefer NO_TRADE when evidence is weak, contradictory, stale, during consolidation, or during high-impact news blackout.
5. A BUY requires bullish chart direction, valid entry, stop below entry, take-profit above entry, and acceptable risk/reward.
6. A SELL requires bearish chart direction, valid entry, stop above entry, take-profit below entry, and acceptable risk/reward.
7. If news_blackout_active is true, action must be NO_TRADE.
8. If setup_alert.features.consolidation.active is true, action must be NO_TRADE.
9. If setup age exceeds risk_policy.max_setup_age_minutes, action must be NO_TRADE.
10. If required fields are missing or inconsistent, action must be NO_TRADE and requires_human_review must be true.
11. Use concise rationale. Do not output markdown. Output only JSON matching the required schema.
```

### 11.4 User Prompt Template

```text
Review this SMC setup and return a structured trading decision.

Input JSON:
{{llm_input_json}}
```

### 11.5 Confidence Guidance

| Confidence | Meaning | Backend Status |
|---:|---|---|
| 0–54 | Weak/blocked/invalid | NO_TRADE |
| 55–69 | Watchlist only | NO_TRADE unless manually reviewed |
| 70–84 | Valid trade idea | Approved if validator passes |
| 85–100 | Strong confluence | Approved if validator passes; still not guaranteed |

### 11.6 Deterministic Validator

After LLM response, backend must validate:

#### Hard rejection conditions

- `news_blackout_active == true`
- setup older than `MAX_SETUP_AGE_MINUTES`
- source setup indicates consolidation active
- malformed output schema
- missing numeric entry/SL/TP for BUY/SELL
- BUY with `stop_loss >= entry.preferred`
- BUY with `take_profit.tp1 <= entry.preferred`
- SELL with `stop_loss <= entry.preferred`
- SELL with `take_profit.tp1 >= entry.preferred`
- `risk_reward < MIN_RR`
- `confidence < LLM_CONFIDENCE_APPROVE_THRESHOLD`
- LLM action conflicts with source setup direction unless LLM chooses `NO_TRADE`

#### Validator output

```json
{
  "validator_status": "APPROVED",
  "final_action": "BUY",
  "final_confidence": 76,
  "rejections": [],
  "warnings": ["Confidence is not calibrated probability."]
}
```

If rejected:

```json
{
  "validator_status": "REJECTED",
  "final_action": "NO_TRADE",
  "final_confidence": 0,
  "rejections": ["News blackout active"],
  "warnings": []
}
```

---

## 12. News and Telegram Context MVP

### 12.1 News Blackout

MVP uses manual event data from:

```text
backend/app/seed_data/news_events.example.json
```

Example:

```json
[
  {
    "event_id": "NFP_2026_08_07",
    "title": "Nonfarm Payrolls",
    "event_time": "2026-08-07T08:30:00-04:00",
    "impact": "HIGH",
    "symbols": ["ES", "NQ"],
    "blackout_minutes_before": 30,
    "blackout_minutes_after": 30
  }
]
```

Backend function:

```text
is_blackout_active(symbol, current_time) -> { active: bool, events: list }
```

Only `impact == HIGH` events force no-trade by default.

### 12.2 News Headlines

MVP supports manual headline insertion. Later versions can integrate a live news API.

Context sent to LLM should include only recent headlines within the last 60 minutes by default.

Fields:

- headline text
- source
- timestamp
- impact
- bias
- affected symbols

### 12.3 Telegram Aggregation Stub

MVP does not scrape Telegram.

It exposes `POST /context/telegram-summary`, allowing a normalized summary to be inserted manually or by a future integration.

Aggregation rules for later implementation:

- Deduplicate repeated calls.
- Weight channels by reliability score.
- Ignore messages older than configured window.
- Normalize calls to BULLISH/BEARISH/NEUTRAL/MIXED.
- Never allow Telegram alone to create a trade. It is context only.

---

## 13. UI / UX Specification

### 13.1 Pine Chart UI

#### Diagnostic table rows

| Row | Values |
|---|---|
| BOS | none / bullish / bearish |
| FVG | none / bullish active / bearish active / mitigated |
| IFVG | none / bullish / bearish |
| OB | none / bullish active / bearish active |
| Session | Asia / London / NY AM / NY PM / off-hours |
| S/R | near support / near resistance / none |
| Sweep | none / bullish / bearish |
| Volume | thin / neutral / strong |
| Consolidation | active blocking / inactive |
| SMT | none / bullish / bearish |
| HTF bias | bullish / bearish / neutral |
| Displacement | bullish / bearish / weak |
| Rule score | 0–100 |

#### On-chart visuals

- Bullish candidate marker: upward label/bubble near entry zone.
- Bearish candidate marker: downward label/bubble near entry zone.
- SL line: horizontal line at provisional stop.
- TP line: horizontal line at provisional target.
- FVG box: translucent zone from FVG boundaries.
- OB box: translucent fallback zone.
- Sweep label: `SWEEP ▲` for bullish, `SWEEP ▼` for bearish.
- SMT label: `SMT ▲` for bullish, `SMT ▼` for bearish.
- Consolidation shading: chart background shaded during active consolidation.

### 13.2 Backend Dashboard

Minimum pages:

#### Home `/`

Shows:

- total setups today
- approved decisions
- rejected/no-trade decisions
- latest 50 setup rows
- filter by symbol/action/status

Columns:

| Column | Description |
|---|---|
| Time | Received time. |
| Symbol | ES/NQ. |
| TF | Timeframe. |
| Direction | Bullish/bearish setup. |
| Rule Score | Pine score. |
| LLM Action | BUY/SELL/NO_TRADE/PENDING/ERROR. |
| Confidence | Final score. |
| Entry | Preferred entry. |
| SL | Stop. |
| TP1 | Target. |
| Reason | Short reason. |
| Status | Approved/rejected/error. |

#### Detail `/setups/{setup_id}`

Shows:

- raw TradingView payload
- enriched context
- LLM output
- validator result
- notification status
- manual outcome form

### 13.3 Notification Format

Approved BUY/SELL example:

```text
SMC LLM Decision: BUY ES 5m
Confidence: 76/100
Entry: 6720.50–6722.00, preferred 6721.25
SL: 6714.75
TP1: 6734.25
RR: 2.0
Reason: Bullish sweep + BOS + FVG retest + SMT confirmation; no blackout.
Setup ID: CME_MINI_ES1_5_20260705T134500Z_12345
```

Rejected example:

```text
SMC LLM Decision: NO_TRADE ES 5m
Reason: High-impact news blackout active until 09:00 ET.
Setup ID: CME_MINI_ES1_5_20260705T082500Z_67890
```

---

## 14. Security, Safety, and Compliance Requirements

### 14.1 Security

- Never put API keys in Pine Script alert payloads.
- Use shared secret for TradingView webhook authentication.
- Do not log API keys or secrets.
- Store `.env` outside version control.
- Validate all inbound JSON.
- Treat TradingView webhooks as untrusted input.
- Do not expose dashboard publicly without authentication in production.

### 14.2 Trading Safety

- MVP is decision support, not investment advice.
- No broker API integration.
- No position sizing.
- No leverage recommendations.
- No claims of guaranteed profitability.
- UI must say: “Confidence is a setup-quality score, not a win probability.”
- LLM output must pass deterministic validator before display as approved.

### 14.3 Failure Modes

| Failure | Expected Behavior |
|---|---|
| Webhook auth fails | Return 401; do not store. |
| Payload invalid | Return 422; log error. |
| Duplicate setup | Return duplicate ack; do not enqueue new LLM job. |
| LLM timeout | Mark decision ERROR; optional retry once. |
| LLM malformed output | Mark rejected/no-trade with validation error. |
| News blackout | Force NO_TRADE. |
| Notification fails | Decision remains stored; dashboard shows notification error. |
| DB unavailable | Return 500; log. |

---

## 15. Testing and QA Plan

### 15.1 Automated Backend Tests

Codex must create pytest tests for:

1. `SetupAlert` schema accepts valid example.
2. `SetupAlert` schema rejects missing critical fields.
3. Webhook rejects invalid secret.
4. Webhook accepts valid secret and stores setup.
5. Duplicate setup is idempotent.
6. News blackout returns active within window.
7. News blackout returns inactive outside window.
8. LLM validator approves valid BUY.
9. LLM validator approves valid SELL.
10. LLM validator rejects BUY with SL above entry.
11. LLM validator rejects SELL with SL below entry.
12. LLM validator rejects low RR.
13. LLM validator forces NO_TRADE during blackout.
14. Mock LLM response is stored.
15. Outcome endpoint records manual outcome.

### 15.2 Pine Manual QA

Create `docs/pine_manual_qa.md` with these test steps:

1. Load ES 5m chart.
2. Paste Pine Script.
3. Confirm it compiles.
4. Confirm diagnostic table appears.
5. Confirm companion symbol defaults to NQ.
6. Scroll historical chart to visible BOS/FVG/sweep examples.
7. Confirm FVG boxes and sweep labels appear.
8. Confirm consolidation shading appears during ranges.
9. Create alert with webhook.
10. Use backend local tunnel or deployed URL.
11. Confirm webhook payload appears in backend logs.
12. Confirm dashboard shows setup.

### 15.3 Integration Test

Use example payload:

```bash
curl -X POST "http://localhost:8000/webhooks/tradingview?secret=change-me" \
  -H "Content-Type: application/json" \
  -d @examples/tradingview_webhook_example.json
```

Expected:

```json
{
  "status": "accepted",
  "duplicate": false
}
```

Then open:

```text
http://localhost:8000/
```

Expected:

- Setup visible.
- Decision eventually visible as approved/rejected/error depending on LLM configuration.

---

## 16. MVP Acceptance Criteria

The MVP is complete when all criteria below pass.

### 16.1 Pine Completion Criteria

- [ ] Pine Script compiles on TradingView.
- [ ] Indicator loads on ES and NQ.
- [ ] Companion symbol is configurable and defaults correctly.
- [ ] Diagnostic panel shows all required rows.
- [ ] BOS, FVG, OB, sweep, SMT, volume, consolidation, HTF bias, and displacement states are calculated.
- [ ] Consolidation suppresses alerts.
- [ ] Candidate marker shows entry/SL/TP preview.
- [ ] `alert()` emits syntactically valid JSON.
- [ ] Duplicate alerts for same setup are suppressed.
- [ ] Manual LLM overlay inputs work if user enters action/entry/SL/TP.

### 16.2 Backend Completion Criteria

- [ ] FastAPI app starts locally.
- [ ] `.env.example` exists.
- [ ] SQLite database initializes automatically.
- [ ] `/health` works.
- [ ] `/webhooks/tradingview` authenticates, validates, stores, and queues setups.
- [ ] Duplicate setup IDs are idempotent.
- [ ] LLM wrapper can be mocked in tests.
- [ ] LLM wrapper can call real provider when API key exists.
- [ ] Structured output is validated.
- [ ] Deterministic validator approves/rejects correctly.
- [ ] News blackout logic forces no-trade.
- [ ] Dashboard lists setups and decisions.
- [ ] Outcome recording works.
- [ ] Pytest suite passes.

### 16.3 Documentation Completion Criteria

- [ ] README includes local setup instructions.
- [ ] README includes TradingView alert configuration steps.
- [ ] README explains that LLM decisions do not automatically repaint the TradingView chart in MVP.
- [ ] API docs include endpoints and example cURL.
- [ ] Pine manual QA guide exists.
- [ ] No secrets are committed.

---

## 17. Future Versions

### 17.1 Version 1.1

- Live economic calendar API integration.
- Telegram channel ingestion with user-provided bot/session credentials.
- Outcome auto-monitor using market data feed.
- Better pivot-aligned SMT detection.
- Backtesting/export tool for historical Pine alerts.
- User authentication for dashboard.

### 17.2 Version 1.2

- Separate TradingView `strategy()` backtest script approximating rule-based entries.
- Confidence calibration from logged outcomes.
- Multi-account user settings.
- Cloud deployment templates.
- Alert routing to Discord/Slack/Telegram.

### 17.3 Version 2.0

- Optional traditional ML model trained from logged setups.
- LLM + ML ensemble.
- Broker execution module only after extensive testing and user safeguards.
- Custom charting web app using TradingView Lightweight Charts or another chart library to show fully automatic LLM overlays.

---

## 18. Codex Agent Build Brief

Copy this section into Codex Agent as the implementation instruction.

```text
Build the MVP repository for “SMC LLM Trade Setup Validator” exactly according to docs/PRD.md.

Core deliverables:
1. Pine Script indicator at pine/smc_llm_candidate_detector.pine.
2. Python FastAPI backend under backend/app.
3. Pydantic schemas for SetupAlert and LLMTradeDecision.
4. JSON schema files under schemas/.
5. Example payloads under examples/.
6. SQLite persistence with SQLAlchemy.
7. Webhook endpoint with shared-secret auth and idempotency.
8. Background LLM decision job.
9. LLM prompt and OpenAI-compatible structured-output client.
10. Deterministic validator that can override unsafe/invalid LLM responses to NO_TRADE.
11. Manual news events/headlines and Telegram summary context endpoints.
12. Minimal dashboard with recent setups/decisions and setup detail page.
13. Manual outcome endpoint and form.
14. Pytest test suite covering schemas, auth, idempotency, blackout, validation, and mock LLM decisions.
15. README, AGENTS.md, API docs, deployment notes, and Pine manual QA guide.

Important constraints:
- Do not implement broker execution or auto-trading.
- Do not implement traditional ML training in MVP.
- Do not claim the system predicts markets with certainty.
- Do not put secrets in code.
- The Pine Script must only emit webhooks and display provisional chart data. The final LLM decision is shown in the backend dashboard/notifications; automatic round-trip plotting inside TradingView is out of scope for MVP.
- Use confirmed bars only for alerts.
- Use dynamic alert() payloads in Pine so TradingView can send JSON to the backend.
- Webhook endpoint should return quickly and process LLM in background.

Run commands expected:
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
uvicorn app.main:app --reload

Done means:
- pytest passes.
- Backend starts.
- Example webhook cURL stores a setup.
- Mock LLM decision is visible on dashboard.
- Pine file is ready to paste into TradingView and compile.
```

---

## 19. Definition of “Complete” for This PRD

This PRD is complete for MVP implementation because it defines:

- Product behavior
- Architecture
- Pine feature logic
- Backend API
- Database tables
- Input/output schemas
- LLM prompts
- Validation rules
- UI requirements
- Test plan
- Acceptance criteria
- Codex Agent instructions

It does not promise a flawless profitable trading system. It specifies a buildable MVP that can be coded, tested, and evaluated honestly.
