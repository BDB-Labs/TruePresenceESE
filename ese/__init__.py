"""Ensemble Software Engineering (ESE) package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ese-cli")
except PackageNotFoundError:
    __version__ = "0.0.0"
__copyright__ = "Copyright (c) 2026 BagelTech.net"
