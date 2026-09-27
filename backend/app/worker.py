"""Small durable decision queue; receipts survive web-process restarts."""

import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update

from app.config import Settings
from app.database import SessionLocal
from app.models import DecisionJobRecord, SetupAlertRecord
from app.workflow import process_tradingview_alert

logger = logging.getLogger(__name__)


class DecisionWorker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._wake = threading.Event()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="decision-worker", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def notify(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self.thread.join(timeout=5)

    def run_once(self) -> bool:
        now = datetime.now(timezone.utc)
        eligible = or_(
            and_(DecisionJobRecord.status == "QUEUED", DecisionJobRecord.available_at <= now),
            and_(DecisionJobRecord.status == "PROCESSING", DecisionJobRecord.lease_until <= now),
        )
        token = uuid.uuid4().hex
        # Cover the configured provider timeout/retries plus DB and validation work.
        lease_seconds = max(300, self.settings.llm_timeout_seconds * (self.settings.llm_max_retries + 1) + 120)
        with SessionLocal() as db:
            setup_id = db.scalar(select(DecisionJobRecord.setup_id).where(eligible).order_by(
                DecisionJobRecord.available_at, DecisionJobRecord.setup_id,
            ).limit(1))
            if setup_id is None:
                return False
            claimed = db.execute(update(DecisionJobRecord).where(
                DecisionJobRecord.setup_id == setup_id, eligible,
            ).values(status="PROCESSING", lease_token=token,
                     lease_until=now + timedelta(seconds=lease_seconds),
                     attempts=DecisionJobRecord.attempts + 1))
            if claimed.rowcount != 1:
                db.rollback()
                return False
            db.query(SetupAlertRecord).filter_by(setup_id=setup_id).update({"status": "PROCESSING"})
            db.commit()

        try:
            with SessionLocal() as db:
                setup = db.query(SetupAlertRecord).filter_by(setup_id=setup_id).one()
                result = process_tradingview_alert(json.loads(setup.payload_json), db, self.settings, job_token=token)
                if result["duplicate"]:
                    db.query(DecisionJobRecord).filter_by(setup_id=setup_id, lease_token=token).update(
                        {"status": "DONE", "lease_token": None, "lease_until": None, "last_error": None},
                    )
                    db.commit()
            logger.info("decision_job_completed")
        except Exception as exc:
            # Exception strings may contain credentials/SQL; persist only the type.
            logger.error("decision_job_failed error_type=%s", type(exc).__name__)
            with SessionLocal() as db:
                job = db.query(DecisionJobRecord).filter_by(setup_id=setup_id, lease_token=token).first()
                if job is not None:
                    job.status = "FAILED" if job.attempts >= 3 else "QUEUED"
                    job.last_error = type(exc).__name__
                    job.available_at = datetime.now(timezone.utc) + timedelta(seconds=5 * job.attempts)
                    job.lease_until = None
                    job.lease_token = None
                    db.query(SetupAlertRecord).filter_by(setup_id=setup_id).update({"status": job.status})
                    db.commit()
        return True

    def _next_delay(self) -> float:
        # Idle workers sleep between recovery scans so Neon can suspend. A newly
        # committed webhook wakes this process immediately; retries use their due time.
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            jobs = db.execute(select(DecisionJobRecord.status, DecisionJobRecord.available_at,
                                     DecisionJobRecord.lease_until).where(
                DecisionJobRecord.status.in_(["QUEUED", "PROCESSING"]),
            )).all()
        delays = [3600.0]
        for status, available, lease in jobs:
            due = lease if status == "PROCESSING" else available
            if due is not None:
                due = due.replace(tzinfo=timezone.utc) if due.tzinfo is None else due
                delays.append(max(0.1, (due - now).total_seconds()))
        return min(delays)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            try:
                while not self._stop.is_set() and self.run_once():
                    pass
                delay = self._next_delay()
            except Exception as exc:
                logger.error("decision_worker_unavailable error_type=%s", type(exc).__name__)
                delay = 30
            self._wake.wait(timeout=delay)
