from dataclasses import dataclass

from olympus_core.models.monitoring import ProbeStatus


@dataclass(frozen=True, slots=True)
class StatusTransition:
    previous: ProbeStatus
    current: ProbeStatus


class TransitionTracker:
    def __init__(self, failure_threshold: int, recovery_threshold: int) -> None:
        self.status = ProbeStatus.UNKNOWN
        self._failure_threshold = failure_threshold
        self._recovery_threshold = recovery_threshold
        self._failures = 0
        self._successes = 0

    def record(self, success: bool) -> StatusTransition | None:
        previous = self.status
        if success:
            self._failures = 0
            self._successes += 1
            if self.status != ProbeStatus.UP and self._successes >= self._recovery_threshold:
                self.status = ProbeStatus.UP
        else:
            self._successes = 0
            self._failures += 1
            if self.status != ProbeStatus.DOWN and self._failures >= self._failure_threshold:
                self.status = ProbeStatus.DOWN

        if self.status != previous:
            return StatusTransition(previous, self.status)
        return None
