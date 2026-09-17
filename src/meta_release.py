# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Manage Ubuntu meta-release data."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from charmlibs import apt

logger = logging.getLogger(__name__)


class PullUpdatesError(Exception):
    """An exception class indicating the pull operation failed."""

    def __init__(self):
        super().__init__("failed to pull updates")


class MetaRelease:
    """Pull meta-release files from the repo and copy them to a destination directory."""

    REPOSITORY = "https://git.launchpad.net/meta-release"
    PUBLISHED_FILES = [
        "EOLReleaseAnnouncement",
        "meta-release",
        "meta-release-development",
        "meta-release-lts",
        "meta-release-lts-development",
        "meta-release-lts-proposed",
        "meta-release-proposed",
        "meta-release-unit-testing",
        "raspi",
    ]

    def __init__(self, destination: Path):
        self.destination = destination

    def install(self) -> None:
        """Install the tools required to retrieve meta-release data."""
        apt.add_package("git")
        logger.info(__name__ + ": dependencies installed")

    def pull_updates(self, ref: str) -> None:
        """Publish a fresh copy of the meta-release repository."""
        logger.info(
            "meta-release: cloning %s (ref: %s) into %s", self.REPOSITORY, ref, self.destination
        )
        temporary_directory = Path(tempfile.mkdtemp(prefix="ubuntu-changelogs-"))
        clone_directory = temporary_directory / "meta-release"
        try:
            subprocess.check_call(["git", "clone", self.REPOSITORY, str(clone_directory)])
            logger.info(__name__ + ": repository cloned")
            subprocess.check_call(
                [
                    "git",
                    "-C",
                    str(clone_directory),
                    "-c",  # Set config for suppressing detachedHead warning
                    "advice.detachedHead=false",
                    "checkout",
                    ref,
                ]
            )
            logger.info(__name__ + ": checked out ref %s", ref)
            self.destination.mkdir(parents=True, exist_ok=True)
            for name in self.PUBLISHED_FILES:
                source = clone_directory / name
                published = self.destination / name
                if source.is_dir():
                    shutil.copytree(source, published, dirs_exist_ok=True)
                    subprocess.check_call(["chown", "-R", "root:www-data", str(published)])
                elif source.is_file():
                    shutil.copy2(source, published)
                    subprocess.check_call(["chown", "root:www-data", str(published)])
                else:
                    raise FileNotFoundError(
                        f"expected published file '{name}' missing from {self.REPOSITORY}"
                    )
            logger.info(__name__ + ": copied all files")
        except subprocess.CalledProcessError as e:
            logger.error(__name__ + f": failed to clone repo: status code {e.returncode}")
            raise PullUpdatesError() from None
        finally:
            shutil.rmtree(temporary_directory, ignore_errors=True)

    def uninstall(self) -> None:
        """Uninstall the tools used to retrieve meta-release data."""
        apt.remove_package("git")
