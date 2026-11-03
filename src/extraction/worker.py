"""The background worker that reads queued documents.

Purpose: reading a page takes a minute or two on a CPU, so the web request only stores the file
    and queues a job; this thread picks the job up and records the result. It starts with the API
    (src/api/main.py) and stops with it. `CREDLENS_OCR_WORKER=0` leaves it off (tests); a job that
    was running when the server stopped is put back in the queue at start-up.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 10).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.db import models as db
from src.extraction.engine import get_engine
from src.extraction.service import next_queued, process_job

log = logging.getLogger(__name__)


class OcrWorker:
    def __init__(self, engine: Engine, config: dict[str, Any]) -> None:
        self.engine, self.config = engine, config
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="credlens-ocr", daemon=True)

    def start(self) -> None:
        with Session(self.engine) as session:  # a crash left a job "running": run it again
            session.execute(
                update(db.ExtractionJob)
                .where(db.ExtractionJob.status == "running")
                .values(status="queued")
            )
            session.commit()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        poll = float(self.config["ocr"]["poll_seconds"])
        while not self._stop.wait(poll):
            try:
                with Session(self.engine) as session:
                    job_id = next_queued(session)
                    if job_id is not None:
                        process_job(session, self.config, get_engine(self.config), job_id)
            except Exception:  # noqa: BLE001 - the worker must keep running
                log.exception("The reading worker hit an error")


def maybe_start(engine: Engine, config: dict[str, Any]) -> OcrWorker | None:
    if os.environ.get("CREDLENS_OCR_WORKER", "1").strip() == "0":
        return None
    worker = OcrWorker(engine, config)
    worker.start()
    return worker
