"""Idle-time learning orchestration with conservative resource and quality gates."""
import threading
import time


class IdleLearningManager:
    """Runs at most one bounded, validation-gated learning attempt per cooldown."""

    def __init__(self, agent, *, idle_after_seconds=300, cooldown_seconds=1800,
                 max_training_rows=500, min_validation_samples=4, clock=None):
        self.agent = agent
        self.idle_after_seconds = max(1.0, float(idle_after_seconds))
        self.cooldown_seconds = max(self.idle_after_seconds, float(cooldown_seconds))
        self.max_training_rows = max(1, int(max_training_rows))
        self.min_validation_samples = max(2, int(min_validation_samples))
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._last_activity = self._clock()
        self._last_cycle = float("-inf")
        self._last_result = None
        self._running = False

    def mark_activity(self):
        """Reset idle timer after an interaction without interrupting active work."""
        with self._lock:
            self._last_activity = self._clock()

    def status(self):
        with self._lock:
            now = self._clock()
            return {
                "enabled": True,
                "running": self._running,
                "idle_after_seconds": self.idle_after_seconds,
                "cooldown_seconds": self.cooldown_seconds,
                "seconds_since_activity": max(0.0, now - self._last_activity),
                "last_result": self._last_result,
            }

    def run_if_idle(self, payload=None):
        """Audit data and attempt one isolated epoch only after a sustained idle period."""
        with self._lock:
            now = self._clock()
            idle_for = now - self._last_activity
            if self._running:
                return {"status": "skipped", "reason": "cycle_already_running"}
            if idle_for < self.idle_after_seconds:
                return {
                    "status": "skipped", "reason": "not_idle",
                    "idle_for_seconds": round(idle_for, 2),
                    "required_seconds": self.idle_after_seconds,
                }
            if now - self._last_cycle < self.cooldown_seconds:
                return {"status": "skipped", "reason": "cooldown"}
            self._running = True
            self._last_cycle = now

        try:
            audit = self.agent.learning.dataset.audit_splits()
            if not audit.get("valid", False):
                result = {
                    "status": "blocked", "reason": "dataset_integrity_failed",
                    "violations": audit.get("violations", [])[:20],
                }
            else:
                rows = self.agent.learning.dataset.load()
                train_rows = [
                    row for row in rows
                    if row.get("split", "train") == "train"
                    and row.get("type", "qa") in {"qa", "pair"}
                ]
                validation_rows = [
                    row for row in rows
                    if row.get("split") == "validation"
                    and row.get("type", "qa") == "qa"
                ]
                if len(train_rows) > self.max_training_rows:
                    result = {
                        "status": "skipped", "reason": "training_budget_exceeded",
                        "training_rows": len(train_rows),
                        "maximum_training_rows": self.max_training_rows,
                    }
                elif len(validation_rows) < self.min_validation_samples:
                    result = {
                        "status": "skipped", "reason": "insufficient_validation_samples",
                        "validation_samples": len(validation_rows),
                        "required_samples": self.min_validation_samples,
                    }
                elif not train_rows:
                    result = {"status": "skipped", "reason": "training_split_empty"}
                else:
                    report = self.agent.learning.train_incremental(
                        epochs=1,
                        min_validation_samples=self.min_validation_samples,
                        regression_tolerance=0.02,
                        min_improvement=0.001,
                    )
                    result = {
                        "status": "completed" if report.get("accepted") else "no_improvement",
                        "learning_report": report,
                    }
        except Exception as exc:
            result = {
                "status": "error",
                "reason": type(exc).__name__,
                "message": str(exc)[:1000],
            }
        finally:
            with self._lock:
                self._running = False
                self._last_result = result
        return result
