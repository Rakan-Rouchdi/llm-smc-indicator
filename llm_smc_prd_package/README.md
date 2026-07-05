# SMC LLM Trade Setup Validator — PRD Package

This package converts the original SMC/ICT TradingView indicator concept into a complete MVP PRD using an LLM-powered reasoning wrapper instead of traditional ML.

Files:

- `PRD.md` — complete build-ready product and technical specification.
- `Codex_Agent_Build_Brief.md` — short implementation brief to paste into Codex.
- `schemas/setup_alert.schema.json` — TradingView webhook payload schema.
- `schemas/llm_trade_decision.schema.json` — strict LLM output schema.
- `examples/tradingview_webhook_example.json` — sample alert payload.
- `examples/llm_decision_buy_example.json` — sample approved decision.
- `examples/llm_decision_no_trade_example.json` — sample rejected/no-trade decision.

Important MVP limitation: TradingView alerts can send data outward to a backend, but the backend's LLM response does not automatically repaint the TradingView chart. The final decision is displayed in the backend dashboard/notifications; Pine displays provisional chart data.
