# Copyright 2026 Canonical
# See LICENSE file for licensing details.

from unittest.mock import Mock

import utils


def test_create_user_adds_system_account(monkeypatch):
    run = Mock(return_value=Mock(returncode=1))
    monkeypatch.setattr("utils.subprocess.run", run)
    check_call = Mock()
    monkeypatch.setattr("utils.subprocess.check_call", check_call)

    user = "user"
    utils.create_user(user)

    run.assert_called_once_with(
        ["getent", "passwd", user],
        capture_output=True,
        text=True,
    )
    check_call.assert_called_once_with(
        [
            "useradd",
            "--system",
            "--no-create-home",
            "--shell",
            "/usr/sbin/nologin",
            "--user-group",
            user,
        ]
    )


def test_create_user_skips_existing_account(monkeypatch):
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("utils.subprocess.run", run)
    check_call = Mock()
    monkeypatch.setattr("utils.subprocess.check_call", check_call)

    user = "user"
    utils.create_user(user)

    check_call.assert_not_called()


def test_create_dir_owns_root_owned_directory(monkeypatch, tmp_path):
    check_call = Mock()
    monkeypatch.setattr("utils.subprocess.check_call", check_call)

    path = tmp_path / "state"
    user = "user"
    group = "group"
    utils.create_dir(path, 0o700, user, group)

    assert path.is_dir()
    assert path.stat().st_mode & 0o777 == 0o700
    check_call.assert_called_once_with(["chown", "-R", "-h", f"{user}:{group}", str(path)])
