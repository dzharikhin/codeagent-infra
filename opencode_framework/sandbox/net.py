"""Networking helpers for the OpenCode Framework."""

import socket
from typing import Iterable, Optional

from opencode_framework.exceptions import PortAllocationError


def find_free_port(
    start: int = 4096,
    end: int = 4196,
    reserved: Optional[Iterable[int]] = None,
) -> int:
    """Return the first free TCP port on 127.0.0.1 in the inclusive range.

    Probes each port in ``[start, end]`` by attempting a ``socket.bind`` on
    ``127.0.0.1``. The first port that binds successfully is returned. The
    socket is closed before returning so the caller (e.g. Docker) can claim it.

    Args:
        start: Lower bound of the port range (inclusive).
        end: Upper bound of the port range (inclusive).
        reserved: Ports to skip regardless of bind availability (e.g. ports
            already claimed by wizard-configured compose mappings).

    Returns:
        First free port in the range.

    Raises:
        PortAllocationError: If no port in the range is free.
    """
    reserved_set = set(reserved or ())
    for port in range(start, end + 1):
        if port in reserved_set:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise PortAllocationError(
        message=f"No free TCP port available on 127.0.0.1 in [{start}, {end}]",
        remediation="Free a port in that range or pass --server=<port> explicitly.",
    )
