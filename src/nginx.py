# Copyright 2026 Work
# See LICENSE file for licensing details.

"""Manage the nginx web server used by Ubuntu Changelogs."""

import logging
import shutil
import subprocess
from pathlib import Path

from charmlibs import apt

logger = logging.getLogger(__name__)


class Nginx:
    """Manage the nginx web server used by Ubuntu Changelogs."""

    CHARM_DIR = Path(__file__).parent.parent
    NGINX_CONFIG = CHARM_DIR / "files" / "nginx.conf"
    ROBOTS_TXT = CHARM_DIR / "files" / "robots.txt"
    DEFAULT_CONFIG = Path("/etc/nginx/sites-enabled/default")
    CUSTOM_CONFIG = Path("/etc/nginx/sites-enabled/index.conf")
    SERVING_DIR = Path("/var/www/changelogs.ubuntu.com")

    def install(self) -> None:
        """Install nginx through APT and apply static configuration."""
        apt.update()
        apt.add_package("nginx-core")

        # Apply configuration and create serving directory
        self.DEFAULT_CONFIG.unlink(missing_ok=True)
        shutil.copy2(self.NGINX_CONFIG, self.CUSTOM_CONFIG)
        self.SERVING_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("nginx installed and configured")

    def setup(self) -> None:
        """Copy static files into the serving directory."""
        shutil.copy2(self.ROBOTS_TXT, self.SERVING_DIR / "robots.txt")
        logger.info("static files copied to serving directory")

    def is_running(self) -> bool:
        """Return whether nginx is running."""
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "nginx"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def start(self) -> None:
        """Start nginx."""
        if self.is_running():
            self._systemctl("reload")
        else:
            self._systemctl("start")

    def stop(self) -> None:
        """Stop nginx."""
        self._systemctl("stop")

    def uninstall(self) -> None:
        """Uninstall nginx and remove the custom configuration."""
        apt.remove_package("nginx-core")
        self.CUSTOM_CONFIG.unlink(missing_ok=True)
        shutil.rmtree(self.SERVING_DIR, ignore_errors=True)

    def get_version(self) -> str:
        """Return the installed nginx version."""
        result = subprocess.run(["nginx", "-v"], check=True, capture_output=True, text=True)
        return result.stderr.removeprefix("nginx version: nginx/").strip()

    def get_serving_dir(self) -> Path:
        """Return the directory being served."""
        return self.SERVING_DIR

    def _systemctl(self, action: str) -> None:
        """Run a systemctl action against nginx and check for errors."""
        result = subprocess.run(
            ["systemctl", action, "nginx"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            logger.error("systemctl %s nginx failed: %s", action, details)
            raise RuntimeError(f"systemctl {action} nginx failed: {details}")
