# Copyright 2026 Canonical
# See LICENSE file for licensing details.

from pathlib import Path
from unittest.mock import Mock, call

import pytest

from changelogs import Changelogs, ServiceStatus


def test_install_copies_script_and_installs_packages(monkeypatch):
    add_package = Mock()
    monkeypatch.setattr("changelogs.apt.add_package", add_package)
    copy2 = Mock()
    monkeypatch.setattr("changelogs.shutil.copy2", copy2)
    check_call = Mock()
    monkeypatch.setattr("changelogs.subprocess.check_call", check_call)

    create_user = Mock()
    monkeypatch.setattr("utils.create_user", create_user)
    create_dir = Mock()
    monkeypatch.setattr("utils.create_dir", create_dir)
    destination = Path("/var/www/changelogs.ubuntu.com")

    changelogs = Changelogs(destination)
    changelogs.install()

    assert add_package.call_args_list == [
        call("python3-launchpadlib"),
        call("dpkg-dev"),
    ]
    create_user.assert_called_once_with(changelogs.USER)
    assert create_dir.call_args_list == [
        call(Changelogs.CACHE_DIR, 0o755, changelogs.USER, changelogs.GROUP),
        call(Changelogs.STATE_DIR, 0o700, changelogs.USER, changelogs.GROUP),
        call(destination / Changelogs.PUBLISH_DIR, 0o755, changelogs.USER, changelogs.GROUP),
    ]
    assert copy2.call_args_list == [
        call(changelogs.SCRIPT_SRC, changelogs.SCRIPT_DEST),
        call(changelogs.SERVICE_SRC, changelogs.SYSTEMD_DIR / changelogs.SERVICE_SRC.name),
        call(changelogs.TIMER_SRC, changelogs.SYSTEMD_DIR / changelogs.TIMER_SRC.name),
    ]
    assert check_call.call_args_list == [
        call(["chmod", "a+rwx,g-w,o-w", str(changelogs.SCRIPT_DEST)]),
        call(["systemctl", "daemon-reload"]),
        call(["systemctl", "enable", "--now", changelogs.TIMER_UNIT]),
    ]


def test_extractor_status_running_returns_running(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=activating\nResult=success\nExecMainStatus=0\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.extractor_status() is ServiceStatus.RUNNING
    run.assert_called_once_with(
        [
            "systemctl",
            "show",
            changelogs.SERVICE_UNIT,
            "--property=ActiveState,Result,ExecMainStatus",
        ],
        capture_output=True,
        text=True,
    )


def test_extractor_status_failed_active_state_returns_failed(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=failed\nResult=exit-code\nExecMainStatus=1\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.extractor_status() is ServiceStatus.FAILED


def test_extractor_status_non_success_result_returns_failed(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=inactive\nResult=timeout\nExecMainStatus=0\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.extractor_status() is ServiceStatus.FAILED


def test_extractor_status_success_returns_ok(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=inactive\nResult=success\nExecMainStatus=0\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.extractor_status() is ServiceStatus.OK


def test_extractor_status_never_run_returns_ok(monkeypatch):
    # A unit that has never run reports success with no meaningful exit status.
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=inactive\nResult=success\nExecMainStatus=\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.extractor_status() is ServiceStatus.OK


def test_run_extractor_starts_service(monkeypatch):
    run = Mock(return_value=Mock(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())
    changelogs.run_extractor()

    run.assert_called_once_with(
        ["systemctl", "start", "--no-block", changelogs.SERVICE_UNIT],
        capture_output=True,
        text=True,
    )


def test_run_extractor_raises_on_failure(monkeypatch):
    run = Mock(return_value=Mock(returncode=1, stdout="", stderr="boom"))
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())
    with pytest.raises(RuntimeError, match="boom"):
        changelogs.run_extractor()


def test_uninstall_removes_packages_and_script(monkeypatch):
    remove_package = Mock()
    monkeypatch.setattr("changelogs.apt.remove_package", remove_package)
    unlinked = []

    def record_unlink(self, *, missing_ok=False):
        unlinked.append((self, missing_ok))

    monkeypatch.setattr("changelogs.Path.unlink", record_unlink)
    rmtree = Mock()
    monkeypatch.setattr("changelogs.shutil.rmtree", rmtree)
    run = Mock()
    monkeypatch.setattr("changelogs.subprocess.run", run)
    check_call = Mock()
    monkeypatch.setattr("changelogs.subprocess.check_call", check_call)

    changelogs = Changelogs(Mock())
    changelogs.uninstall()

    run.assert_called_once_with(
        ["systemctl", "disable", "--now", changelogs.TIMER_UNIT],
    )
    check_call.assert_called_once_with(["systemctl", "daemon-reload"])
    assert remove_package.call_args_list == [
        call("python3-launchpadlib"),
        call("dpkg-dev"),
    ]
    assert unlinked == [
        (changelogs.SYSTEMD_DIR / changelogs.SERVICE_SRC.name, True),
        (changelogs.SYSTEMD_DIR / changelogs.TIMER_SRC.name, True),
        (changelogs.SCRIPT_DEST, True),
    ]
    assert rmtree.call_args_list == [
        call(changelogs.CACHE_DIR, ignore_errors=True),
        call(changelogs.STATE_DIR, ignore_errors=True),
    ]
