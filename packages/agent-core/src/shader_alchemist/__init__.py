"""Shader Alchemist agent-core package.

The CLI entry point is intentionally not imported here. Keeping ``main`` lazy
prevents ``python -m shader_alchemist.main`` from loading the module twice and
emitting a ``runpy`` warning.
"""

__all__: list[str] = []