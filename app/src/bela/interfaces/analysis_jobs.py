"""Bounded, cancellable background analysis for the local dashboard."""

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Event, RLock, Thread
from uuid import uuid4

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.storage.analysis_log import save_analysis


class AnalysisBusy(ValueError):
    pass


@dataclass
class _Job:
    id: str
    source: tuple
    cancel: Event = field(default_factory=Event)
    done: bool = False
    result: dict | None = None
    error: str | None = None
    log_path: str | None = None


class AnalysisJobs:
    def __init__(self, journal_directory=None):
        self._journal_directory = journal_directory
        self._lock = RLock()
        self._jobs = OrderedDict()
        self._active = None

    def start(self, match, config, *, source=None, journal_context=None):
        # Fail incomplete/out-of-turn inputs before creating a worker.
        if match.state.phase.value != "playing" or match.state.next_player != match.state.setup.player:
            raise ValueError("Move analysis requires your turn in an unfinished deal.")
        with self._lock:
            if self._active is not None and not self._active.done:
                raise AnalysisBusy("An analysis is still stopping. Try again shortly.")
            job = _Job(str(uuid4()), source or (match.id, match.revision, len(match.deals)))
            self._jobs[job.id] = self._active = job
            while len(self._jobs) > 8:
                self._jobs.popitem(last=False)

            def run():
                try:
                    result = analyze_moves(match, config, expected_revision=match.revision,
                                           cancelled=job.cancel.is_set)
                    path = save_analysis(match, result, directory=self._journal_directory,
                                         **{"source": "dashboard", "job_id": job.id,
                                            **(journal_context or {})})
                    with self._lock:
                        job.result = result
                        job.log_path = str(path)
                except OSError as error:
                    with self._lock:
                        job.error = f"Could not preserve analysis diagnostics: {error}"
                except ValueError as error:
                    with self._lock:
                        job.error = str(error)
                except Exception:
                    with self._lock:
                        job.error = "Analysis failed unexpectedly. Please restart the analysis."
                finally:
                    with self._lock:
                        job.done = True

            Thread(target=run, daemon=True, name="bela-analysis").start()
            return job.id

    def invalidate(self):
        with self._lock:
            if self._active is not None and not self._active.done:
                self._active.cancel.set()

    def cancel(self, job_id):
        with self._lock:
            self._get(job_id).cancel.set()

    def _get(self, job_id):
        if not isinstance(job_id, str) or job_id not in self._jobs:
            raise ValueError("Analysis not found.")
        return self._jobs[job_id]

    def view(self, job_id, source):
        with self._lock:
            job = self._get(job_id)
            stale = job.source != source
            status = "stale" if stale else "failed" if job.error else "finished" if job.done else (
                "cancelling" if job.cancel.is_set() else "running")
            return {"id": job.id, "match_id": job.source[0], "revision": job.source[1],
                    "deal_number": job.source[2], "state": status,
                    "result": job.result if job.done and not stale and not job.error else None,
                    "error": job.error if not stale else None, "analysis_log": job.log_path}


def interactive_config(data):
    required = {"samples", "seconds", "seed", "policy", "objective"}
    optional = {"self_policy", "learning_samples", "exact_endgame"}
    if not isinstance(data, dict) or not required <= set(data) or set(data) - required - optional:
        raise ValueError("Expected analysis samples, seconds, seed, policy and objective.")
    config = MonteCarloConfig(**data)
    if config.samples > 1000 or config.seconds > 15 or (config.learning_samples or 0) > 1000:
        raise ValueError("Dashboard analysis is limited to 1000 samples and 15 seconds.")
    return config
