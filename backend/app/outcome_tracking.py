"""Authenticated price evidence and automatic paper outcomes, isolated from approvals."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.delivery import _object
from app.models import AutoOutcomeRecord, LLMDecisionRecord, PriceBarRecord, SetupAlertRecord
from app.news import utc
from app.outcome_engine import PriceBar, PriceBatch, evaluate_paper_path


def store_price_batch(db, batch: PriceBatch, settings, now):
    if not settings.outcome_tracking_enabled or not settings.outcome_feed_id:
        raise ValueError("OUTCOME_FEED_DISABLED")
    if batch.feed_id != settings.outcome_feed_id or batch.symbol != settings.outcome_feed_symbol:
        raise ValueError("FEED_ID_OR_SYMBOL_MISMATCH")
    if not now-timedelta(minutes=90) <= batch.emitted_at <= now+timedelta(seconds=5):
        raise ValueError("EMISSION_TIME_OUT_OF_RANGE")
    if any(b.close_time > now or b.open_time < now-timedelta(hours=48) for b in batch.bars):
        raise ValueError("BAR_TIME_OUT_OF_RANGE")
    existing = {utc(r.open_time): r for r in db.query(PriceBarRecord).filter(
        PriceBarRecord.feed_id == batch.feed_id, PriceBarRecord.symbol == batch.symbol,
        PriceBarRecord.open_time.in_([b.open_time for b in batch.bars])).all()}
    added, conflicts = 0, 0
    for b in batch.bars:
        raw = b.model_dump_json()
        row = existing.get(b.open_time)
        if row is None:
            db.add(PriceBarRecord(feed_id=batch.feed_id, symbol=batch.symbol, open_time=b.open_time,
                close_time=b.close_time, received_at=now, updated_at=now, payload_json=raw))
            added += 1
        elif PriceBar.model_validate_json(row.payload_json) != b:
            # Never silently overwrite a previously observed price. Preserve both versions.
            if row.conflict_json is None:
                row.conflict_json, row.updated_at = raw, now
            conflicts += 1
    db.commit()
    return {"status": "accepted", "added": added, "conflicts": conflicts}


def latest_automatic(db, ids):
    records = {}
    if ids:
        for row in db.query(AutoOutcomeRecord).filter(AutoOutcomeRecord.decision_id.in_(ids)).order_by(
                AutoOutcomeRecord.data_version.desc(), AutoOutcomeRecord.evaluated_at.desc(), AutoOutcomeRecord.id.desc()):
            records.setdefault(row.decision_id, {**_object(row.result_json), "evaluated_at": utc(row.evaluated_at).isoformat(),
                "evidence_hash": row.evidence_hash})
    return records


def outcome_feed_status(db, settings):
    row = db.query(PriceBarRecord).filter_by(feed_id=settings.outcome_feed_id,
        symbol=settings.outcome_feed_symbol).order_by(PriceBarRecord.close_time.desc()).first()
    now = datetime.now(timezone.utc)
    status = "DISABLED" if not settings.outcome_tracking_enabled or not settings.outcome_feed_id else "WAITING_FOR_FEED"
    if status != "DISABLED" and row:
        status = "RECEIVING" if now-utc(row.close_time) <= timedelta(minutes=30) else "STALE_OR_MARKET_CLOSED"
    return {"status": status, "symbol": settings.outcome_feed_symbol,
        "latest_bar_close": utc(row.close_time).isoformat() if row else None,
        "last_received": utc(row.received_at).isoformat() if row else None,
        "scope": "Newest 500 decisions created in the last 72 hours; paper OHLC observations, not fills"}


def evaluate_outcomes_once(settings, now=None):
    if not settings.outcome_tracking_enabled or not settings.outcome_feed_id:
        return 0
    # Import lazily: the ledger uses this module for display, not for approval decisions.
    from app.forward_testing import cohort_reason
    now = now or datetime.now(timezone.utc)
    added = 0
    with SessionLocal() as db:
        decisions = db.query(LLMDecisionRecord).filter(LLMDecisionRecord.created_at >= now-timedelta(hours=72)).order_by(
            LLMDecisionRecord.created_at.desc(), LLMDecisionRecord.id.desc()).limit(500).all()
        previous = latest_automatic(db, [d.id for d in decisions])
        for d in decisions:
            s = db.query(SetupAlertRecord).filter_by(setup_id=d.setup_id).one_or_none()
            if not s or cohort_reason(s, d) != "ELIGIBLE_PAPER_REVIEW":
                continue
            payload = _object(s.payload_json)
            decided = utc(d.created_at)
            bars = []
            rows = []
            result = {"outcome": "UNKNOWN", "reason": "MISSING_TIMING", "paper_only": True}
            try:
                anchor_time = datetime.fromisoformat(payload["diagnostics"]["bar_close_time"])
                expiry = datetime.fromisoformat(_object(d.raw_output_json)["expires_at"])
                if anchor_time.tzinfo is None or expiry.tzinfo is None:
                    raise ValueError("Timezone required")
                if anchor_time < decided-timedelta(hours=48):
                    raise ValueError("Anchor outside retained evaluation window")
                rows = db.query(PriceBarRecord).filter(PriceBarRecord.feed_id == settings.outcome_feed_id,
                    PriceBarRecord.symbol == s.symbol, PriceBarRecord.close_time >= anchor_time,
                    PriceBarRecord.open_time < decided+timedelta(hours=24)).order_by(PriceBarRecord.open_time).all()
                bars = [PriceBar.model_validate_json(r.payload_json) for r in rows]
                if s.symbol != settings.outcome_feed_symbol:
                    result["reason"] = "FEED_SYMBOL_MISMATCH"
                elif any(r.conflict_json for r in rows):
                    result["reason"] = "CONFLICTING_PRICE_EVIDENCE"
                else:
                    result = evaluate_paper_path(action=d.final_action, entry=d.entry_preferred,
                        stop=d.stop_loss, target=d.take_profit_1, decided_at=decided, expires_at=expiry,
                        anchor_time=anchor_time, anchor_price=payload.get("price"), bars=bars, now=now)
            except (ValueError, KeyError, TypeError, OverflowError):
                pass
            result.update(feed_id=settings.outcome_feed_id, feed_symbol=s.symbol, bar_count=len(bars),
                decided_at=decided.isoformat(), entry=d.entry_preferred, stop_loss=d.stop_loss,
                take_profit_1=d.take_profit_1, action=d.final_action,
                expires_at=_object(d.raw_output_json).get("expires_at"),
                anchor_time=payload.get("diagnostics", {}).get("bar_close_time"), anchor_price=payload.get("price"),
                first_bar_close=bars[0].close_time.isoformat() if bars else None,
                last_bar_close=bars[-1].close_time.isoformat() if bars else None,
                bar_evidence_sha256=hashlib.sha256("".join(r.payload_json+(r.conflict_json or "") for r in rows).encode()).hexdigest(),
                method="conservative_1m_ohlc_v1", source_confirmation="WEBHOOK_AUTH_ONLY")
            raw = json.dumps(result, sort_keys=True)
            fingerprint = hashlib.sha256(raw.encode()).hexdigest()
            if previous.get(d.id, {}).get("evidence_hash") == fingerprint:
                continue
            if db.query(AutoOutcomeRecord.id).filter_by(decision_id=d.id, evidence_hash=fingerprint).first():
                continue
            data_version = max((utc(r.updated_at) for r in rows), default=decided)
            # New evidence outranks older evaluations even if two worker instances overlap.
            db.add(AutoOutcomeRecord(decision_id=d.id, evaluated_at=now, data_version=data_version,
                evidence_hash=fingerprint, result_json=raw))
            try:
                db.commit()
                added += 1
            except IntegrityError:
                db.rollback()  # Another worker recorded the same immutable evidence.
    return added
