# Copyright 2026 Work
# See LICENSE file for licensing details.

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock


def load_crawler_module(monkeypatch):
    apt_pkg = ModuleType("apt_pkg")
    setattr(apt_pkg, "get_lock", Mock())
    monkeypatch.setitem(sys.modules, "apt_pkg", apt_pkg)

    launchpadlib = ModuleType("launchpadlib")
    credentials = ModuleType("launchpadlib.credentials")
    setattr(credentials, "Credentials", Mock)
    launchpad = ModuleType("launchpadlib.launchpad")
    setattr(launchpad, "Launchpad", Mock)
    monkeypatch.setitem(sys.modules, "launchpadlib", launchpadlib)
    monkeypatch.setitem(sys.modules, "launchpadlib.credentials", credentials)
    monkeypatch.setitem(sys.modules, "launchpadlib.launchpad", launchpad)

    script = Path(__file__).parents[2] / "files" / "lp-extract-changelogs.py"
    spec = importlib.util.spec_from_file_location("lp_extract_changelogs", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_arguments_documents_storage_directories(monkeypatch):
    crawler = load_crawler_module(monkeypatch)

    defaults = crawler.parse_arguments([])
    assert defaults.cache_dir == "/var/cache/ubuntu-changelogs/lp-cache"
    assert defaults.state_dir == "/var/lib/ubuntu-changelogs"
    assert defaults.output_dir == "./changelogs"

    arguments = crawler.parse_arguments(
        ["--cache-dir", "/cache", "--state-dir", "/state", "--output-dir", "/output"]
    )
    assert arguments.cache_dir == "/cache"
    assert arguments.state_dir == "/state"
    assert arguments.output_dir == "/output"


def test_crawler_uses_persistent_state_directory(monkeypatch, tmp_path):
    crawler_module = load_crawler_module(monkeypatch)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    last_check = state_dir / "last_check.txt"
    last_check.write_text("100000")

    crawler = crawler_module.LaunchpadChangelogsCrawler(
        cachedir="/cache", statedir=state_dir, targetdir="/output"
    )

    assert crawler.lp_cachedir == "/cache"
    assert crawler.credentials_file == str(state_dir / "lp-credential.txt")
    assert crawler.last_check_file == str(last_check)
    assert crawler.targetdir == "/output"
    assert crawler._time_of_last_check == 100000 - 8 * 60 * 60

    crawler._time_of_last_check = 200000
    crawler.write_last_check_date()
    assert last_check.read_text() == "200000"


def test_fetch_source_handles_network_error(monkeypatch, tmp_path):
    crawler_module = load_crawler_module(monkeypatch)
    urlopen = Mock(side_effect=crawler_module.urllib.error.URLError("network unreachable"))
    monkeypatch.setattr(crawler_module.urllib.request, "urlopen", urlopen)
    crawler = crawler_module.LaunchpadChangelogsCrawler(statedir=tmp_path)

    assert not crawler._fetch_source(["https://example.test/source.dsc"], tmp_path)
    urlopen.assert_called_once_with(
        "https://example.test/source.dsc", timeout=crawler_module.DOWNLOAD_TIMEOUT
    )


def test_failed_fetch_is_counted_and_temporary_directory_is_removed(monkeypatch, tmp_path):
    crawler_module = load_crawler_module(monkeypatch)
    crawler = crawler_module.LaunchpadChangelogsCrawler(statedir=tmp_path)
    monkeypatch.setattr(crawler, "_fetch_source", Mock(return_value=False))
    temporary_directory = tmp_path / "download"
    temporary_directory.mkdir()
    monkeypatch.setattr(
        crawler_module.tempfile, "mkdtemp", Mock(return_value=str(temporary_directory))
    )
    rmtree = Mock()
    monkeypatch.setattr(crawler_module.shutil, "rmtree", rmtree)
    source = Mock(srcurls=[], srcname="package", srcversion="1.0")

    assert not crawler._unpack_changelogs_to_target(source, str(tmp_path / "output"))
    assert crawler.failed == 1
    rmtree.assert_called_once_with(str(temporary_directory), ignore_errors=True)
