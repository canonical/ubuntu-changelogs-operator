# Copyright 2026 Canonical
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import pytest
from ops import testing

from changelogs import ServiceStatus
from charm import UbuntuChangelogsOperatorCharm


def test_start(monkeypatch: pytest.MonkeyPatch):
    """Test that the charm has the correct state after handling the start event."""
    # Arrange:
    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    monkeypatch.setattr("nginx.Nginx.start", lambda self: None)
    monkeypatch.setattr("nginx.Nginx.get_version", lambda self: "1.0.0")
    # Act:
    state_out = ctx.run(ctx.on.start(), testing.State())
    # Assert:
    assert state_out.workload_version is not None
    assert state_out.unit_status == testing.ActiveStatus()


def test_install_orchestrates_components(monkeypatch: pytest.MonkeyPatch):
    """Test that install sets up each service component."""
    calls = []
    monkeypatch.setattr("nginx.Nginx.install", lambda self: calls.append("nginx.install"))
    monkeypatch.setattr(
        "meta_release.MetaRelease.install", lambda self: calls.append("meta_release.install")
    )
    monkeypatch.setattr(
        "changelogs.Changelogs.install", lambda self: calls.append("changelogs.install")
    )

    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    state_out = ctx.run(ctx.on.install(), testing.State())

    assert calls == [
        "nginx.install",
        "meta_release.install",
        "changelogs.install",
    ]
    assert state_out.unit_status == testing.ActiveStatus("Ready")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ServiceStatus.OK, testing.ActiveStatus()),
        (ServiceStatus.RUNNING, testing.MaintenanceStatus("extracting changelogs")),
        (ServiceStatus.FAILED, testing.BlockedStatus("changelog extraction failed")),
    ],
)
def test_update_status_reflects_extraction_health(
    monkeypatch: pytest.MonkeyPatch, status: ServiceStatus, expected
):
    """Test that update-status maps extraction health to the unit status."""
    monkeypatch.setattr("changelogs.Changelogs.extractor_status", lambda self: status)

    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    state_out = ctx.run(ctx.on.update_status(), testing.State())

    assert state_out.unit_status == expected


def test_pull_changelogs_action_triggers_extraction(monkeypatch: pytest.MonkeyPatch):
    """Test that the pull-changelogs action triggers the extractor and reports success."""
    monkeypatch.setattr("changelogs.Changelogs.run_extractor", lambda self: None)

    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    state_out = ctx.run(ctx.on.action("pull-changelogs"), testing.State())

    assert ctx.action_results == {"result": "changelog extraction triggered"}
    assert state_out.unit_status == testing.MaintenanceStatus("extracting changelogs")


def test_pull_changelogs_action_fails_on_error(monkeypatch: pytest.MonkeyPatch):
    """Test that the pull-changelogs action is marked failed when triggering fails."""

    def boom(self):
        raise RuntimeError("nope")

    monkeypatch.setattr("changelogs.Changelogs.run_extractor", boom)

    ctx = testing.Context(UbuntuChangelogsOperatorCharm)
    with pytest.raises(testing.ActionFailed) as exc_info:
        ctx.run(ctx.on.action("pull-changelogs"), testing.State())

    assert "failed to trigger changelog extraction: nope" in exc_info.value.message
