# Copyright 2026 Canonical
# See LICENSE file for licensing details.

import subprocess

import pytest

from meta_release import MetaRelease, PullUpdatesError


def test_pull_updates_fails_fast_without_connectivity(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Test that an unreachable repository fails before the clone starts."""

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("meta_release.subprocess.run", timeout)
    monkeypatch.setattr(
        "meta_release.subprocess.check_call",
        lambda *args, **kwargs: pytest.fail("clone must not start"),
    )

    release = MetaRelease(tmp_path)

    with pytest.raises(PullUpdatesError, match="cannot reach"):
        release.pull_updates("main")
