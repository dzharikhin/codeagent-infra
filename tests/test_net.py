"""Tests for networking helpers."""

import socket

import pytest

from opencode_framework.exceptions import PortAllocationError
from opencode_framework.net import find_free_port


class TestFindFreePort:
    """Tests for find_free_port."""

    def test_returns_start_when_available(self):
        """Should return the start port when it is free."""
        port = find_free_port(4096, 4196)
        assert port == 4096

    def test_skips_bound_port(self):
        """Should skip a port that is already bound and return the next one."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 4096))
        sock.listen(1)
        try:
            port = find_free_port(4096, 4196)
            assert port == 4097
        finally:
            sock.close()

    def test_finds_port_in_middle_of_range(self):
        """Should find the first free port after several bound ports."""
        socks = []
        try:
            for p in range(4096, 4099):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", p))
                s.listen(1)
                socks.append(s)
            port = find_free_port(4096, 4196)
            assert port == 4099
        finally:
            for s in socks:
                s.close()

    def test_exhausted_range_raises(self):
        """Should raise PortAllocationError when no port in range is free."""
        socks = []
        try:
            for p in range(4096, 4098):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", p))
                s.listen(1)
                socks.append(s)
            with pytest.raises(PortAllocationError) as exc_info:
                find_free_port(4096, 4097)
            assert "4096" in exc_info.value.message
            assert "4097" in exc_info.value.message
            assert exc_info.value.remediation is not None
        finally:
            for s in socks:
                s.close()

    def test_custom_range(self):
        """Should respect custom start/end parameters."""
        port = find_free_port(5000, 5005)
        assert 5000 <= port <= 5005

    def test_reserved_skips_port_even_when_free(self):
        """Should skip a port listed in reserved even if it would bind successfully."""
        port = find_free_port(4096, 4196, reserved=[4096])
        assert port == 4097

    def test_reserved_skips_multiple_ports(self):
        """Should skip all ports in reserved and return the first free remainder."""
        port = find_free_port(4096, 4196, reserved=[4096, 4097, 4098])
        assert port == 4099

    def test_reserved_none_behaves_as_default(self):
        """Passing reserved=None should behave identically to omitting the argument."""
        port = find_free_port(4096, 4196, reserved=None)
        assert port == 4096

    def test_reserved_exhausts_all_ports_raises(self):
        """Should raise PortAllocationError when reserved covers the entire range."""
        with pytest.raises(PortAllocationError):
            find_free_port(4096, 4097, reserved=[4096, 4097])
