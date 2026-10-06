# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Behaviour tests for the Launchpad changelog crawler script."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

# --------------------------------------------------------------------------
# Fakes for the small part of Launchpad the crawler touches.
# --------------------------------------------------------------------------


def make_source(
    name="hello",
    version="1.0-1",
    component="main",
    status="Published",
    published=True,
    urls=(),
    binaries=(),
):
    """Build a fake Launchpad source publication."""
    return SimpleNamespace(
        source_package_name=name,
        source_package_version=version,
        component_name=component,
        status=status,
        date_published=datetime(2024, 1, 1, tzinfo=timezone.utc) if published else None,
        sourceFileUrls=lambda: list(urls),
        getPublishedBinaries=lambda: list(binaries),
    )


def make_binary(name, version, component="main"):
    """Build a fake Launchpad binary publication."""
    return SimpleNamespace(
        binary_package_name=name,
        binary_package_version=version,
        component_name=component,
    )


class FakePublishedSources(list):
    """The collection Launchpad returns, with the total_size the crawler reads."""

    @property
    def total_size(self):
        return len(self)


def make_crawler(lp, tmp_path, sources):
    """Build a crawler on temp dirs, wired to a fake archive that returns ``sources``."""
    (tmp_path / "state").mkdir(exist_ok=True)
    crawler = lp.LaunchpadChangelogsCrawler(
        cachedir=str(tmp_path / "cache"),
        statedir=str(tmp_path / "state"),
        targetdir=str(tmp_path / "out"),
    )
    archive = Mock()
    archive.getPublishedSources.return_value = FakePublishedSources(sources)
    crawler._launchpad = SimpleNamespace(
        distributions={"Ubuntu": SimpleNamespace(main_archive=archive)}
    )
    return crawler, archive


def source_file(tmp_path, name):
    """Write a file and return its ``file://`` URL, so downloads need no network."""
    path = tmp_path / "source" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text("fake source data")
    return path.as_uri()


def stub_dpkg_source(lp, monkeypatch, **files):
    """Replace the dpkg-source call with one that writes a small debian/ tree."""
    contents = files or {
        "changelog": "hello (1.0-1) unstable; urgency=medium\n",
        "copyright": "Copyright (c) 2024\n",
        "NEWS.Debian": "hello (1.0-1) unstable; urgency=medium\n",
    }

    def write_debian_tree(argv, stdout=None):
        unpackdir = Path(argv[-1])
        (unpackdir / "debian").mkdir(parents=True, exist_ok=True)
        for name, text in contents.items():
            (unpackdir / "debian" / name).write_text(text)
        return 0

    monkeypatch.setattr(lp, "subprocess", SimpleNamespace(call=write_debian_tree))


# --------------------------------------------------------------------------
# Small rules.
# --------------------------------------------------------------------------


def test_poolhash_keeps_four_characters_for_lib_packages(lp):
    assert lp.poolhash("libhello") == "libh"
    assert lp.poolhash("hello") == "h"


def test_source_version_drops_the_epoch(lp):
    source = lp.LaunchpadSourcePackage(None, make_source(version="1:2.3-1"))
    assert source.srcversion == "2.3-1"


def test_unpublished_source_is_not_published(lp):
    source = lp.LaunchpadSourcePackage(None, make_source(status="Pending", published=False))
    assert not source.published
    assert source.pending


def test_parse_arguments_defaults(lp):
    args = lp.parse_arguments([])
    assert args.cache_dir == "/var/cache/ubuntu-changelogs"
    assert args.state_dir == "/var/lib/ubuntu-changelogs"
    assert args.output_dir == "./changelogs"


def test_parse_arguments_accepts_overrides(lp):
    args = lp.parse_arguments(
        ["--cache-dir", "/cache", "--state-dir", "/state", "--output-dir", "/out"]
    )
    assert (args.cache_dir, args.state_dir, args.output_dir) == ("/cache", "/state", "/out")


# --------------------------------------------------------------------------
# Saved state.
# --------------------------------------------------------------------------


def test_last_check_is_read_with_eight_hour_overlap(lp, tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "last_check.txt").write_text("100000")

    crawler, archive = make_crawler(lp, tmp_path, [])

    assert crawler._time_of_last_check == 100000 - 8 * 60 * 60
    crawler.get_changelogs()
    overlap_start = datetime.fromtimestamp(100000 - 8 * 60 * 60).isoformat()
    archive.getPublishedSources.assert_called_once_with(
        order_by_date=True, created_since_date=overlap_start
    )


def test_write_last_check_date_saves_the_new_time(lp, tmp_path):
    crawler, _ = make_crawler(lp, tmp_path, [])
    crawler._time_of_last_check = 1234567890.0

    crawler.write_last_check_date()

    assert (tmp_path / "state" / "last_check.txt").read_text() == "1234567890.0"


# --------------------------------------------------------------------------
# Crawl scenarios.
# --------------------------------------------------------------------------


def test_first_crawl_extracts_changelog_files(lp, tmp_path, monkeypatch):
    """Test extraction for one source package"""
    crawler, _ = make_crawler(
        lp,
        tmp_path,
        [make_source(urls=[source_file(tmp_path, "hello_1.0-1.dsc")])],
    )
    stub_dpkg_source(lp, monkeypatch)

    assert crawler.get_changelogs() is True

    # Assert the files have been extracted
    pool = Path(crawler.targetdir) / "pool/main/h/hello/hello_1.0-1"
    assert (pool / "changelog").read_text().startswith("hello (1.0-1)")
    assert (pool / "copyright").exists()
    assert (pool / "NEWS.Debian").exists()
    assert crawler.extracted == 1
    assert crawler.failed == 0

    # Assert download cache has been cleaned up
    assert list(Path(crawler.downloads_cachedir).iterdir()) == []


def test_existing_changelog_is_skipped_and_binary_symlink_is_created(lp, tmp_path):
    """
    Test that:
    - existing changelogs are not extracted again
    - symlinks under the 'binary' directory are created the second time
      a package is found on launchpad
    """
    crawler, _ = make_crawler(
        lp,
        tmp_path,
        [make_source(binaries=[make_binary("hello-bin", "1.0-1")])],
    )
    pool = Path(crawler.targetdir) / "pool/main/h/hello/hello_1.0-1"
    pool.mkdir(parents=True)
    (pool / "changelog").write_text("already extracted")

    assert crawler.get_changelogs() is True

    assert crawler.skipped == 1
    assert crawler.extracted == 0
    assert crawler.symlinked == 1
    link = Path(crawler.targetdir) / "binary/h/hello-bin/1.0-1"
    assert link.is_symlink()
    assert link.resolve() == pool.resolve()


def test_unpublished_source_is_not_downloaded(lp, tmp_path, monkeypatch):
    """Don't fetch a package that is marked as unpublished on Launchpad"""
    crawler, _ = make_crawler(lp, tmp_path, [make_source(published=False)])
    fetch = Mock(return_value=True)
    monkeypatch.setattr(crawler, "_fetch_source", fetch)

    assert crawler.get_changelogs() is True

    fetch.assert_not_called()
    assert not (Path(crawler.targetdir) / "pool").exists()


def test_download_failure_is_counted_and_cleans_up(lp, tmp_path):
    """Complete failure means directories are not created and cache is cleaned up"""
    crawler, _ = make_crawler(lp, tmp_path, [make_source(urls=["file:///missing/hello_1.0-1.dsc"])])

    assert crawler.get_changelogs() is False

    assert crawler.failed == 1
    assert not (Path(crawler.targetdir) / "pool").exists()
    assert list(Path(crawler.downloads_cachedir).iterdir()) == []


def test_binary_lookup_network_error_is_counted(lp, tmp_path):
    """Test resilience to network errors, count them as failures"""
    source = make_source(binaries=[make_binary("hello-bin", "1.0-1")])
    source.getPublishedBinaries = Mock(side_effect=lp.urllib.error.URLError("network down"))
    crawler, _ = make_crawler(lp, tmp_path, [source])
    pool = Path(crawler.targetdir) / "pool/main/h/hello/hello_1.0-1"
    pool.mkdir(parents=True)
    (pool / "changelog").write_text("already extracted")

    assert crawler.get_changelogs() is False

    assert crawler.failed == 1
    assert crawler.symlinked == 0


def test_symlink_creation_error_is_counted(lp, tmp_path):
    """Failure to create symlinks counts as a generic failure"""
    crawler, _ = make_crawler(
        lp, tmp_path, [make_source(binaries=[make_binary("hello-bin", "1.0-1")])]
    )
    pool = Path(crawler.targetdir) / "pool/main/h/hello/hello_1.0-1"
    pool.mkdir(parents=True)
    (pool / "changelog").write_text("already extracted")
    # A plain file where the pool-hash directory belongs makes makedirs fail.
    (Path(crawler.targetdir) / "binary").mkdir()
    (Path(crawler.targetdir) / "binary/h").write_text("not a directory")

    assert crawler.get_changelogs() is False

    assert crawler.failed == 1
    assert crawler.symlinked == 0
