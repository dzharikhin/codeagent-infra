"""Container exit watchdog for ACP launch sessions.

ACP mode hands launch's stdout to the editor as a JSON-RPC transport, so
launch cannot always rely on the docker client to notice container death:
a container stopped or removed externally can leave the
``docker compose run`` client hanging, and with it the editor session.

The watchdog polls the container's lifecycle state in a daemon thread.
Once the container has been observed running and is then confirmed
stopped, dead or removed, it gives the docker child a short grace period
to exit on its own (the healthy client usually does) and otherwise
terminates it, letting launch exit with a conventional status code.

The module is docker-free: the container state is supplied by a callable,
which keeps the thread logic unit-testable without a docker daemon.
"""

import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

#: Container states that count as "gone for good" once armed. Any other
#: state (``paused``, ``restarting``, ...) is tolerated, as are query
#: failures, to avoid killing the session on a transient hiccup.
_TERMINAL_STATES = frozenset({"removed", "exited", "dead"})


@dataclass
class WatchdogConfig:
    """Tunables for :class:`ContainerExitWatchdog`.

    Args:
        poll_interval: Seconds between container state queries.
        grace_period: Seconds to wait for the docker child to exit on
            its own after the container is confirmed gone.
        terminate_grace: Seconds to wait between SIGTERM and SIGKILL
            when the docker child ignores the first signal.
    """

    poll_interval: float = 2.0
    grace_period: float = 5.0
    terminate_grace: float = 3.0


class ContainerExitWatchdog:
    """Terminate a docker child once its container stops or is removed.

    The watchdog stays passive until the container is first observed
    ``running`` — before that, absence or ``created`` are normal startup
    states, and a container that never starts fails the docker child on
    its own. Once armed, a confirmed terminal state starts a grace
    period; if the child is still alive afterwards it is terminated and,
    if needed, killed. Single-fire: after handling one trigger the
    thread exits.

    Read ``triggered`` only after :meth:`stop` has joined the thread.

    Args:
        container_name: Name of the container to watch.
        status_fn: Callable mapping the container name to its lifecycle
            state — ``"removed"`` when the container does not exist, a
            docker state string (``running``, ``exited``, ...) when it
            does, and ``None`` when the query itself failed.
        child: The docker client child process to terminate on trigger.
        config: Polling and grace tunables; defaults apply when omitted.
    """

    def __init__(
        self,
        container_name: str,
        status_fn: Callable[[str], Optional[str]],
        child: subprocess.Popen,
        config: Optional[WatchdogConfig] = None,
    ) -> None:
        self.container_name = container_name
        self._status_fn = status_fn
        self._child = child
        self._config = config or WatchdogConfig()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.triggered = False
        self.trigger_reason: Optional[str] = None

    def start(self) -> None:
        """Start the polling thread; does nothing when already running."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="ocf-container-watchdog", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the thread to stop and wait for it to finish.

        Args:
            timeout: Maximum seconds to wait for the thread to exit.
        """
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        """Return True while the polling thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        armed = False
        while not self._stop_event.is_set():
            try:
                status = self._status_fn(self.container_name)
            except Exception:
                status = None  # query failures must never cause a kill
            if status == "running":
                armed = True
            elif armed and status in _TERMINAL_STATES:
                self._on_container_gone(status)
                return
            self._stop_event.wait(self._config.poll_interval)

    def _on_container_gone(self, status: str) -> None:
        # Grace: a healthy docker client notices container death and
        # exits on its own; only a hung client needs to be terminated.
        deadline = time.monotonic() + self._config.grace_period
        while time.monotonic() < deadline:
            if self._child.poll() is not None:
                return
            if self._stop_event.wait(0.1):
                return
        self._terminate_child(status)

    def _terminate_child(self, status: str) -> None:
        self.triggered = True
        self.trigger_reason = f"container '{self.container_name}' is {status}"
        self._signal_child(terminate=True)
        deadline = time.monotonic() + self._config.terminate_grace
        while time.monotonic() < deadline:
            if self._child.poll() is not None:
                return
            time.sleep(0.1)
        self._signal_child(terminate=False)

    def _signal_child(self, terminate: bool) -> None:
        try:
            if self._child.poll() is not None:
                return
            if terminate:
                self._child.terminate()
            else:
                self._child.kill()
        except (ProcessLookupError, OSError, ValueError):
            pass
