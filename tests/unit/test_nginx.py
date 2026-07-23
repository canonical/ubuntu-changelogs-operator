# Copyright 2026 Canonical
# See LICENSE file for licensing details.

from unittest.mock import Mock

import nginx
from nginx import Nginx


def test_get_version_reads_nginx_stderr(monkeypatch):
    """Nginx writes its version to stderr."""
    run = Mock(return_value=Mock(stderr="nginx version: nginx/1.28.0 (Ubuntu)\n"))
    monkeypatch.setattr(nginx.subprocess, "run", run)

    assert Nginx().get_version() == "1.28.0 (Ubuntu)"
    run.assert_called_once_with(["nginx", "-v"], check=True, capture_output=True, text=True)
