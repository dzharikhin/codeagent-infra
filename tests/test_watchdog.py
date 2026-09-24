"""Tests for the container exit watchdog."""

import threading
import time
from typing import List, Optional

from opencode_framework.sandbox.watchdog import (
    ContainerExitWatchdog,
    WatchdogConfig,
)

FAST = WatchdogConfig(poll_interval=0.01, grace_period=0.05, terminate_grace=0.05)


class FakeChild:
    """subprocess.Popen stand-in recording signals with scripted liveness.

    Args:
        exit_code: Value returned by poll(); None means still running.
        die_on_terminate: Clear the exit code once terminate() is called
            (client that exits on SIGTERM).
        ignore_terminate: Stay alive through terminate(); only kill()
            ends the process.
    """

    def __init__(
        self,
        exit_code: Optional[int] = None,
        die_on_terminate: bool = False,
        ignore_terminate: bool = False,
    ):
        self._exit_code = exit_code
        self._die_on_terminate = die_on_terminate
        self._ignore_terminate = ignore_terminate
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> Optional[int]:
        if self._exit_code is None:
            return None
        return self._exit_code

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self._die_on_terminate and not self._ignore_terminate:
            self._exit_code = 0

    def kill(self) -> None:
        self.kill_calls += 1
        if not self._ignore_terminate:
            self._exit_code = 0

    def wait(self, timeout: Optional[float] = None) -> int:
        return self._exit_code if self._exit_code is not None else 0


class StatusScript:
    """Callable returning states in order, repeating the last one.

    The special state "raise" makes the call raise, simulating a failed
    docker query.
    """

    def __init__(self, states: List[str]):
        self.states = states
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, name: str) -> Optional[str]:
        with self._lock:
            idx = min(self.calls, len(self.states) - 1)
            self.calls += 1
        state = self.states[idx]
        if state == "raise":
            raise RuntimeError("docker daemon unreachable")
        return state


class TestContainerExitWatchdog:
    """Tests for the watchdog thread lifecycle and trigger semantics."""

    def test_triggers_on_removed_after_armed(self):
        child = FakeChild(die_on_terminate=True)
        script = StatusScript(["running", "removed"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        deadline = time.monotonic() + 2.0
        while not watchdog.triggered and time.monotonic() < deadline:
            time.sleep(0.005)
        watchdog.stop()

        assert watchdog.triggered
        assert "removed" in (watchdog.trigger_reason or "")
        assert child.terminate_calls == 1
        assert child.kill_calls == 0

    def test_triggers_on_exited_state(self):
        child = FakeChild(die_on_terminate=True)
        script = StatusScript(["running", "exited"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        deadline = time.monotonic() + 2.0
        while not watchdog.triggered and time.monotonic() < deadline:
            time.sleep(0.005)
        watchdog.stop()

        assert watchdog.triggered
        assert "exited" in (watchdog.trigger_reason or "")

    def test_kills_child_that_ignores_terminate(self):
        child = FakeChild(ignore_terminate=True)
        script = StatusScript(["running", "dead"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        deadline = time.monotonic() + 2.0
        while child.kill_calls == 0 and time.monotonic() < deadline:
            time.sleep(0.005)
        watchdog.stop()

        assert watchdog.triggered
        assert child.terminate_calls == 1
        assert child.kill_calls == 1

    def test_no_trigger_while_running(self):
        child = FakeChild()
        script = StatusScript(["running"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        time.sleep(0.15)
        watchdog.stop()

        assert not watchdog.triggered
        assert child.terminate_calls == 0

    def test_no_trigger_before_first_running(self):
        child = FakeChild()
        script = StatusScript(["created", "removed"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        time.sleep(0.15)
        watchdog.stop()

        assert not watchdog.triggered
        assert child.terminate_calls == 0

    def test_tolerates_query_failures_before_trigger(self):
        child = FakeChild(die_on_terminate=True)
        script = StatusScript(["running", "raise", "removed"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        deadline = time.monotonic() + 2.0
        while not watchdog.triggered and time.monotonic() < deadline:
            time.sleep(0.005)
        watchdog.stop()

        assert watchdog.triggered

    def test_never_triggers_on_persistent_failures(self):
        child = FakeChild()
        script = StatusScript(["raise"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        time.sleep(0.15)
        watchdog.stop()

        assert not watchdog.triggered
        assert child.terminate_calls == 0

    def test_child_exiting_within_grace_avoids_terminate(self):
        child = FakeChild(exit_code=0)
        script = StatusScript(["running", "removed"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        deadline = time.monotonic() + 2.0
        while script.calls < 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        time.sleep(0.15)
        watchdog.stop()

        assert not watchdog.triggered
        assert child.terminate_calls == 0

    def test_paused_state_is_tolerated(self):
        child = FakeChild()
        script = StatusScript(["running", "paused"])
        watchdog = ContainerExitWatchdog("ocf_x", script, child, config=FAST)

        watchdog.start()
        time.sleep(0.15)
        watchdog.stop()

        assert not watchdog.triggered
        assert child.terminate_calls == 0

    def test_stop_before_start_is_safe(self):
        watchdog = ContainerExitWatchdog(
            "ocf_x", StatusScript(["running"]), FakeChild(), config=FAST
        )
        watchdog.stop()
        assert not watchdog.triggered
        assert not watchdog.is_alive()

    def test_start_is_idempotent(self):
        watchdog = ContainerExitWatchdog(
            "ocf_x", StatusScript(["running"]), FakeChild(), config=FAST
        )
        watchdog.start()
        thread = watchdog._thread
        watchdog.start()
        assert watchdog._thread is thread
        watchdog.stop()

    def test_stop_joins_thread(self):
        watchdog = ContainerExitWatchdog(
            "ocf_x", StatusScript(["running"]), FakeChild(), config=FAST
        )
        watchdog.start()
        watchdog.stop(timeout=2.0)
        assert not watchdog.is_alive()
