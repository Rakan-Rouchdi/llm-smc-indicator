# Mobile And Forward-Testing Validation

## Mobile Checks

Headless Chrome through Playwright, actual verified `window.innerWidth` values
320, 390, 768 and 1440px, height 844px. This replaces the earlier failed viewport
override; it does not claim physical iPhone/Safari verification.

Found and fixed: long setup IDs in the detail header caused page width 388px on
a 320px viewport. Header wrapping/minimum sizing fixed; command touch targets
are at least 44px tall. Existing wide history tables scroll inside their own
container, not the page. The design detector's generic border-padding warnings
were reviewed against screenshots; existing key/value rows have 8px bottom
padding and were not redesigned.

Tested dashboard, detail and forward ledger at all four sizes for both approved
and stale-news local scenarios: 24 route/viewport checks, no page overflow or
uncaught JavaScript errors. News-stale rendering remains blocked. The synthetic
review form was expanded, populated and submitted to an intercepted 422 response
at all four widths; the error appears, values remain, and retry is enabled.
The form presentation fixture contains a deliberately long ID and never changes
stored eligibility, calls OpenAI, sends a webhook or writes a market outcome.
Backend acceptance, rejection, authentication and append-only writes are tested
separately with isolated pytest databases.

Screenshots (synthetic data only):

- `screenshots/mobile_2026_11_13/390-dashboard.png`
- `screenshots/mobile_2026_11_13/320-4.png`
- `screenshots/mobile_2026_11_13/390-review-form.png`

Run the local preview using `backend/scripts/preview_mvp.py`, then run:

```sh
node backend/scripts/check_mobile_dashboard.cjs http://127.0.0.1:8014 /tmp/smc-mobile-check
```

The helper requires Playwright available to Node and installed Google Chrome.
This check used the existing bundled Playwright through NODE_PATH; no production
dependency or browser was installed. An optional fourth argument supplies a
Jinja-rendered synthetic ledger HTML fixture to exercise the review form.
The helper refuses non-loopback base hosts and blocks external browser requests.

## Forward Tracking

See `forward_testing.md` for the fixed cohort, daily workflow, timing semantics,
manual evidence rules, API and rollback. New append-only review and notification
attempt tables are additive. News policy, credential files, alert configuration,
Pine logic and trade/broker functions were not changed or used.

Baseline: 273 tests passed. Expanded suite: 291 passed, 0 failed, with the
existing Starlette/httpx deprecation warning.
All previews used disposable SQLite, mock LLM, no .env loading and no outbound
notifications. UI success is not evidence of a new natural market signal.

Deployment is a separate approval step. These checks validate the local changed
application; they do not claim the hosted service contains this code before a
successful approved deployment and hosted route verification.
