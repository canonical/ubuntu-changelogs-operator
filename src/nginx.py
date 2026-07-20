# Copyright 2026 Work
# See LICENSE file for licensing details.

"""Manage the nginx web server used by Ubuntu Changelogs."""

import logging
import shutil
import subprocess
from pathlib import Path

from charmlibs import apt

logger = logging.getLogger(__name__)

CHARM_DIR = Path(__file__).parent.parent
NGINX_CONFIG = CHARM_DIR / "files" / "nginx.conf"
DEFAULT_CONFIG = Path("/etc/nginx/sites-enabled/default")
CUSTOM_CONFIG = Path("/etc/nginx/sites-enabled/index.conf")
SERVING_DIR = Path("/var/www/changelogs.ubuntu.com")


def install() -> None:
    """Install nginx through APT and apply static configuration."""
    apt.update()
    apt.add_package("nginx-core")

    # Apply configuration and create serving directory
    DEFAULT_CONFIG.unlink(missing_ok=True)
    shutil.copy2(NGINX_CONFIG, CUSTOM_CONFIG)
    SERVING_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("nginx installed and configured")


def is_running() -> bool:
    """Return whether nginx is running."""
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", "nginx"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def start() -> None:
    """Start nginx."""
    if is_running():
        _systemctl("reload")
    else:
        _systemctl("start")


def stop() -> None:
    """Stop nginx."""
    _systemctl("stop")


def uninstall() -> None:
    """Uninstall nginx and remove the custom configuration."""
    apt.remove_package("nginx-core")
    CUSTOM_CONFIG.unlink(missing_ok=True)
    shutil.rmtree(SERVING_DIR, ignore_errors=True)


def get_version() -> str:
    """Return the installed nginx version."""
    result = subprocess.run(["nginx", "-v"], check=True, capture_output=True, text=True)
    return result.stderr.removeprefix("nginx version: nginx/").strip()


def get_serving_dir() -> Path:
    """Return the directory being served."""
    return SERVING_DIR


def _systemctl(action: str) -> None:
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
