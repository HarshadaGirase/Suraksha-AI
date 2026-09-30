"""The rescue clock (CLAUDE.MD §17).

Real wall-clock elapsed, uncapped. The original spec animated a fake clock to
"T+3:40" over 4.4 real seconds, which padded the product to look slower than it
is. Four Gemini calls and a PDF render land somewhere around 15-30 seconds, and
"documents ready in 28 seconds vs 4-6 hours manual" is both a better line and a
true one.

If a run takes 90 seconds, this reports 90 seconds. A clock that lies about the
good case will also lie about the bad one, and the bad one is what a judge will
happen to hit.
"""

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RescueClock:
    """Started by create_case; read whenever a stat is emitted."""

    started_at: float | None = None
    marks: dict[str, float] = field(default_factory=dict)

    def start(self) -> None:
        if self.started_at is None:
            self.started_at = time.monotonic()

    @property
    def running(self) -> bool:
        return self.started_at is not None

    def elapsed(self) -> float:
        """Seconds since start, or 0.0 before it starts."""
        if self.started_at is None:
            return 0.0
        return time.monotonic() - self.started_at

    def mark(self, name: str) -> float:
        """Record a milestone and return its elapsed time."""
        t = self.elapsed()
        self.marks.setdefault(name, t)
        return t

    def since(self, name: str) -> float | None:
        """Seconds between a recorded mark and now, or None if never marked."""
        if name not in self.marks:
            return None
        return self.elapsed() - self.marks[name]

    def format(self) -> str:
        """Display form: '28s' under a minute, '1:34' beyond it."""
        total = int(self.elapsed())
        if total < 60:
            return f"{total}s"
        return f"{total // 60}:{total % 60:02d}"
