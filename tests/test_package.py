"""Test package imports and basic version info."""

from __future__ import annotations

import importlib
import re

import simulor


def test_version_defined() -> None:
    assert hasattr(simulor, "__version__")
    assert isinstance(simulor.__version__, str)
    assert simulor.__version__.strip() != ""
    assert re.match(r"^\d+\.\d+\.\d+(\S*)?$", simulor.__version__)


def test_package_importable() -> None:
    mod = importlib.import_module("simulor")
    assert mod is not None
