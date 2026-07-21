# Copyright 2026 Work
# See LICENSE file for licensing details.

from pathlib import Path
from unittest.mock import Mock, call

from changelogs import Changelogs


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
    assert copy2.called
    check_call.assert_called_once_with(
        ["chmod", "a+rwx,g-w,o-w", str(changelogs.SCRIPT_DEST)],
    )


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


def test_uninstall_removes_packages_and_script(monkeypatch):
    remove_package = Mock()
    monkeypatch.setattr("changelogs.apt.remove_package", remove_package)
    unlink = Mock()
    monkeypatch.setattr("changelogs.Path.unlink", unlink)
    rmtree = Mock()
    monkeypatch.setattr("changelogs.shutil.rmtree", rmtree)

    changelogs = Changelogs(Mock())
    changelogs.uninstall()

    assert remove_package.call_args_list == [
        call("python3-launchpadlib"),
        call("python3-apt"),
        call("dpkg-dev"),
    ]
    unlink.assert_called_once_with(missing_ok=True)
    assert rmtree.call_args_list == [
        call(changelogs.CACHE_DIR, ignore_errors=True),
        call(changelogs.STATE_DIR, ignore_errors=True),
    ]
