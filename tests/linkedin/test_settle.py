"""The main page settle wait (CaptureMode.SETTLE).

The timeline below is the one measured on a live profile in 11/2026, in 0.5 s
poll steps after navigation returned: first paint 1,505 characters, unchanged
for about 1.7 s, then the lazy component fetches, then 6,170 characters.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest

from linkedin_mcp_server.linkedin import capture as capture_module
from linkedin_mcp_server.linkedin.capture import SectionCapture, _HydrationTracker

COMPONENT = "https://www.linkedin.com/flagship-web/rsc-action/actions/component"


class FakePage:
    def __init__(self) -> None:
        self.handlers: dict[str, list[Callable[[Any], None]]] = {}
        self.length = 0

    def on(self, event: str, handler: Callable[[Any], None]) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event: str, handler: Callable[[Any], None]) -> None:
        self.handlers[event].remove(handler)

    def emit(self, event: str, request: Any) -> None:
        for handler in list(self.handlers.get(event, [])):
            handler(request)

    async def evaluate(self, _script: str) -> int:
        return self.length


class FakeSession:
    """Runs a scripted timeline: step n happens during the n-th poll delay."""

    def __init__(self, page: FakePage, timeline: dict[int, Callable[[], None]]):
        self.page = page
        self.timeline = timeline
        self.steps = 0

    async def delay(self, seconds: float) -> None:
        assert seconds == capture_module._SETTLE_POLL
        self.steps += 1
        if self.steps in self.timeline:
            self.timeline[self.steps]()


def _capture(session: FakeSession) -> SectionCapture:
    return SectionCapture(session, navigator=None, content=None)  # type: ignore[arg-type]


def _request(url: str = COMPONENT) -> Any:
    return SimpleNamespace(url=url)


def _measured_timeline(page: FakePage) -> dict[int, Callable[[], None]]:
    """First paint, 1.5 s of silence, fetches in flight for 1 s, two text steps."""
    first, second, third = _request(), _request(), _request()

    def set_length(n: int) -> Callable[[], None]:
        def apply() -> None:
            page.length = n

        return apply

    def start() -> None:
        page.emit("request", first)
        page.emit("request", second)
        page.emit("request", third)

    def finish(*requests: Any) -> Callable[[], None]:
        def apply() -> None:
            for request in requests:
                page.emit("requestfinished", request)

        return apply

    return {
        1: set_length(1505),
        # 2, 3: first paint holds still (the trap: 1.7 s of no change)
        4: start,
        5: set_length(2750),
        6: finish(first, second),
        7: finish(third),
        8: set_length(6170),
    }


class TestHydrationTracker:
    def test_counts_only_component_fetches_until_they_finish_or_fail(self):
        page = FakePage()
        tracker = _HydrationTracker(page)
        tracker.install()
        component, failed, other = (
            _request(),
            _request(),
            _request("https://www.linkedin.com/voyager/api/graphql"),
        )
        for request in (component, failed, other):
            page.emit("request", request)
        assert (tracker.started, tracker.pending) == (2, 2)
        page.emit("requestfinished", component)
        page.emit("requestfailed", failed)
        page.emit("requestfinished", other)
        assert (tracker.started, tracker.pending) == (2, 0)

    def test_remove_detaches_every_listener_and_reset_forgets_an_attempt(self):
        page = FakePage()
        tracker = _HydrationTracker(page)
        tracker.install()
        page.emit("request", _request())
        tracker.reset()
        assert (tracker.started, tracker.pending) == (0, 0)
        tracker.remove()
        assert all(not handlers for handlers in page.handlers.values())


class TestSettle:
    async def test_waits_through_the_silent_gap_until_the_cards_have_loaded(self):
        page = FakePage()
        tracker = _HydrationTracker(page)
        tracker.install()
        session = FakeSession(page, _measured_timeline(page))
        settled = await _capture(session)._settle("https://x/in/ada/", tracker)
        assert settled is True
        assert page.length == 6170
        # last change at step 8, then one quiet second: steps 9 and 10
        assert session.steps == 10

    async def test_text_alone_would_have_stopped_in_the_gap(self):
        """Without the fetch signal a 1 s quiet window ends inside the trap."""
        page = FakePage()
        session = FakeSession(page, _measured_timeline(page))
        quiet = capture_module._SETTLE_QUIET
        steps_quiet = 0
        last = None
        for _ in range(20):
            await session.delay(capture_module._SETTLE_POLL)
            if page.length == last:
                steps_quiet += 1
                if steps_quiet * capture_module._SETTLE_POLL >= quiet:
                    break
            else:
                last, steps_quiet = page.length, 0
        assert page.length == 1505

    async def test_without_any_component_fetch_it_waits_for_the_first_then_settles(
        self,
    ):
        page = FakePage()
        page.length = 900
        tracker = _HydrationTracker(page)
        tracker.install()
        session = FakeSession(page, {})
        assert await _capture(session)._settle("https://x/in/ada/", tracker) is True
        assert session.steps == 9  # until 4 s, then one quiet second

    async def test_without_a_tracker_the_text_must_hold_still_three_seconds(self):
        page = FakePage()
        page.length = 900
        session = FakeSession(page, {})
        assert await _capture(session)._settle("https://x/in/ada/", None) is True
        assert session.steps == 6

    async def test_gives_up_at_the_cap_and_says_so(
        self, caplog: pytest.LogCaptureFixture
    ):
        page = FakePage()
        tracker = _HydrationTracker(page)
        tracker.install()
        page.emit("request", _request())  # never finishes
        session = FakeSession(page, {})
        assert await _capture(session)._settle("https://x/in/ada/", tracker) is False
        assert session.steps == int(
            capture_module._SETTLE_CAP / capture_module._SETTLE_POLL
        )
        assert "did not settle" in caplog.text
