# Copyright 2026 Canonical
# See LICENSE file for licensing details.

from pathlib import Path
from unittest.mock import Mock, call

from changelogs import Changelogs, TimerStatus


def test_install_copies_script_and_installs_packages(monkeypatch):
    add_package = Mock()
    monkeypatch.setattr("changelogs.apt.add_package", add_package)
    copy2 = Mock()
    monkeypatch.setattr("changelogs.shutil.copy2", copy2)
    check_call = Mock()
    monkeypatch.setattr("changelogs.subprocess.check_call", check_call)
    cache_dir = Mock()
    monkeypatch.setattr(Changelogs, "CACHE_DIR", cache_dir)
    state_dir = Mock()
    monkeypatch.setattr(Changelogs, "STATE_DIR", state_dir)

    changelogs = Changelogs(Mock())
    changelogs.install()

    assert add_package.call_args_list == [
        call("python3-launchpadlib"),
        call("python3-apt"),
        call("dpkg-dev"),
    ]
    cache_dir.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)
    state_dir.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
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


def test_extract_changelogs_updates_destination_in_place(monkeypatch):
    check_call = Mock()
    monkeypatch.setattr("changelogs.subprocess.check_call", check_call)

    changelogs = Changelogs(Path("/tmp/dest"))
    changelogs.extract_changelogs()

    check_call.assert_called_once_with(
        [
            "/usr/bin/python3",
            str(changelogs.SCRIPT_DEST),
            "--cache-dir",
            str(changelogs.CACHE_DIR),
            "--state-dir",
            str(changelogs.STATE_DIR),
            "--output-dir",
            "/tmp/dest/changelogs",
        ]
    )


def test_timer_status_running_returns_running(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=activating\nResult=success\nExecMainStatus=0\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.timer_status() is TimerStatus.RUNNING
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


def test_timer_status_failed_active_state_returns_failed(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=failed\nResult=exit-code\nExecMainStatus=1\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.timer_status() is TimerStatus.FAILED


def test_timer_status_non_success_result_returns_failed(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=inactive\nResult=timeout\nExecMainStatus=0\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.timer_status() is TimerStatus.FAILED


def test_timer_status_success_returns_ok(monkeypatch):
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=inactive\nResult=success\nExecMainStatus=0\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.timer_status() is TimerStatus.OK


def test_timer_status_never_run_returns_ok(monkeypatch):
    # A unit that has never run reports success with no meaningful exit status.
    run = Mock(
        return_value=Mock(
            stdout="ActiveState=inactive\nResult=success\nExecMainStatus=\n",
        )
    )
    monkeypatch.setattr("changelogs.subprocess.run", run)

    changelogs = Changelogs(Mock())

    assert changelogs.timer_status() is TimerStatus.OK


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
        call("python3-apt"),
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
