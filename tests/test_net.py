"""Tests for networking helpers."""

import socket
from typing import List, Optional

import pytest

from opencode_framework.exceptions import PortAllocationError
from opencode_framework.sandbox.net import find_free_port

_EPHEMERAL_PROBE_ATTEMPTS = 50


def _bind(port: int) -> socket.socket:
    """Bind a listening TCP socket on 127.0.0.1:port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    return sock


def _consecutive_free_ports(count: int) -> int:
    """Return a base port where [base, base+count-1] are all currently free.

    Uses an ephemeral-port probe to stay far from fixed service ports, then
    verifies the whole window is bindable. Retries because the kernel may
    hand out a base that collides with an adjacent service port; each retry
    gets a fresh ephemeral base.
    """
    for _ in range(_EPHEMERAL_PROBE_ATTEMPTS):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            base = probe.getsockname()[1]
        socks: List[Optional[socket.socket]] = []
        try:
            for port in range(base, base + count):
                socks.append(_bind(port))
        except OSError:
            for sock in socks:
                if sock is not None:
                    sock.close()
            continue
        for sock in socks:
            assert sock is not None
            sock.close()
        return base
    pytest.fail(f"Could not find {count} consecutive free ports")


class TestFindFreePort:
    """Tests for find_free_port."""

    def test_returns_start_when_available(self):
        """Should return the start port when it is free."""
        base = _consecutive_free_ports(2)
        assert find_free_port(base, base + 1) == base

    def test_skips_bound_port(self):
        """Should skip a port that is already bound and return the next one."""
        base = _consecutive_free_ports(2)
        sock = _bind(base)
        try:
            assert find_free_port(base, base + 1) == base + 1
        finally:
            sock.close()

    def test_finds_port_in_middle_of_range(self):
        """Should find the first free port after several bound ports."""
        base = _consecutive_free_ports(4)
        socks = [_bind(p) for p in range(base, base + 3)]
        try:
            assert find_free_port(base, base + 100) == base + 3
        finally:
            for sock in socks:
                sock.close()

    def test_exhausted_range_raises(self):
        """Should raise PortAllocationError when no port in range is free."""
        base = _consecutive_free_ports(2)
        socks = [_bind(p) for p in (base, base + 1)]
        try:
            with pytest.raises(PortAllocationError) as exc_info:
                find_free_port(base, base + 1)
            assert str(base) in exc_info.value.message
            assert str(base + 1) in exc_info.value.message
            assert exc_info.value.remediation is not None
        finally:
            for sock in socks:
                sock.close()

    def test_custom_range(self):
        """Should respect custom start/end parameters."""
        base = _consecutive_free_ports(6)
        port = find_free_port(base, base + 5)
        assert base <= port <= base + 5

    def test_reserved_skips_port_even_when_free(self):
        """Should skip a port listed in reserved even if it would bind successfully."""
        base = _consecutive_free_ports(2)
        assert find_free_port(base, base + 1, reserved=[base]) == base + 1

    def test_reserved_skips_multiple_ports(self):
        """Should skip all ports in reserved and return the first free remainder."""
        base = _consecutive_free_ports(4)
        reserved = [base, base + 1, base + 2]
        assert find_free_port(base, base + 3, reserved=reserved) == base + 3

    def test_reserved_none_behaves_as_default(self):
        """Passing reserved=None should behave identically to omitting the argument."""
        base = _consecutive_free_ports(1)
        assert find_free_port(base, base + 100, reserved=None) == base

    def test_reserved_exhausts_all_ports_raises(self):
        """Should raise PortAllocationError when reserved covers the entire range."""
        base = _consecutive_free_ports(2)
        with pytest.raises(PortAllocationError):
            find_free_port(base, base + 1, reserved=[base, base + 1])
