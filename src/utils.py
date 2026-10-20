# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Misc utility functions."""

import subprocess
from pathlib import Path


def create_dir(path: Path, mode: int, user: str, group: str) -> None:
    """Create a directory, set up mode and ownership."""
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)
    subprocess.check_call(["chown", "-R", "-h", f"{user}:{group}", str(path)])


def create_user(user: str) -> None:
    """Create a user."""
    result = subprocess.run(
        ["getent", "passwd", user],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    subprocess.check_call(
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
