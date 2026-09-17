#!/usr/bin/env python3
# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Charm the Ubuntu Changelogs service."""

import logging
import time

import ops
import pydantic
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
    IngressPerAppRequirer,
)

from changelogs import Changelogs, ServiceStatus
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
        self.meta_release = MetaRelease(self.nginx.SERVING_DIR)
        self.changelogs = Changelogs(self.nginx.SERVING_DIR)

        self.ingress_changelogs = IngressPerAppRequirer(
            charm=self,
            port=self.nginx.PORT,
            strip_prefix=True,
            relation_name="ingress_changelogs",
        )

        framework.observe(self.on.install, self._on_install)
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.on.update_status, self._on_update_status)
        framework.observe(self.on.stop, self._on_stop)
        framework.observe(self.on.remove, self._on_remove)
        framework.observe(self.on.pull_changelogs_action, self._on_pull_changelogs)
        framework.observe(self.ingress_changelogs.on.ready, self._on_ingress_ready)

    def _on_install(self, event: ops.InstallEvent):
        """Install the workload on the machine."""
        self.unit.status = ops.MaintenanceStatus("installing ubuntu changelogs operator")
        try:
            self.nginx.install()
            self.meta_release.install()
            self.changelogs.install()
        except Exception:
            logger.exception(__name__ + ": error while installing Ubuntu changelogs dependencies")
            self.unit.status = ops.BlockedStatus(
                "failed installing ubuntu changelogs dependencies"
            )
            raise

        logger.info(__name__ + ": ubuntu changelogs dependencies installed")
        self.unit.status = ops.ActiveStatus("Ready")

    def _on_start(self, event: ops.StartEvent):
        """Start the workload."""
        self.unit.status = ops.MaintenanceStatus("starting services")
        self.nginx.start()
        self.unit.set_workload_version(self.nginx.get_version())
        logger.info(__name__ + ": services started")
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """React to configuration updates."""
        self.unit.status = ops.MaintenanceStatus("rolling out configuration")

        try:
            config = self.load_config(CharmConfig)
        except pydantic.ValidationError:
            logger.exception(__name__ + ": error while parsing configuration")
            self.unit.status = ops.BlockedStatus("failed parsing configuration")
            raise

        try:
            self.nginx.setup()
            self.meta_release.pull_updates(config.meta_release_ref)
        except Exception as e:
            logger.error(__name__ + f": error while rolling out configuration: {e}")
            self.unit.status = ops.MaintenanceStatus("failed rolling out configuration")
            event.defer()
            return

        logger.info(__name__ + ": configuration successfully updated")
        self.unit.status = ops.ActiveStatus("ready")

    def _on_update_status(self, event: ops.UpdateStatusEvent) -> None:
        """Report the health of the changelog extraction process."""
        status = self.changelogs.extractor_status()
        if status is ServiceStatus.RUNNING:
            logger.info(__name__ + ": changelog extraction still in progress")
            self.unit.status = ops.MaintenanceStatus("extracting changelogs")
        elif status is ServiceStatus.FAILED:
            logger.error(__name__ + ": last changelog extraction failed")
            self.unit.status = ops.MaintenanceStatus("changelog extraction failed")
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
        logger.info(__name__ + ": services removed")

    def _on_pull_changelogs(self, event: ops.ActionEvent) -> None:
        """Handle the pull-changelogs action."""
        try:
            self.changelogs.run_extractor()
        except Exception as e:
            logger.exception(__name__ + ": pull-changelogs action failed")
            event.fail(f"failed to trigger changelog extraction: {e}")
            return
        event.set_results({"result": "changelog extraction triggered"})
        # We set the unit on a maintenance status, which will be cleaned
        # up by the on-update-status hook.
        self.unit.status = ops.MaintenanceStatus("extracting changelogs")

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent):
        """Handle the ingress connection."""
        logger.info(__name__ + ": ingress is ready. URL: %s", event.url)
        hostname: str | None = self.config.get("hostname")  # type: ignore[assignment]
        self.ingress_changelogs.provide_ingress_requirements(
            port=self.nginx.PORT,
            host=hostname,
        )
        logger.info(__name__ + ": ingress successfully configured")


if __name__ == "__main__":  # pragma: nocover
    ops.main(UbuntuChangelogsOperatorCharm)
