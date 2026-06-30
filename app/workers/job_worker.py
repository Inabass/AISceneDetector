import logging
import threading
from collections.abc import Callable
from time import monotonic

from app.db.session import SessionLocal
from app.repositories.job_repository import JobRepository
from app.services.feature_service import run_training_feature_job
from app.services.job_service import JobService

logger = logging.getLogger(__name__)
JobExecutor = Callable[[int], None]


class JobWorker:
    def __init__(self, poll_interval_sec: float = 1.0) -> None:
        self.poll_interval_sec = poll_interval_sec
        self.executors: dict[str, JobExecutor] = {
            "training_feature_extraction": run_training_feature_job,
        }
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="aisd-job-worker", daemon=True)
        self._thread.start()
        logger.info("Job worker started")

    def stop(self, timeout_sec: float = 10.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout_sec)
        logger.info("Job worker stopped")

    def _run_loop(self) -> None:
        self._recover_interrupted_jobs()
        while not self._stop_event.is_set():
            ran_job = self._run_one_job()
            if not ran_job:
                self._stop_event.wait(self.poll_interval_sec)

    def _recover_interrupted_jobs(self) -> None:
        db = SessionLocal()
        try:
            recovered = JobService(db).recover_interrupted_jobs()
            if recovered:
                logger.warning("Recovered %s interrupted jobs at worker startup", recovered)
        finally:
            db.close()

    def _run_one_job(self) -> bool:
        db = SessionLocal()
        try:
            job = JobRepository(db).get_next_queued(set(self.executors))
            if job is None:
                return False
            job_id = job.id
            job_type = job.type
        finally:
            db.close()

        executor = self.executors[job_type]
        logger.info("Starting queued job %s (%s)", job_id, job_type)
        started = monotonic()
        executor(job_id)
        logger.info("Finished queued job %s (%s) in %.2fs", job_id, job_type, monotonic() - started)
        return True
