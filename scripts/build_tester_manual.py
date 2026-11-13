"""Build the versioned, secret-free private tester handbook. Requires reportlab."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    Flowable, KeepTogether,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/SMC_LLM_Private_Tester_Manual.pdf"
INK = colors.HexColor("#20272B")
TEAL = colors.HexColor("#006D68")
MUTED = colors.HexColor("#536169")
LIGHT = colors.HexColor("#EFF4F3")
LINE = colors.HexColor("#D5DEDE")
WARN = colors.HexColor("#9B402E")
WIDTH = A4[0] - 92

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
if (FONT_DIR / "Arial.ttf").exists():
    for name, filename in (("Manual", "Arial.ttf"), ("ManualBold", "Arial Bold.ttf"),
                           ("ManualItalic", "Arial Italic.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
    pdfmetrics.registerFontFamily("Manual", normal="Manual", bold="ManualBold", italic="ManualItalic")
    BASE, BOLD, ITALIC = "Manual", "ManualBold", "ManualItalic"
else:
    BASE, BOLD, ITALIC = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyManual", fontName=BASE, fontSize=10.2, leading=14.2,
                          textColor=INK, spaceAfter=8))
styles.add(ParagraphStyle(name="SmallManual", parent=styles["BodyManual"], fontSize=8.8, leading=12, spaceAfter=6))
styles.add(ParagraphStyle(name="TableManual", parent=styles["BodyManual"], fontSize=9.1, leading=12.2, spaceAfter=0))
styles.add(ParagraphStyle(name="TableHeadManual", parent=styles["TableManual"], fontName=BOLD,
                          textColor=colors.white))
styles.add(ParagraphStyle(name="SectionManual", fontName=BOLD, fontSize=24, leading=28,
                          textColor=INK, spaceAfter=12))
styles.add(ParagraphStyle(name="SubManual", fontName=BOLD, fontSize=12, leading=16,
                          textColor=TEAL, spaceBefore=9, spaceAfter=6))
styles.add(ParagraphStyle(name="KickerManual", fontName=BOLD, fontSize=9, leading=12,
                          textColor=TEAL, spaceAfter=9))
styles.add(ParagraphStyle(name="TitleManual", fontName=BOLD, fontSize=34, leading=38,
                          textColor=INK, spaceAfter=16))
styles.add(ParagraphStyle(name="CodeManual", fontName="Courier", fontSize=8.1, leading=11,
                          textColor=INK, spaceAfter=4))


def p(text, style="BodyManual"):
    return Paragraph(text, styles[style])


def table(headers, rows, fractions, small=False):
    data = [[p(escape(h), "TableHeadManual") for h in headers]]
    data += [[p(cell, "SmallManual" if small else "TableManual") for cell in row] for row in rows]
    result = Table(data, colWidths=[WIDTH * f for f in fractions], hAlign="LEFT", repeatRows=1, spaceAfter=8)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, -1), (-1, -1), .5, LINE),
    ]))
    return result


def callout(title, body, warning=False):
    color = WARN if warning else TEAL
    result = Table([[p(title, "SubManual")], [p(body)]], colWidths=[WIDTH])
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF1EE") if warning else LIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
    ]))
    return KeepTogether([Spacer(1, 7), result, Spacer(1, 9)])


def bullets(items):
    return [p("<b>%s.</b> %s" % (i, text)) for i, text in enumerate(items, 1)]


def code(lines):
    return Table([[p(escape(line).replace(" ", "&#160;"), "CodeManual")] for line in lines],
                 colWidths=[WIDTH], spaceAfter=6, style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                     ("LEFTPADDING", (0, 0), (-1, -1), 10),
                     ("TOPPADDING", (0, 0), (-1, -1), 3),
                     ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                 ]))


class Pipeline(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 240

    def draw(self):
        c = self.canv
        stages = [
            ("1  TradingView / Pine", "Confirmed chart conditions create a provisional candidate."),
            ("2  Authenticated webhook", "Backend validates and stores the receipt and durable job."),
            ("3  Safety checks + structured LLM review", "Fresh news and deterministic gates can reject before reasoning."),
            ("4  Final validation + storage", "BUY / SELL / NO_TRADE; invalid model output cannot bypass rules."),
            ("5  Dashboard + approved private notification", "A decision-support record, never an order or a broker fill."),
        ]
        for i, (title, description) in enumerate(stages):
            y = 240 - (i + 1) * 47
            c.setFillColor(LIGHT)
            c.rect(0, y, WIDTH, 43, fill=1, stroke=0)
            c.setFillColor(TEAL)
            c.rect(0, y, 3, 43, fill=1, stroke=0)
            c.setFont(BOLD, 10.4)
            c.setFillColor(INK)
            c.drawString(13, y + 27, title)
            c.setFont(BASE, 9)
            c.drawString(13, y + 11, description)
            if i < 4:
                c.setStrokeColor(TEAL)
                c.line(WIDTH / 2, y - 1, WIDTH / 2, y - 7)


story = []
sections = []


def page(kicker, title):
    if story:
        story.append(PageBreak())
    sections.append(title)
    story.extend([p(kicker.upper(), "KickerManual"), p(title, "SectionManual")])


page("Private beta / tester handbook", "SMC LLM Trade Setup Validator")
story[-1] = p("SMC LLM<br/>Trade Setup Validator", "TitleManual")
story += [p("How it works. What to watch. What not to assume.", "SubManual"),
          p("Handbook 1.0 | 13 November 2026<br/>Backend package 0.3.0 | Policy strict_v1 | Detector timing_sessions_v2", "SmallManual"),
          Spacer(1, 12),
          callout("Ready for controlled testing - not a finished commercial product",
                  "The core chart-to-backend workflow is implemented, deployed and tested. "
                  "Not every original PRD item is complete. There is no established trading edge, "
                  "calibrated win probability, customer account system or paid-product readiness."),
          p("This guide is for a friend testing the interface, signal explanations, delivery and paper outcomes. "
            "It is not a trading strategy recommendation. Do not place trades as part of this test."),
          table(["Read first", "Then use as a reference"], [
              ["2  Safe handoff and quick start<br/>3  System and dependencies<br/>4  Chart installation", "5-8  Chart legend, rules, settings and timing"],
              ["9  Read the dashboard<br/>10  News and notifications<br/>11  Automatic paper outcomes", "12  Test routine and feedback<br/>13  Troubleshooting"],
              ["14  Owner-only alert operations<br/>15  Market-closed local preview", "16  Completion boundaries and sources"],
          ], [.5, .5]),
          p("<b>In plain English:</b> SMC means Smart Money Concepts; LLM means large language model. "
            "ES is the E-mini S&amp;P 500 future; NQ is the E-mini Nasdaq-100 future. "
            "This tool combines programmed chart-pattern checks with an AI review, not a trained price-prediction model.", "SmallManual"),
          Spacer(1, 5),
          p("<b>The three distinctions that prevent most mistakes</b>", "SubManual"),
          p("A chart <b>CANDIDATE</b> is not a final approval. A backend <b>APPROVED</b> decision is not an order. "
            "A paper <b>WIN</b> is not realized profit."),
          p("Evidence snapshot: 321 backend tests passed; real price-feed delivery and private Telegram transport "
            "were verified on 13 November. This handbook does not certify future uptime or future market results.", "SmallManual"),
          p("Share this PDF without credentials. The service address, passwords, API keys, webhook secret and "
            "private chat identifiers are deliberately omitted.", "SmallManual")]

page("01 / Start here", "Safe handoff and quick start")
story += [callout("Do not share the owner's operator login",
                 "The MVP has shared HTTP Basic authentication, not individual read-only tester accounts. "
                 "Those credentials also authorize management/review APIs. Use supervised viewing, a local demo, "
                 "or a separately configured tester instance. A PDF alone does not provision safe customer access.", True),
          table(["Testing mode", "What your friend needs"], [
              ["Chart only", "Their own TradingView account, the owner-provided Pine file, and access to the agreed ES/NQ feed. "
               "No backend keys, webhook secret or OpenAI account required. Leave JSON alerts off in this personal chart copy."],
              ["Hosted workflow review", "Owner-supervised dashboard access, or an isolated instance with its own credentials and data. "
               "The existing Telegram bot sends only to the owner's configured private chat."],
              ["Local UI demo", "Repository, Python 3.11+, installed backend dependencies and the isolated preview command on page 15. "
               "No market session or paid API call is needed."],
          ], [.25, .75]),
          p("Your first 10 minutes", "SubManual")]
story += bullets([
    "Agree that this is observation-only testing. Choose chart-only, supervised or isolated mode before receiving access.",
    "For comparison with the live cohort, open the exact delayed NQ continuous contract and a standard 4h candlestick chart. "
    "The current source is CME_MINI_DL:NQ1!; do not substitute a CFD, micro contract or a different data entitlement.",
    "Add the detector and keep its default rules. Use Compact panel, candidate price labels on, debug zones/markers off, test mode off.",
    "Read Gate, Candle and HTF. WAIT / No setup is a valid state. A historical label is not a current instruction.",
    "In the supervised dashboard, check current readiness, news status and timestamps before reading the latest decision. "
    "Open Forward testing to see eligibility, delivery timings and paper outcome evidence.",
    "Record questions with the exact symbol, timeframe, UTC time and a redacted screenshot. Do not create or change a production alert.",
])
story += [p("Before handoff, the owner supplies the approved script version, access method, test start/end date and "
            "where to send feedback. Credentials must be exchanged separately through an appropriate private channel.", "SmallManual")]

page("02 / Architecture", "What the system actually does")
story += [Pipeline(), p("A second, data-only path follows the prices", "SubManual"),
          p("The separate SMC Paper Price Feed sends completed 1m NQ bars in 5m batches. The backend stores these bars "
            "and compares eligible final decisions with later prices. This path does not call the LLM or produce trading signals."),
          table(["Component", "Current role / dependency"], [
              ["TradingView + Pine v6", "Live chart detection and server-side alerts. Current candidate alert: NQ 4h. Separate price-feed alert: NQ 5m. "
               "A webhook-capable plan, enabled 2FA and available alert slots are needed to operate alerts [S1-S2]."],
              ["Render + Neon", "Hosted FastAPI worker/dashboard plus persistent PostgreSQL. Local development uses SQLite. "
               "Free hosting/database wake-up and quotas remain operational risks [S3-S4]."],
              ["OpenAI", "Live structured reviewer: gpt-4o-mini. Owner-managed API credentials and credits. "
               "Failure provenance is stored; fallback cannot become a live approved push."],
              ["ShowMyTrades calendar", "Live scheduled USD-event coverage, refreshed every 15 minutes while the backend runs. "
               "Not a comprehensive breaking-news or headline service."],
              ["Telegram", "Live outgoing final-approved notification transport. Incoming sentiment/summary context remains mocked."],
              ["Uptime monitor", "Optional health checks. A green /health check proves neither alert delivery nor signal accuracy."],
          ], [.25, .75], small=True),
          p("The Mac can be closed once hosted alerts are configured. TradingView, Render, Neon and external services must remain available. "
            "This is not entirely free: TradingView entitlements and live OpenAI usage can cost money; quotas/pricing may change.", "SmallManual")]

page("03 / Chart setup", "Install and open the detector")
story += [p("For a personal chart-only copy; do not alter the live owner layout or its alerts.", "SmallManual")]
story += bullets([
    "Get the owner-approved file pine/smc_llm_candidate_detector.pine. In TradingView, open Pine Editor, create a new indicator, "
    "paste the complete source, save it with a distinct personal name, and Add to chart. Report any compiler error rather than patching rules ad hoc.",
    "Use standard time-based candles. Validated detector combinations are ES and NQ on 5m, 15m, 1h and 4h. "
    "For the current live test, use NQ 4h. Charts validated elsewhere do not have active backend alerts automatically.",
    "Check the exact feed and delayed-data badge with the owner. ES pairs with NQ and NQ with ES. "
    "Leave Companion symbol override blank unless a coordinated feed change is explicitly agreed.",
    "In indicator settings, use Panel mode = Compact; Show diagnostic table = on; Show candidate price labels = on. "
    "Keep Show FVG zones and Show proof markers off initially.",
    "Keep Enable test webhook alert = off. For your chart-only copy, turn Enable alert() JSON payloads off. "
    "The owner's production copy keeps JSON enabled. A Pine toggle alone does not create a TradingView alert [S1].",
    "Allow data to load. If Gate says 1m data incomplete or Companion data, capture it with the symbol and time. "
    "Do not lower data-quality checks to remove the message.",
])
story += [callout("A chart change is not an alert update",
                 "TradingView alerts run a saved snapshot of code, inputs, symbol and timeframe. Changing the visible chart "
                 "does not update an existing server-side alert. Only the owner should perform an approved replacement [S1]."),
          table(["Use", "Do not substitute"], [
              ["ES / NQ futures, agreed exact data feed", "MES/MNQ, broker CFDs, SPY/QQQ, gold, crypto or arbitrary correlated symbols"],
              ["Standard candles; supported interval", "Heikin Ashi, Renko or other synthetic prices for evaluation"],
              ["Agreed price adjustments / session settings", "Unannounced back-adjustment or settlement-price changes"],
          ], [.5, .5]),
          p("XAUUSD is not supported. A gold chart is not a valid way to make this ES/NQ workflow generate weekend signals. "
            "Use the isolated preview for market-closed UI tests.", "SmallManual")]

page("04 / Chart legend", "Read the panel, not just the color")
story += [table(["Compact panel row", "Meaning / what to do"], [
    ["SMC strict_v1", "WAIT means no current eligible candidate; BULLISH/BEARISH identifies a provisional candidate direction."],
    ["Gate", "The first blocking reason, or PASS. Read the reason before treating the score as meaningful. "
     "PASS is a Pine rule result, not backend/news approval."],
    ["Candle", "OPEN / PREVIEW may change before close. CLOSED means the chart candle is confirmed. "
     "Only confirmed realtime closing bars can emit new natural alerts."],
    ["Score", "X/100 with a separate minimum of 75. No setup means no active directional FVG; it is not a frozen score."],
    ["HTF", "Completed higher-timeframe bias. A 4h chart normally uses D (daily), not the unfinished daily candle."],
    ["Session (1m)", "Session of the latest completed minute used in this chart bar. It is not necessarily the wall-clock session at delivery."],
    ["Setups / 100 bars", "Recent qualifying setup count in loaded chart history. Not delivered webhooks, filled trades, wins or a complete backtest."],
    ["News / final decision", "Backend only. Pine cannot see live news approval, final LLM results, Telegram success or backend readiness."],
], [.3, .7]),
          p("Chart visuals", "SubManual"),
          table(["Visual", "Interpretation"], [
              ["BUY CANDIDATE / SELL CANDIDATE", "Provisional direction with Entry, SL, TP and RR. Not a fill or final approval. "
               "Old labels remain historical even if the current panel is WAIT."],
              ["Gray background", "Consolidation pause. Two confirmed clear bars are required before release."],
              ["FVG box (optional)", "Gap zone. Retired boxes may say MITIGATED, INVALIDATED, EXPIRED or SUPERSEDED. "
               "Only one active zone is tracked; not every historical zone remains eligible."],
              ["BOS / SWEEP / SMT labels (optional)", "Debug evidence markers, not separate entry signals. Older drawings are pruned. "
               "Obstructive entry/SL/TP line trails were intentionally removed."],
          ], [.3, .7]),
          p("In Diagnostics mode, ages such as 3b mean three chart bars. READY means eligible for that feature; "
            "EXPIRED means too old. The current label ORDER BLOCK means event-order/sequence blocked, <b>not</b> an order-block zone. "
            "That wording is a known clarity limitation.", "SmallManual")]

page("05 / Detection policy", "What must line up for a candidate")
story += [p("The rules are an explicit approximation of SMC concepts, not a claim that every discretionary trader "
            "would label the same pattern. A high score cannot override a hard block."),
          table(["Feature", "Implemented definition"], [
              ["BOS", "Break of Structure: a confirmed close crosses a buffered last confirmed swing high/low. Default pivots need three bars on either side."],
              ["FVG + retest", "Fair Value Gap: a three-candle gap at least two ticks wide. A later candle overlaps the still-valid zone. "
               "A close beyond the far edge invalidates it; midpoint mitigation retires it after candidate evaluation."],
              ["Liquidity sweep", "Wick beyond a watched pool, then close back inside. Pools use prior-day, completed-session or equal-pivot levels; "
               "the current priority is equal-pivot, then session, then prior-day."],
              ["SMT", "ES/NQ rolling 20-bar high/low non-confirmation with aligned companion timestamps. "
               "This is not full pivot-matched SMT."],
              ["Relative volume", "Volume / 50-bar average. Below 0.70 is THIN and blocks; 1.50 or higher is STRONG."],
              ["Consolidation", "20-bar range compression AND low directional efficiency, with two confirmed clear bars before release."],
              ["HTF / displacement", "HTF close and EMA 50/200 alignment use completed HTF bars. Displacement adds score for a large directional body "
               "with a close near that candle's extreme."],
          ], [.23, .77], small=True),
          p("Required sequence", "SubManual"),
          p("Aligned sweep <b>or</b> SMT must occur no later than BOS. FVG forms on the BOS bar or within two bars after it; "
            "retest occurs later. BOS/liquidity evidence must remain within the configured six-bar limit. "
            "The companion and completed 1m session data must be available; HTF must agree; consolidation and thin volume must be absent."),
          table(["Confirmation", "Points", "Confirmation", "Points"], [
              ["Aligned active FVG", "25", "Aligned recent BOS", "20"],
              ["Aligned sweep", "10", "Aligned SMT", "10"],
              ["Aligned HTF", "15", "Strong RVOL", "10"],
              ["Aligned displacement", "10", "Maximum / minimum", "100 / 75"],
          ], [.35, .15, .35, .15]),
          p("Valid risk geometry and at least 1.5 RR are also required. One candidate is emitted per tracked FVG. "
            "Strict NQ 4h filtering can be quiet for days; low frequency alone proves neither quality nor failure.", "SmallManual"),
          p("<b>Other terms:</b> HTF = higher timeframe; EMA = exponential moving average; ATR = average true range; "
            "RVOL = relative volume; tick = the instrument's minimum price increment. SMT here means paired-market non-confirmation.", "SmallManual")]

page("06 / Settings reference", "Keep the baseline fixed during testing")
story += [p("Changing settings changes the experiment. Record any owner-approved variant separately; do not compare mixed settings "
            "as if they were one performance sample. These are baseline values, not optimized recommendations."),
          table(["Input group", "Baseline", "Why it matters"], [
              ["Companion / pivots", "Auto pair; left 3 / right 3", "Controls structure confirmation and associated delay."],
              ["BOS / FVG minimum", "2 / 2 ticks", "Requires a buffered break and a minimum gap size."],
              ["Sweep / equal-level tolerance", "1 / 4 ticks", "Sets wick clearance and equal-pivot matching."],
              ["SMT lookback", "20 bars", "Rolling-window comparison, not pivot matching."],
              ["RVOL", "50 bars; 0.70 thin; 1.50 strong", "Thin volume blocks; strong volume adds score."],
              ["ATR / displacement", "ATR 14; body 1.0 ATR", "Measures movement magnitude; directional close is also required."],
              ["Consolidation", "20 bars; range 2.0 ATR; efficiency &lt; 0.30", "Both compression and low efficiency trigger the pause."],
              ["HTF input / EMA", "60; EMA 50 / 200", "Auto-escalates when 60m is not above the chart. See page 8."],
              ["Zone expiry", "30 chart bars", "Maximum FVG age, not the LLM decision's entry expiry."],
              ["Rule score / confirmation age", "75 minimum / 6 bars", "Hard gates still apply even above the score threshold."],
              ["Risk levels", "Minimum RR 1.50; target 2.0R; stop buffer 2 ticks", "Entry is FVG midpoint; stop uses zone/sweep extreme plus buffer. "
               "Target is algebraic, not proof of reachable liquidity."],
              ["Display", "Compact; labels on; zones/proof markers off", "Switch Diagnostics on temporarily when reporting a blocker."],
              ["Alert inputs", "Owner JSON on; test mode off", "Friend's chart-only copy: JSON off. Never enable production test mode to force activity."],
          ], [.28, .26, .46], small=True),
          callout("Rule score and model confidence are different",
                 "The rule score counts deterministic confirmations. The LLM's setup-quality score is a model assessment. "
                 "Neither is a measured probability of winning. Backend baseline confidence threshold is 70; "
                 "it does not waive news, freshness, direction or risk checks."),
          p("<b>Levels and RR:</b> Entry = proposed observation price; SL = stop-loss level; TP1 = first take-profit level. "
            "RR is reward distance / risk distance. Synthetic BUY example: entry 100, SL 95, TP1 110 gives 10/5 = 2.0 RR. "
            "It is arithmetic, not a forecast or an instruction to trade.", "SmallManual")]

page("07 / Time and sessions", "Why signals arrive later than a wick")
story += [table(["Source of delay", "What to expect"], [
              ["Market-data entitlement", "The current NQ source is delayed. First price-feed verification showed a ten-minute difference "
               "between market bar close and emission. Check the actual timestamp; do not assume every delay is ten minutes."],
              ["Pivot confirmation", "Three right bars must finish before a pivot is confirmed. On 4h this is three chart bars, "
               "not three minutes; market breaks can lengthen wall-clock time."],
              ["Confirmed chart / HTF", "Candidates wait for the chart close; HTF bias uses a completed HTF candle. "
               "These are intentional information delays, not rendering bugs."],
              ["Network, hosting, model", "Webhook transport, database/worker scheduling and LLM processing add separate delay. "
               "A green health check does not prove a timely decision."],
          ], [.3, .7]),
          p("Effective higher timeframe with the default 60m input", "SubManual"),
          table(["Chart", "5m", "15m", "1h", "4h"], [["HTF used", "1h", "1h", "4h", "Daily"]], [.28, .18, .18, .18, .18]),
          p("Session labels use America/New_York", "SubManual"),
          table(["Label", "New York local-time window"], [
              ["ASIA", "18:00 to 00:00"], ["LONDON", "02:00 to 05:00"],
              ["NY_AM", "08:30 to 11:30"], ["NY_PM", "13:30 to 16:00"],
              ["OFF_HOURS", "All other minutes; not by itself a news blackout or a closed-market declaration."],
          ], [.28, .72]),
          p("These are implementation-defined context windows, not exchange opening hours or universal session definitions. "
            "Daylight saving is handled with New York timestamps; do not hard-code a London/UTC offset. "
            "A 4h candle can span multiple windows. Session (1m) follows the latest completed included minute.", "SmallManual"),
          p("The backend uses the <b>actual candle-close time</b>, including shortened final candles, and normally rejects setup age over 15 minutes. "
            "Its stored timestamps use UTC. News and delivery times should be compared in one timezone.", "SmallManual"),
          callout("No zero-lag claim", "Confirmed bars reduce known timing/repainting problems. They do not make historical markings "
                 "equivalent to tradable realtime opportunities, or establish complete historical/live equivalence.")]

page("08 / Dashboard", "Read current status before the latest decision")
story += [p("Open the owner-provided HTTPS dashboard in a browser. Do not open backend/templates/index.html directly: "
            "it is a server template, not a running dashboard. Refresh the page to get a new snapshot."),
          table(["Area / field", "What it tells you"], [
              ["Armed (operator-verified)", "Combined readiness based partly on an operator's TradingView observation. "
               "Not a live poll or a promise that the next webhook will arrive."],
              ["Worker / failed jobs / oldest pending", "Processing health. A stuck queue or STOPPED worker needs owner investigation even when /health is green."],
              ["TradingView alert / last checked", "ACTIVE, expired/inactive or UNKNOWN observation. Observations become stale after the configured age "
               "(normally 24h); UNKNOWN is not proof the alert was deleted."],
              ["News coverage / calendar refresh", "Current ES/NQ safety state, source publication time, last fetch, failures and next attempt. "
               "Compare freshness, not just a recent download."],
              ["Latest Setup / Source", "Symbol, interval, received/open/close times, SMC facts and CHART CANDIDATE or DELIVERY TEST. "
               "The dashboard is a received-setup ledger, not a continuously streaming chart."],
              ["Latest Decision", "Model, time, raw LLM Action and <b>Final Action</b>. Final action plus validator result is authoritative. "
               "PENDING means unfinished processing, not approval."],
              ["Entry (unfilled), SL, TP1, RR", "Proposed levels, not an executed position. Use the final stored decision for paper evaluation, "
               "not older provisional Pine levels."],
              ["Historical warning", "The newest stored decision may be old. It must not be read as a new entry signal merely because it is displayed first."],
              ["Recorded News Context", "Snapshot associated with that setup, not necessarily today's live news. "
               "It can legitimately differ from current coverage at the top."],
              ["Setup History / raw payloads", "Open a row for context, validation and delivery evidence. Raw data is for auditing, not another recommendation."],
          ], [.32, .68], small=True),
          p("Navigation", "SubManual"),
          p("<b>Health</b>: public process liveness. <b>Processing Status</b>: authenticated operational JSON. "
            "<b>Forward testing</b>: eligible/excluded receipts, timing, automatic outcomes and manual annotations. "
            "Main history shows 25 recent setups; it is not the entire database."),
          p("For example: LLM Action BUY with Final Action NO_TRADE / REJECTED means the validator blocked the model. "
            "Do not ignore the final result because the raw response looked positive.", "SmallManual")]

page("09 / Safety and notifications", "News and the LLM are separate gates")
story += [table(["Current news state", "Meaning"], [
              ["CLEAR", "A source-validated, in-window calendar is fresh and no configured blackout is active. "
               "This does not mean all possible market risks are absent."],
              ["BLACKOUT", "A configured scheduled event window blocks final approval. The current adapter blocks HIGH/MEDIUM "
               "events and Fed-labelled appearances, normally 30 minutes before and after."],
              ["UNKNOWN / unavailable / stale", "Required coverage cannot be trusted. Approvals remain blocked. "
               "Never turn off the gate or renew an old timestamp to manufacture CLEAR."],
          ], [.3, .7]),
          p("What the news feed does and does not cover", "SubManual"),
          p("The free ShowMyTrades scheduled USD calendar refreshes every 15 minutes while the service runs. "
            "Publication freshness is capped at two hours. A failed fetch retains the old snapshot but does not renew it. "
            "The backend checks news before/after reasoning and again before notification."),
          p("Source validation checks format, time and declared coverage; it is not independent verification of every event. "
            "Unscheduled headlines, incomplete publisher data and broader systemic risk are not comprehensively covered."),
          p("How the LLM is constrained", "SubManual"),
          p("The live reviewer receives structured chart facts and supplied context, not vague chart screenshots. "
            "It returns strict JSON: BUY, SELL or NO_TRADE, quality score, explanation and proposed levels. "
            "Schema checks and deterministic rules can override it. OpenAI failure or mock fallback is held as NO_TRADE "
            "in the live OpenAI-requested workflow; it cannot become a live final push."),
          table(["Notification you see", "Interpretation"], [
              ["TradingView app / toast", "Provisional Pine candidate. Backend news or validation may still reject it."],
              ["Private Telegram BUY / SELL", "Final approved, fresh, non-test, non-fallback decision passed send-time news checks. "
               "Still unfilled decision support, not a trade instruction."],
              ["SMC NOTIFICATION DELIVERY TEST", "Transport diagnostic only. No setup, approval, order or performance observation."],
              ["SENT / UNKNOWN / FAILED", "SENT is API acceptance, not phone reading. UNKNOWN requires reconciliation; do not blindly resend. "
               "Failure does not erase the stored decision."],
          ], [.34, .66], small=True),
          p("Telegram sentiment context is still mock data, even though outgoing bot delivery is live. The bot is configured "
            "for one private recipient; starting it from your friend's account does not subscribe them automatically.", "SmallManual")]

page("10 / Outcomes", "Automatic tracking without invented wins")
story += [p("The live NQ feed batches the latest 20 completed 1m bars at each 5m close. The repair buffer can fill some short delivery gaps. "
            "It is delayed market evidence, not broker execution data. No LLM call is used to decide a paper outcome."),
          table(["Result", "Evidence required"], [
              ["WIN", "Eligible final decision; post-decision preferred-entry price touch; then TP1 before SL with unambiguous minute evidence."],
              ["LOSS", "Post-decision entry touch; then SL before TP1 with unambiguous minute evidence."],
              ["EXPIRED", "Continuous evidence of no entry touch before a known decision expiry. Missing data cannot prove expiry."],
              ["UNKNOWN", "Missing/ambiguous prices, both exits touched in one bar, uncertain entry sequence, unmatched price anchor, "
               "contract change, invalid/missing timing, conflicting bars or an unresolved path."],
          ], [.22, .78]),
          p("Conservative rules worth knowing", "SubManual")]
story += bullets([
    "Only current-cohort, current-revision, approved live-provider BUY/SELL decisions qualify. Tests, rejected decisions and "
    "mock/fallback records are excluded. The cohort began 13 November 2026 at 17:10:12 UTC.",
    "The exact setup-close minute and price must match the feed. Continuous same-contract data is required through the relevant path. "
    "Session breaks and outages may leave UNKNOWN rather than a guessed result.",
    "A minute's low/high must span the final preferred entry price, not just any part of its zone. Entry is considered only after "
    "the recorded decision time and before decision expiry. Earlier price movement is not credited "
    "as an achievable entry. Boundary-straddling minutes that touch relevant levels remain ambiguous.",
    "Entry and exit within one minute are UNKNOWN unless entry is exactly that complete post-decision bar's open. "
    "If both SL and TP1 are touched, sequence is still UNKNOWN.",
    "An entered observation is followed for at most 24 hours from the decision. The evaluator considers the newest 500 decisions "
    "created within 72 hours; it does not reconstruct older weeks without price evidence.",
])
story += [p("Where to see it", "SubManual"),
          p("Forward testing shows Automatic paper outcome, Automatic evidence and a separate Manual annotation. "
            "Manual corrections append evidence; they do not overwrite the automatic audit. UNRECORDED in the manual field "
            "does not mean automatic tracking has failed."),
          callout("Paper result is not realized P&amp;L", "OHLC range touches do not prove fills, tick ordering, fees, spread, slippage or "
                 "profitability. Keep UNKNOWN results visible; do not exclude them to inflate performance. NQ is the only active price feed.")]

page("11 / Test routine", "What your friend should actually test")
story += [p("Before each session", "SubManual")]
story += bullets([
    "Confirm the agreed exact chart/feed, timeframe and baseline settings. Note delayed data and the timezone used in screenshots.",
    "Check worker, queue, news publication/freshness and alert observation/expiry. The owner checks actual TradingView alert logs when needed.",
    "Check automatic feed status. RECEIVING means recent stored bars; STALE_OR_MARKET_CLOSED needs context, "
    "not an automatic conclusion that the market or server is broken.",
])
story += [p("When a candidate appears", "SubManual")]
story += bullets([
    "Capture the candidate label and Compact/Diagnostics state with the symbol, interval and candle-close time. "
    "Note whether you saw it live or only in history.",
    "Match its setup ID/time to the dashboard receipt and TradingView alert log. Compare LLM action, final action and rejection reason. "
    "A chart label alone does not prove a webhook was sent.",
    "For an approved result, check the private notification and automatic outcome evidence. Record missing or late delivery, "
    "but do not place an order or mark a historical pre-decision touch as a fill.",
])
story += [p("Weekly review", "SubManual"),
          p("Review all receipts, exclusions, rejections, delivery failures, delay distributions and UNKNOWN outcomes. "
            "Keep test records separate. Compare like-for-like settings and data feeds. Do not optimize the rules after each isolated win/loss."),
          table(["Feedback record", "Fill in"], [
              ["Observed at (UTC)", "Date/time; live observation or historical review"],
              ["Environment", "Exact symbol/feed, interval, device/browser, script/policy version"],
              ["Reference", "Setup ID or relevant candle close; no credentials or webhook URL"],
              ["Expected / actual", "What you expected, what the panel/dashboard/log actually showed"],
              ["Evidence", "Redacted chart + dashboard screenshots; timing and reproduction steps"],
              ["Impact", "Visual confusion, missing candidate, delivery failure, unsafe approval, or uncertain outcome"],
          ], [.3, .7], small=True),
          p("Stop using a result for evaluation and notify the owner immediately if stale news permits approval, a test/fallback "
            "is pushed as live, prices appear future-dated or the same setup produces duplicate notifications.", "SmallManual")]

page("12 / Troubleshooting", "Quiet is not the same as broken")
story += [table(["Symptom", "Check first", "Safe response"], [
              ["No candidate for days", "Gate reason, 100-bar count, confirmed bars, active alert and expiry", "Strict NQ 4h can be sparse. "
               "Investigate evidence; do not lower thresholds just to get alerts."],
              ["No setup / score empty", "Active FVG lifecycle", "Expected without a directional active zone. It is not automatically a calculation freeze."],
              ["1m data incomplete", "Loaded intrabar history and gaps", "Wait/reload ordinary chart data or report it. Do not synthesize missing minutes."],
              ["Companion data", "Exact companion, entitlement and timestamps", "Owner checks alignment. Do not substitute another symbol without validation."],
              ["Chart candidate, no final BUY/SELL", "Webhook log, processing job, news, validator", "Read the final reason. Pine does not know backend news and may remain bullish after rejection."],
              ["Webhook failed / timed out", "TradingView delivery status and matching stored setup", "Report promptly. A timeout can occur even after storage. "
               "Owner reconciles before any retry; no duplicate alert."],
              ["Couldn't find domain", "Saved alert destination", "Owner checks for a stale tunnel/domain. Use the approved stable HTTPS host, not an old quick-tunnel URL."],
              ["401 or 503 dashboard", "Credentials / server auth configuration", "Ask owner privately. Do not disable production authentication or use raw template files."],
              ["News UNKNOWN or HTTP 429", "Publication age, refresh error, next retry", "Leave approvals blocked. Do not change freshness dates or hammer the publisher."],
              ["PENDING / failed job", "Worker, database, oldest pending", "Owner investigates status/logs; never replay old setups as fresh signals."],
              ["No Telegram message", "Final eligibility, outbox, expiry, news and recipient", "Only approved fresh decisions are pushed. SENT is not proof of phone receipt; UNKNOWN needs review."],
              ["Paper outcome UNKNOWN", "Automatic evidence reason, coverage and contract", "This is often the correct conservative result. Provide evidence, not a guessed WIN/LOSS."],
              ["Latest decision is old", "Received and decided times, historical banner", "Expected when no new receipt exists. Refresh; do not treat the old result as current."],
          ], [.25, .29, .46], small=True),
          p("Escalate with redacted evidence and UTC timestamps. Never send passwords, API keys, tokens, query secrets "
            "or full private webhook URLs in screenshots, chat, support tickets or Git commits.", "SmallManual")]

page("13 / Owner operations", "Two alerts, with different jobs")
story += [p("Reference configuration only. Reading this manual is not permission to create, replace or duplicate live alerts. "
            "A friend should not attach new alerts to the owner's endpoint."),
          table(["Setting", "Candidate alert", "Data-only price alert"], [
              ["Name", "SMC LLM Candidate Detector webhook", "SMC Paper Price Feed NQ"],
              ["Symbol / interval", "CME_MINI_DL:NQ1! / 4h", "CME_MINI_DL:NQ1! / 5m"],
              ["Indicator", "SMC LLM Candidate Detector", "SMC Paper Price Feed"],
              ["Condition", "Any alert() function call", "Any alert() function call"],
              ["Inputs", "JSON on; test off; score 75", "Feed on; ID nq-paper-v1"],
              ["Message", "Script-generated JSON", "Script-generated JSON; last 20 completed 1m bars"],
              ["Webhook path", "/webhooks/tradingview", "/webhooks/tradingview/prices"],
              ["Notifications", "App + toast + webhook", "Webhook only"],
              ["Expiry", "7 Jan 2027, 18:00 UTC", "7 Jan 2027, 18:00 UTC"],
          ], [.21, .395, .395], small=True),
          p("Both use the existing HTTPS backend and a privately configured secret. No static JSON, password or API key belongs in Pine. "
            "TradingView requires 2FA for webhooks; plan/alert limits must be checked in the account [S2]."),
          p("Owner checks after an approved change", "SubManual")]
story += bullets([
    "Verify the actual editor/script identity, compiled source, inputs, symbol and interval. A prior MCP tab-routing issue targeted "
    "the wrong editor; it was restored. Do not assume a tab-switch response proves the write target.",
    "Inspect saved alert snapshots, expiry and destination privately. Keep one candidate alert plus one data-only feed. "
    "The live candidate snapshot remains revision 19; the restored editor revision number is not a rule change.",
    "Confirm real delivery in the TradingView log and corresponding stored receipt or price-bar timestamp. "
    "A manual HTTP probe is not proof of TradingView-origin delivery.",
])
story += [p("Public /health checks only liveness. Authenticated /status, /decisions/latest, /notifications and "
            "/dashboard/forward-testing give different evidence. The price feed does not increment the candidate receipt count. "
            "Arrange alert renewal before expiry; no automatic renewal is implemented.", "SmallManual")]

page("14 / Safe offline practice", "Test the interface when markets are closed")
story += [p("Use the isolated preview. It creates synthetic fixtures in disposable SQLite, ignores .env files, "
            "uses mock reasoning, keeps verified-news test gates enabled and disables outbound workers/notifications. "
            "It does not change production, send TradingView alerts or use an OpenAI key."),
          p("Dependencies for local testers", "SubManual"),
          p("Get the owner-approved repository, Python 3.11 or newer and a terminal. The backend installs FastAPI, Uvicorn, "
            "Pydantic, SQLAlchemy, Jinja2, JSON Schema validation, psycopg, HTTP clients and the OpenAI SDK. "
            "The SDK being installed does not mean the preview calls OpenAI. No Node.js, broker or tunnel is needed."),
          p("One-time setup (macOS/Linux; from the repository root)", "SubManual"),
          code(["python3 -m venv backend/.venv", "backend/.venv/bin/python -m pip install -e './backend[dev]'"]),
          Spacer(1, 9),
          p("Start an approved-looking synthetic UI case", "SubManual"),
          code(["backend/.venv/bin/python backend/scripts/preview_mvp.py \\", "  --port 8012 --scenario approved"]),
          p("Open <b>http://127.0.0.1:8012/dashboard</b>. Stop with Ctrl-C. If the port is occupied, choose another unused local "
            "port. On Windows, use the corresponding backend\\.venv\\Scripts\\python.exe path.", "SmallManual"),
          table(["Scenario", "Expected demonstration"], [
              ["approved", "Synthetic approved BUY display; explicitly a DELIVERY TEST, not a market result."],
              ["blackout", "NO_TRADE with blackout refusal."],
              ["stale", "NO_TRADE / unknown news, not confirmed ready."],
              ["gold", "Unsupported XAUUSD rejected; not gold signal support."],
          ], [.25, .75]),
          p("Repeat the command with another --scenario value. History includes all four fixtures. "
            "The local preview is intentionally not armed and is unauthenticated on loopback only. "
            "Never publish it through a tunnel or deploy it as a public dashboard.", "SmallManual"),
          p("Optional developer regression check", "SubManual"),
          code(["cd backend", ".venv/bin/python -m pytest -q"]),
          callout("What this proves", "UI, schema and rule behavior can be exercised with markets closed. "
                 "A chart reload, historical drawing or local demo does not prove real webhook delivery, notification delivery or profitability.")]

page("15 / Release boundaries", "What is complete, and what is not")
story += [table(["Status", "Honest assessment"], [
              ["Implemented and exercised", "Pine detection/diagnostics on ES/NQ 5m, 15m, 1h, 4h; authenticated webhook and durable jobs; "
               "live structured OpenAI review; deterministic validation; persistent storage; protected dashboard; scheduled-news fail-closed gates; "
               "private Telegram transport; mobile checks; automatic NQ paper-outcome infrastructure."],
              ["Live operational evidence", "321 tests pass. Real price-feed webhook delivered on 13 Nov at 19:40 UTC; backend stored it at 19:40:02. "
               "Private Telegram diagnostic was received on the phone. These are delivery/code checks, not market-performance proof."],
              ["Partial or not implemented", "Order-block fallback is NONE; no IFVG detector or manual final-decision Pine overlay. "
               "SMT is rolling-window, not pivot-aligned. Telegram sentiment is mocked; no normalized summary ingestion workflow is connected. "
               "No comprehensive live headline feed. Gold and broad asset support are absent."],
              ["Not finished as a product", "No independent tester accounts/read-only roles, multi-tenant isolation, customer billing/licensing or self-service onboarding. "
               "Dashboard is basic, without the full original PRD filtering interface. Hosting reliability and recovery still need production hardening."],
              ["Not proven", "A representative forward sample, complete natural candidate-to-final-push cycle for the current cohort, "
               "real eligible paper WIN/LOSS behavior over time, calibrated confidence, realistic execution costs or profitability."],
          ], [.25, .75], small=True),
          p("Release decision", "SubManual"),
          p("<b>Yes:</b> a usable, controlled private-testing MVP. <b>No:</b> every original PRD requirement completed, "
            "a validated signal service, or a finished product ready for paying customers. Before wider release, finish safe tester access, "
            "run representative forward evaluation, harden monitoring/backups/availability, reconcile remaining scope and review "
            "provider data rights and applicable distribution requirements."),
          p("References and evidence", "SubManual"),
          p("Implementation: pine/smc_llm_candidate_detector.pine; backend/app/eligibility.py, validators.py, outcome_engine.py; "
            "docs/automatic_paper_outcomes.md, automatic_outcome_activation.md, private_telegram_activation_2026_11_13.md, "
            "forward_testing.md, automatic_news_calendar.md, closed_market_testing.md. The July PRD is the baseline; "
            "the dated rollout documents explain subsequent scope changes.", "SmallManual"),
          p('[S1] <link href="https://www.tradingview.com/pine-script-docs/faq/alerts/" color="#006D68">TradingView: alerts and saved snapshots</link><br/>'
            '[S2] <link href="https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/" color="#006D68">TradingView: webhooks, 2FA, delivery status and timeouts</link><br/>'
            '[S3] <link href="https://render.com/docs/free" color="#006D68">Render: free-service limits and idle behavior</link><br/>'
            '[S4] <link href="https://neon.com/docs/introduction/compute-lifecycle" color="#006D68">Neon: compute suspension and activation</link>', "SmallManual"),
          p("External documentation checked 13 November 2026. Operating status is a dated snapshot, not continuous certification. "
            "No service address or credential is embedded in this handbook.", "SmallManual")]


def decoration(canvas, doc):
    canvas.saveState()
    if doc.page <= len(sections):
        bookmark = f"section-{doc.page}"
        canvas.bookmarkPage(bookmark)
        canvas.addOutlineEntry(sections[doc.page - 1], bookmark, level=0, closed=False)
    canvas.setTitle("SMC LLM Trade Setup Validator - Private Tester Manual")
    canvas.setAuthor("SMC LLM MVP Project")
    canvas.setSubject("Private paper-testing handbook; decision support only")
    canvas.setFillColor(MUTED)
    canvas.setFont(BOLD, 8)
    canvas.drawString(46, A4[1] - 29, "SMC / PRIVATE TESTER HANDBOOK")
    canvas.setStrokeColor(LINE)
    canvas.line(46, 39, A4[0] - 46, 39)
    canvas.setFont(BASE, 7.5)
    canvas.drawString(46, 26, "13 NOV 2026  |  PAPER TESTING ONLY  |  NO ORDERS")
    canvas.drawRightString(A4[0] - 46, 26, f"{doc.page:02d} / 16")
    canvas.restoreState()


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=46, rightMargin=46,
                            topMargin=58, bottomMargin=52, title="SMC LLM Private Tester Manual",
                            author="SMC LLM MVP Project", pageCompression=1)
    doc.build(story, onFirstPage=decoration, onLaterPages=decoration)
    print(OUTPUT)


if __name__ == "__main__":
    main()
