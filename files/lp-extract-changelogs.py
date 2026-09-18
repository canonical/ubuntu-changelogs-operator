#!/usr/bin/python3
"""Get changelogs, NEWS.Debian and copyright directly from LP instead of crawling the archive."""

import argparse
import datetime
import glob
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import apt_pkg
from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad

LOCK_FILE = "/run/lock/lp-extract-changelogs.lock"
DEFAULT_CACHE_DIR = "/var/cache/ubuntu-changelogs/lp-cache"
DEFAULT_STATE_DIR = "/var/lib/ubuntu-changelogs"
DEFAULT_OUTPUT_DIR = "./changelogs"
DOWNLOAD_TIMEOUT = 30
SERVICE_ROOT = "production"
LP_CRAWLER_TMPDIR_PREFIX = "lp-crawler-"

# get all uploads (including all distro series and all pockets)
# for this distribution since a given date
DISTRIBUTION = "Ubuntu"


def debug_print_lp(lp_object):
    """Print debug information for a lp object."""
    print(f"name: {lp_object.__class__.__name__}")
    print(f"attributes: {sorted(lp_object.lp_attributes)}")
    print(f"collections: {sorted(lp_object.lp_collections)}")
    print(f"entries: {sorted(lp_object.lp_entries)}")
    print(f"operations: {sorted(lp_object.lp_operations)}")
    print("")


def cleanup_tmpdirs():
    try:
        dirs = glob.glob(f"/tmp/{LP_CRAWLER_TMPDIR_PREFIX}*")
        for dir in dirs:
            shutil.rmtree(dir)
        if len(dirs) > 0:
            logging.info("cleaned up temp dirs")
    except Exception as error:
        logging.error("failed to cleanup temp dirs: %s", error)


def poolhash(name):
    if name.startswith("lib"):
        return name[0:4]
    else:
        return name[0:1]


class LaunchpadSourcePackage:
    """Represents a launchpad source package."""

    # arches and pool
    SUPPORTED_ARCHES = ["i386", "amd64"]

    def __init__(self, launchpad, lp_source):
        self._launchpad = launchpad
        self._lp_source = lp_source
        self._srcname = self._lp_source.source_package_name
        self._srcver = self._lp_source.source_package_version
        # srip epoch, just like the other changelog extractors
        if ":" in self._srcver:
            self._srcver = self._srcver.split(":")[1]
        self._srcurls = self._lp_source.sourceFileUrls()
        self._srcomponent = self._lp_source.component_name

    @property
    def published(self):
        return self._lp_source.date_published is not None

    @property
    def pending(self):
        return self.status == "Pending"

    @property
    def status(self):
        return self._lp_source.status

    @property
    def srcname(self):
        return self._srcname

    @property
    def srcversion(self):
        return self._srcver

    @property
    def srcurls(self):
        return self._srcurls

    @property
    def srccomponent(self):
        return self._srcomponent

    @property
    def binary_packages_versions_components(self):
        binaries = set()
        for binary in self._lp_source.getPublishedBinaries():
            binaries.add(
                (
                    binary.binary_package_name,
                    binary.binary_package_version,
                    binary.component_name,
                )
            )
        return binaries

    def __str__(self):
        src = self._lp_source
        return f"{src.source_package_name}: {src.source_package_version} ({src.date_published})"


class LaunchpadChangelogsCrawler:
    """A crawler that can find out about changed packages in LP."""

    # LP service name (free form)
    SERVICE_NAME = "get_changelogs"

    # the files we are interested in
    CHANGELOG_EXTRACT_FILES = ["copyright", "changelog", "NEWS.Debian"]

    def __init__(
        self,
        cachedir=DEFAULT_CACHE_DIR,
        statedir=DEFAULT_STATE_DIR,
        targetdir=DEFAULT_OUTPUT_DIR,
    ):
        self.lp_cachedir = os.path.abspath(cachedir)
        self.credentials_file = os.path.join(os.path.abspath(statedir), "lp-credential.txt")
        self.last_check_file = os.path.join(os.path.abspath(statedir), "last_check.txt")
        self._launchpad = None
        self.targetdir = targetdir
        # statistics
        self.skipped = 0
        self.extracted = 0
        self.symlinked = 0
        self.failed = 0
        # date
        self._time_of_last_check = 0
        if os.path.exists(self.last_check_file):
            with open(self.last_check_file, "r") as fd:
                self._time_of_last_check = float(fd.read().strip())
            # be paranoid and subtract 8h, it seems like we miss
            # packages otherwise (LP: #685814, #372270)
            self._time_of_last_check -= 8 * 60 * 60
        else:
            logging.warning("assuming last check 30 days ago")
            logging.warning(
                "MAKE SURE THAT YOU POPULATED THE CHANGELOGS FROM A DIFFERENT SOURCE INITIALLY"
            )
            self._time_of_last_check = time.time() - 30 * 24 * 60 * 60

    def login(self):
        """Login and figure out if interactive or token login can be used."""
        # credentials.load and credentials.save were misbehaving on new
        # launchpadlib, and per webops, we can get away with using this
        # service anonymously.  Fix the "right way" if it becomes a
        # problem.

        # if not os.path.exists(self.credentials_file):
        #    self.login_interactive()
        # else:
        #    self.login_with_token(self.credentials_file)

        service = SERVICE_ROOT
        self._launchpad = Launchpad.login_anonymously(self.SERVICE_NAME, service, self.lp_cachedir)

    def login_interactive(self):
        service = SERVICE_ROOT
        self._launchpad = Launchpad.get_token_and_login(
            self.SERVICE_NAME, service, self.lp_cachedir
        )
        with open(self.credentials_file, "w+") as fd:
            self._launchpad.credentials.save(fd)

    def login_with_token(self, credentials_file):
        service = SERVICE_ROOT
        credentials = Credentials()
        with open(credentials_file, "r") as fd:
            credentials.load(fd)
        self._launchpad = Launchpad(credentials, service, self.lp_cachedir)

    def get_changelogs(self):
        ubuntu = self._launchpad.distributions[DISTRIBUTION]
        archive = ubuntu.main_archive
        date = datetime.datetime.fromtimestamp(self._time_of_last_check)
        logging.info(f"last checked: {date}")
        self.get_changelogs_since(archive, date.isoformat())
        return self.failed == 0

    def get_changelogs_since(self, archive, date):
        self._time_of_last_check = time.time()
        now = time.time()
        # It's important to omit the status filter here, even if we find
        # ourselves filtering on the status later.  This is because the
        # collection may change as we're iterating over it.  Without any
        # filtering, this is OK because entries can never be removed from
        # the collection: the worst case is that we encounter the same
        # publication twice.  With filtering on mutable properties, it would
        # be possible to lose entries between two successive batches.
        changed = archive.getPublishedSources(order_by_date=True, created_since_date=date)
        logging.debug(f"getPublishedSources() took {time.time() - now} seconds")
        self._get_changelogs_from_source_package_history_collection(changed)

    def _get_changelogs_from_source_package_history_collection(self, changed):
        logging.info(f"packages to check: {changed.total_size}")
        progress_threshold = min(int(changed.total_size / 10), 100)
        progress_count = 0
        start_time = time.time()
        for source_raw in changed:
            progress_count += 1
            if progress_count % progress_threshold == 0:
                logging.info(f"processed {progress_count} packages...")

            s = LaunchpadSourcePackage(self._launchpad, source_raw)
            logging.debug(f"source package: '{s}'")

            if s.pending:
                logging.debug(f"{s.srcname} {s.srcversion} in PENDING state")
            if not s.published:
                logging.debug(f"{s.srcname} in state {s.status}")
                continue

            dest = (
                f"{self.targetdir}/pool/{s.srccomponent}/{poolhash(s.srcname)}"
                f"/{s.srcname}/{s.srcname}_{s.srcversion}"
            )

            if not self._unpack_changelogs_to_target(s, dest):
                continue

        duration = time.time() - start_time
        logging.info(f"extracted {self.extracted} changelogs in {duration} seconds")
        return True

    def _unpack_changelogs_to_target(self, s, dest):
        # check if we have the data for this already
        if os.path.exists(os.path.join(dest, "changelog")):
            logging.debug(f"skipping already existing '{dest}'")
            self.skipped += 1
            if self._create_binary_symlinks(s, dest):
                self.symlinked += 1
            return False

        # fetch/unpack
        tmpdir = tempfile.mkdtemp(prefix=LP_CRAWLER_TMPDIR_PREFIX)
        try:
            if not self._fetch_source(s.srcurls, tmpdir):
                logging.error(f"{s.srcname} {s.srcversion} failed to fetch")
                self.failed += 1
                return False
            unpackdir = os.path.join(tmpdir, "target/")
            if not self._unpack_source(unpackdir, tmpdir):
                logging.error(f"{s.srcname} {s.srcversion} failed to unpack in {tmpdir}")
                self.failed += 1
                return False

            # extract interesting data
            if os.path.exists(os.path.join(unpackdir, "debian/changelog")):
                logging.debug(f"extracting changelog for {s.srcname} {s.srcversion}")
                self.extracted += 1
                # add primary dir (based on src data)
                for f in self.CHANGELOG_EXTRACT_FILES:
                    src = f"{unpackdir}/debian/{f}"
                    if os.path.exists(src):
                        if not os.path.exists(dest):
                            # broken symlink, get rid of them
                            if os.path.islink(dest):
                                logging.debug(f"removing broken symlink '{dest}'")
                                os.remove(dest)
                            os.makedirs(dest)
                        logging.debug(f"extracting '{src}' to '{dest}'")
                        shutil.copy(src, dest)
            else:
                logging.error(f"{s.srcname} - {s.srcversion} has no debian/changelog")
                self.failed += 1
                return False

            return True
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _fetch_source(self, srcurls, tmpdir):
        for url in srcurls:
            target = os.path.join(
                tmpdir, urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
            )
            try:
                logging.debug(f"Retrieving '{url}' to '{target}'")
                with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
                    with open(target, "wb") as fd:
                        shutil.copyfileobj(response, fd)
            except urllib.error.HTTPError as error:
                logging.error("failed to retrieve %s: HTTP %s", url, error.code)
                return False
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                logging.error("failed to retrieve %s: %s", url, error)
                return False
        return True

    def _unpack_source(self, unpackdir, tmpdir):
        dsc = glob.glob(f"{tmpdir}/*.dsc")
        if len(dsc) != 1:
            logging.error("expected one .dsc file in %s, found %d", tmpdir, len(dsc))
            return False
        with open(os.path.devnull, "w") as devnull:
            res = subprocess.call(
                ["dpkg-source", "--no-check", "-x", dsc[0], unpackdir],
                stdout=devnull,
            )
        return res == 0

    def _create_binary_symlinks(self, source, dest):
        linked = False
        # Separate symlink allowing for direct binary + version lookup
        # without requiring the binary component too
        for binary, version, comp in source.binary_packages_versions_components:
            lnkdir = f"{self.targetdir}/binary/{poolhash(binary)}/{binary}"
            lnk = f"{lnkdir}/{version}"
            if not os.path.exists(lnk):
                # broken symlink, get rid of them
                if os.path.islink(lnk):
                    logging.debug(f"removing broken symlink '{dest}'")
                    os.remove(lnk)
                logging.debug(f"create compat symlink '{dest}' -> '{lnk}'")
                if not os.path.exists(lnkdir):
                    os.makedirs(lnkdir)
                os.symlink(os.path.abspath(dest), lnk)
                linked = True
        return linked

    def write_last_check_date(self):
        with open(self.last_check_file, "w+") as fd:
            fd.write(str(self._time_of_last_check))


def parse_arguments(arguments=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="lp-extract-changelogs",
        description="Extract package changelogs from Launchpad.",
    )
    parser.add_argument("-d", "--debug", action="store_true", help="enable debug logging")
    parser.add_argument(
        "-c",
        "--cache-dir",
        dest="cache_dir",
        default=DEFAULT_CACHE_DIR,
        help="directory used for the Launchpad API cache",
    )
    parser.add_argument(
        "-s",
        "--state-dir",
        default=DEFAULT_STATE_DIR,
        help="directory used for persistent crawler state",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="directory where changelog data is written",
    )
    return parser.parse_args(arguments)


def handle_sigterm(signum, frame):
    logging.info("SIGTERM received, performing cleanup")
    cleanup_tmpdirs()
    sys.exit(0)


if __name__ == "__main__":
    args = parse_arguments()

    LOGGING_FORMAT = "%(asctime)s:%(process)d:%(message)s"
    if args.debug:
        logging.basicConfig(format=LOGGING_FORMAT, level=logging.DEBUG)
    else:
        logging.basicConfig(format=LOGGING_FORMAT, level=logging.INFO)

    lock = apt_pkg.get_lock(LOCK_FILE)
    if lock < 0:
        logging.warning("another extractor is running, exiting")
        sys.exit(1)

    # try to cleanup stray tempdirs and set SIGTERM handler
    cleanup_tmpdirs()
    signal.signal(signal.SIGTERM, handle_sigterm)

    # set a sensible default timeout to avoid hanging forever
    socket.setdefaulttimeout(120)

    logging.info("starting Launchpad changelog crawler")
    c = LaunchpadChangelogsCrawler(
        cachedir=args.cache_dir,
        statedir=args.state_dir,
        targetdir=args.output_dir,
    )
    c.login()
    success = c.get_changelogs()
    if success:
        c.write_last_check_date()
    os.close(lock)
    logging.info(
        "skipped: %d, extracted: %d, symlinked: %d, failed: %d",
        c.skipped,
        c.extracted,
        c.symlinked,
        c.failed,
    )
    if not success:
        logging.error("crawl incomplete; last check time was not updated")
        cleanup_tmpdirs()
        sys.exit(1)

    # test code
    # ubuntu = c._launchpad.distributions[DISTRIBUTION]
    # archive = ubuntu.main_archive
    # c.get_changelogs_from_source_packages(archive, ["acct"])
