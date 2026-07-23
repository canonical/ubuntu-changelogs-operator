#!/usr/bin/env python3
# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Charm the Ubuntu Changelogs service."""

import logging
import time

import ops
import pydantic

from changelogs import Changelogs, TimerStatus
from meta_release import MetaRelease
from nginx import Nginx

logger = logging.getLogger(__name__)


class CharmConfig(pydantic.BaseModel):
    """Charm configuration options."""

    meta_release_ref: str


class UbuntuChangelogsOperatorCharm(ops.CharmBase):
    """Charm the Ubuntu Changelogs service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.nginx = Nginx()
        self.meta_release = MetaRelease(self.nginx.get_serving_dir())
        self.changelogs = Changelogs(self.nginx.get_serving_dir())

        framework.observe(self.on.install, self._on_install)
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.on.update_status, self._on_update_status)
        framework.observe(self.on.stop, self._on_stop)
        framework.observe(self.on.remove, self._on_remove)

    def _on_install(self, event: ops.InstallEvent):
        """Install the workload on the machine."""
        self.unit.status = ops.MaintenanceStatus("installing ubuntu changelogs operator")
        try:
            self.nginx.install()
            self.meta_release.install()
            self.changelogs.install()
        except Exception:
            logger.exception("Error while installing Ubuntu changelogs dependencies")
            self.unit.status = ops.BlockedStatus(
                "failed installing ubuntu changelogs dependencies"
            )
            raise

        logger.info("Ubuntu changelogs dependencies installed")
        self.unit.status = ops.ActiveStatus("Ready")

    def _on_start(self, event: ops.StartEvent):
        """Start the workload."""
        self.unit.status = ops.MaintenanceStatus("starting services")
        self.nginx.start()
        self.unit.set_workload_version(self.nginx.get_version())
        logger.info("Services started")
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """React to configuration updates."""
        self.unit.status = ops.MaintenanceStatus("rolling out configuration")

        try:
            config = self.load_config(CharmConfig)
        except pydantic.ValidationError:
            logger.exception("Error while parsing configuration")
            self.unit.status = ops.BlockedStatus("failed parsing configuration")
            raise

        try:
            self.nginx.setup()
            self.meta_release.pull_updates(config.meta_release_ref)
        except Exception:
            logger.exception("Error while rolling out configuration")
            self.unit.status = ops.BlockedStatus("failed rolling out configuration")
            raise
        self.unit.status = ops.ActiveStatus("ready")

    def _on_update_status(self, event: ops.UpdateStatusEvent) -> None:
        """Report the health of the changelog extraction process."""
        status = self.changelogs.timer_status()
        if status is TimerStatus.RUNNING:
            logger.info("changelog extraction still in progress")
            self.unit.status = ops.MaintenanceStatus("extracting changelogs")
        elif status is TimerStatus.FAILED:
            logger.error("last changelog extraction failed")
            self.unit.status = ops.BlockedStatus("changelog extraction failed")
        else:
            self.unit.status = ops.ActiveStatus()

    def _on_stop(self, event: ops.StopEvent) -> None:
        """Stop the workload."""
        self.nginx.stop()
        for _ in range(3):
            if not self.nginx.is_running():
                return
            time.sleep(1)
        raise RuntimeError("nginx is still running after the expected time")

    def _on_remove(self, event: ops.RemoveEvent) -> None:
        """Remove the workload."""
        self.nginx.uninstall()
        self.changelogs.uninstall()


if __name__ == "__main__":  # pragma: nocover
    ops.main(UbuntuChangelogsOperatorCharm)
