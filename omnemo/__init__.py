"""Omnemo — memory-only MCP server: save, recall, search, forget."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("omnemo")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0+unknown"
