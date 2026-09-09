"""Sandbox package: tool-agnostic container isolation.

Owns the devcontainer image build, Docker Compose runtime, mounts,
networks, ports, and the environment variables of this layer. Never
imports tool-specific knowledge; the agent tool registry fills the
agent slots. Import concrete submodules (``sandbox.compose``,
``sandbox.runtime``, ...), not symbols from here.
"""
