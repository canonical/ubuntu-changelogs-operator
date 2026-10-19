# Copyright 2026 Canonical
# See LICENSE file for licensing details.
#
# The integration tests use the Jubilant library and the pytest-jubilant plugin.
# See https://documentation.ubuntu.com/ops/latest/howto/write-integration-tests-for-a-charm/
#
# pytest-jubilant provides a module-scoped `juju` fixture that creates a temporary Juju model.
# The `charm` fixture is defined in conftest.py.

import pathlib
import time

import jubilant
import pytest

APP = "ubuntu-changelogs"
UNIT = f"{APP}/0"
META_RELEASE = "/var/www/changelogs.ubuntu.com/meta-release"


def run(juju: jubilant.Juju, command: str) -> str:
    """Run a shell command on the unit and return its output."""
    return juju.exec(command, unit=UNIT).stdout.strip()


def http_get(juju: jubilant.Juju, path: str) -> str:
    """Fetch a path from the workload."""
    return juju.exec(f"curl -fsS http://localhost{path}", unit=UNIT).stdout


def file_mtime(juju: jubilant.Juju, path: str) -> str:
    """Return the modification time of a file."""
    return run(juju, f"stat -c %y {path}")


def wait_for_meta_release_update(juju: jubilant.Juju, before: str) -> None:
    """Wait until the served meta-release file has a new modification time."""
    deadline = time.monotonic() + 300
    while file_mtime(juju, META_RELEASE) == before:
        if time.monotonic() > deadline:
            pytest.fail("meta-release file was not updated")
        time.sleep(5)


@pytest.mark.juju_setup
def test_deploy(charm: pathlib.Path, juju: jubilant.Juju):
    """Deploy the charm and wait until it is active."""
    juju.deploy(charm, app=APP)
    juju.wait(jubilant.all_active, timeout=900, error=jubilant.any_error)


def test_workload_version_is_set(juju: jubilant.Juju):
    """Report the nginx version as the workload version."""
    version = juju.status().apps[APP].version
    assert run(juju, "nginx -v 2>&1").endswith(f"nginx/{version}")


def test_nginx_is_running(juju: jubilant.Juju):
    """Run nginx with a valid configuration and an open port."""
    assert run(juju, "systemctl is-active nginx") == "active"
    assert "syntax is ok" in run(juju, "nginx -t 2>&1")
    assert "80/tcp" in juju.status().apps[APP].units[UNIT].open_ports


def test_robots_txt_is_served(juju: jubilant.Juju):
    """Serve robots.txt from the repository."""
    assert http_get(juju, "/robots.txt") == pathlib.Path("files/robots.txt").read_text()


def test_meta_release_is_served(juju: jubilant.Juju):
    """Serve the meta-release files and the raspi directory."""
    for path in ("/meta-release", "/meta-release-lts", "/raspi/"):
        assert http_get(juju, path)


def test_pull_meta_release_action_pulls_main(juju: jubilant.Juju):
    """Pull the configured ref, which is main, again with the action."""
    before = file_mtime(juju, META_RELEASE)
    result = juju.run(UNIT, "pull-meta-release")
    assert result.results["result"] == "meta-release updated"
    wait_for_meta_release_update(juju, before)


def test_meta_release_ref_change_pulls_new_files(juju: jubilant.Juju):
    """Pull new files when the configured ref changes to HEAD."""
    before = file_mtime(juju, META_RELEASE)
    juju.config(APP, {"meta_release_ref": "HEAD"})
    wait_for_meta_release_update(juju, before)


def test_extractor_is_installed(juju: jubilant.Juju):
    """Run the installed extractor with --help."""
    output = run(juju, "python3 /usr/local/bin/lp-extract-changelogs --help")
    assert "--cache-dir" in output


def test_extractor_timer_is_enabled(juju: jubilant.Juju):
    """Enable the extractor timer with a six-hour schedule."""
    assert run(juju, "systemctl is-enabled lp-extract-changelogs.timer") == "enabled"
    assert "OnUnitActiveSec=6h" in run(juju, "systemctl cat lp-extract-changelogs.timer")


def test_cache_storage_is_mounted(juju: jubilant.Juju):
    """Mount the cache storage at the configured path."""
    assert "is a mountpoint" in run(juju, "mountpoint /var/cache/ubuntu-changelogs")


# Keep this test last because the changelog extractor is a heavier
# process than the others.
def test_pull_changelogs_action(juju: jubilant.Juju):
    """Trigger extraction with the action."""
    result = juju.run(UNIT, "pull-changelogs")
    assert result.results["result"] == "changelog extraction triggered"
    unit = juju.status().apps[APP].units[UNIT]
    assert unit.workload_status.current == "maintenance"
