# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Fixtures shared by the unit tests."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

SCRIPT = Path(__file__).parents[2] / "files" / "lp-extract-changelogs.py"


def _stub(monkeypatch, name, **attributes):
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    monkeypatch.setitem(sys.modules, name, module)


@pytest.fixture
def lp(monkeypatch):
    """Load the crawler script with its system-only dependencies stubbed.

    The script imports ``apt_pkg``, ``httplib2`` and ``launchpadlib`` at import
    time. These packages live on the deployed machine, not in the unit-test
    environment, so tests provide light stubs here.
    """
    _stub(monkeypatch, "apt_pkg", get_lock=Mock())
    _stub(monkeypatch, "httplib2", HttpLib2Error=type("HttpLib2Error", (Exception,), {}))
    _stub(monkeypatch, "launchpadlib")
    _stub(monkeypatch, "launchpadlib.credentials", Credentials=Mock)
    _stub(monkeypatch, "launchpadlib.launchpad", Launchpad=Mock)

    spec = importlib.util.spec_from_file_location("lp_extract_changelogs", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
