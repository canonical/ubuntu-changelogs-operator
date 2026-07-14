# Copyright 2026 Work
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import pytest
from ops import testing

from charm import UbuntuChangelogsOperatorCharm


def test_start(monkeypatch: pytest.MonkeyPatch):
    """Test that the charm has the correct state after handling the start event."""
    # Arrange:
    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    monkeypatch.setattr("charm.nginx.start", lambda: None)
    monkeypatch.setattr("charm.nginx.get_version", lambda: "1.0.0")
    # Act:
    state_out = ctx.run(ctx.on.start(), testing.State())
    # Assert:
    assert state_out.workload_version is not None
    assert state_out.unit_status == testing.ActiveStatus()


def test_install_orchestrates_components(monkeypatch: pytest.MonkeyPatch):
    """Test that install sets up each service component."""
    calls = []
    monkeypatch.setattr("charm.nginx.install", lambda: calls.append("nginx.install"))

    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    state_out = ctx.run(ctx.on.install(), testing.State())

    assert calls == [
        "nginx.install",
    ]
    assert state_out.unit_status == testing.ActiveStatus("Ready")
