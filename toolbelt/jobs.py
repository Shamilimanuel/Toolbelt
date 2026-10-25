"""Long jobs (downloads, cut-outs, conversions) run here, in the background, so the window never freezes.

A tool hands over a function. That function gets the Job and calls job.report(percent, message) as it goes,
and checks job.cancelled now and then so Cancel works. The page asks for the list twice a second.
"""
import itertools
import threading
import time
import traceback


class Cancelled(Exception):
    """Raised by job.check() when the person pressed Cancel."""


class Job:
    def __init__(self, job_id, title, kind):
        self.id = job_id
        self.title = title
        self.kind = kind
        self.progress = 0.0
        self.state = "waiting"           # waiting, running, done, failed, cancelled
        self.message = ""
        self.result = None               # for example the path of the file it made
        self.extra = {}                  # tool-specific details for the page (speed, size, quality, …)
        self.started = time.time()
        self._cancel = threading.Event()

    @property
    def cancelled(self):
        return self._cancel.is_set()

    def check(self):
        if self._cancel.is_set():
            raise Cancelled()

    def report(self, percent, message=""):
        self.progress = max(0.0, min(100.0, float(percent)))
        if message:
            self.message = message

    def as_dict(self):
        return {"id": self.id, "title": self.title, "kind": self.kind, "progress": round(self.progress, 1),
                "state": self.state, "message": self.message, "result": self.result, "extra": dict(self.extra),
                "started": self.started}


class Jobs:
    def __init__(self, at_once=2):
        self._jobs = []
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._slots = threading.Semaphore(at_once)

    def submit(self, title, kind, work, extra=None):
        job = Job(next(self._ids), title, kind)
        job.extra.update(extra or {})
        with self._lock:
            self._jobs.insert(0, job)
        threading.Thread(target=self._run, args=(job, work), daemon=True).start()
        return job

    def _run(self, job, work):
        with self._slots:
            if job.cancelled:
                job.state = "cancelled"
                return
            job.state = "running"
            try:
                job.result = work(job)
                job.progress = 100.0
                job.state = "done"
            except Cancelled:
                job.state = "cancelled"
                job.message = "Cancelled"
            except Exception as error:               # a failed job reports; it never takes the app down
                job.state = "failed"
                job.message = str(error) or error.__class__.__name__
                traceback.print_exc()

    def list(self):
        with self._lock:
            return [job.as_dict() for job in self._jobs]

    def cancel(self, job_id):
        with self._lock:
            for job in self._jobs:
                if job.id == job_id and job.state in ("waiting", "running"):
                    job._cancel.set()
                    if job.state == "waiting":
                        job.state = "cancelled"
                    return {"ok": True, "message": "Cancelling…"}
        return {"ok": False, "message": "That job isn't running."}

    def clear_finished(self):
        with self._lock:
            self._jobs = [job for job in self._jobs if job.state in ("waiting", "running")]
        return {"ok": True, "message": ""}
