#!/usr/bin/env python3
# Copyright 2026 Work
# See LICENSE file for licensing details.

"""Charm the Ubuntu Changelogs service."""

import logging
import time

import ops

import nginx

logger = logging.getLogger(__name__)


class UbuntuChangelogsOperatorCharm(ops.CharmBase):
    """Charm the Ubuntu Changelogs service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on.install, self._on_install)
        framework.observe(self.on.start, self._on_start)
        # self.framework.observe(self.on.config_changed, self._on_config_changed):q
        framework.observe(self.on.stop, self._on_stop)
        framework.observe(self.on.remove, self._on_remove)

    def _on_install(self, event: ops.InstallEvent):
        """Install the workload on the machine."""
        self.unit.status = ops.MaintenanceStatus("installing ubuntu changelogs operator")
        try:
            nginx.install()
        except Exception as error:
            logger.error("Error while installing Ubuntu changelogs dependencies")
            self.unit.status = ops.BlockedStatus(
                f"failed installing ubuntu changelogs dependencies: {error}"
            )
            raise

        logger.info("Ubuntu changelogs dependencies installed")
        self.unit.status = ops.ActiveStatus("Ready")

    def _on_start(self, event: ops.StartEvent):
        """Start the workload."""
        self.unit.status = ops.MaintenanceStatus("starting services")
        nginx.start()
        self.unit.set_workload_version(nginx.get_version())
        logger.info("Services started")
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        # self.unit.status = ops.MaintenanceStatus("rolling out configuration")
        # self.unit.status = ops.ActiveStatus("ready")
        pass

    def _on_stop(self, event: ops.StopEvent) -> None:
        """Stop the workload."""
        nginx.stop()
        for _ in range(3):
            if not nginx.is_running():
                return
            time.sleep(1)
        raise RuntimeError("nginx is still running after the expected time")

    def _on_remove(self, event: ops.RemoveEvent) -> None:
        """Remove the workload."""
        nginx.uninstall()


if __name__ == "__main__":  # pragma: nocover
    ops.main(UbuntuChangelogsOperatorCharm)
