from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeRange:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def contains(self, time_seconds: float) -> bool:
        return self.start <= time_seconds <= self.end


def clamp_range(start: float, end: float, project_duration: float) -> TimeRange:
    low = max(0.0, min(start, end))
    high = min(max(start, end), max(project_duration, low))
    return TimeRange(low, high)
