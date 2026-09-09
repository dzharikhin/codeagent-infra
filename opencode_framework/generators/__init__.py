"""Generators for the active tool's config directory contents.

Import concrete submodules (``generators.orchestrator``,
``generators.base``, ...), not symbols from here: eagerly importing
the orchestrator here would create an import cycle with the sandbox
generators it uses.
"""
