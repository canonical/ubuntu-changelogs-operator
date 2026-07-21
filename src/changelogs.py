# Copyright 2026 Work
# See LICENSE file for licensing details.

"""Manage package changelog data."""

import logging
import shutil
import subprocess
from pathlib import Path

from charmlibs import apt

logger = logging.getLogger(__name__)


class Changelogs:
    """Extract package changelogs from Launchpad."""

    CHARM_DIR = Path(__file__).parent.parent
    SCRIPT_SRC = CHARM_DIR / "files" / "lp-extract-changelogs.py"
    SCRIPT_DEST = Path("/usr/local/bin/lp-extract-changelogs")
    CACHE_DIR = Path("/var/cache/ubuntu-changelogs/lp-cache")
    STATE_DIR = Path("/var/lib/ubuntu-changelogs")
    PACKAGES = ["python3-launchpadlib", "python3-apt", "dpkg-dev"]

    def __init__(self, destination: Path):
        self.destination = destination

    def install(self) -> None:
        """Install the tools required to retrieve package changelogs."""
        for package in self.PACKAGES:
            apt.add_package(package)
        self.CACHE_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
        self.STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(self.SCRIPT_SRC, self.SCRIPT_DEST)
        subprocess.check_call(["chmod", "a+rwx,g-w,o-w", str(self.SCRIPT_DEST)])
        logger.info("changelog dependencies installed")

    def extract_changelogs(self) -> None:
        """Extract changelogs from Launchpad into the destination directory."""
        destination = self.destination / "changelogs"
        subprocess.check_call(
            [
                "/usr/bin/python3",
                str(self.SCRIPT_DEST),
                "--cache-dir",
                str(self.CACHE_DIR),
                "--state-dir",
                str(self.STATE_DIR),
                "--output-dir",
                str(destination),
            ]
        )
        logger.info("changelogs extracted into %s", destination)

    def uninstall(self) -> None:
        """Uninstall the tools used to retrieve package changelogs."""
        for package in self.PACKAGES:
            apt.remove_package(package)
        self.SCRIPT_DEST.unlink(missing_ok=True)
        shutil.rmtree(self.CACHE_DIR, ignore_errors=True)
        shutil.rmtree(self.STATE_DIR, ignore_errors=True)
