"""Hard budget for the agent loop. Enforced inside the state — no LLM-controlled fields."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AgentBudget:
    """Wall-clock + iteration + LLM-call caps. Created once per request.

    The agent must check `is_exhausted()` before doing further work; on
    exhaustion the graph routes to `generate` with whatever was retrieved.
    Verify still runs but skips the regenerate-retry path.
    """

    max_iterations: int = 2  # plan → retrieve → reflect cycles
    max_total_llm_calls: int = 8  # plan + reflect×2 + refine + generate (+ retry) + verify
    max_wall_clock_ms: int = 15000

    llm_calls_made: int = 0
    _start_time_s: float = field(default_factory=time.monotonic)

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start_time_s) * 1000)

    def remaining_ms(self) -> int:
        return max(0, self.max_wall_clock_ms - self.elapsed_ms())

    def record_llm_call(self) -> None:
        self.llm_calls_made += 1

    def is_exhausted(self, iterations: int) -> bool:
        if self.llm_calls_made >= self.max_total_llm_calls:
            return True
        if iterations >= self.max_iterations:
            return True
        if self.remaining_ms() <= 0:
            return True
        return False

    def can_afford_llm_call(self, reserve: int = 0) -> bool:
        """Use before making an LLM call. Verify-retry consults this too.

        `reserve` is the number of LLM calls that downstream nodes MUST be able
        to make after this point. Reflect/refine pass reserve=2 so generate +
        verify always have slots, even if a future refactor reintroduces the
        loop. Generate and verify themselves call with reserve=0 (default)."""
        return (
            self.llm_calls_made + reserve < self.max_total_llm_calls
            and self.remaining_ms() > 0
        )
