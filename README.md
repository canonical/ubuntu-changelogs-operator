# Ubuntu Changelogs Operator

Ubuntu Changelogs Operator is a [charm](https://juju.is/charms-architecture) for
deploying https://changelogs.ubuntu.com/. The server publishes:
- Ubuntu release data from the Launchpad `meta-release` repository.
- Package changelogs and copyright files from the Launchpad archive.

| Item | Value |
| --- | --- |
| Charm name | `ubuntu-changelogs` |
| Base | Ubuntu 26.04 |
| Architectures | amd64, arm64 |
| Minimum Juju version | 3.6 |

## What the charm does

The charm installs nginx and serves files from `/var/www/changelogs.ubuntu.com`
on port 80.

- On install, the charm installs nginx, git, `python3-launchpadlib`, and
  `dpkg-dev`. It also writes the nginx configuration.
- On config change, the charm copies `robots.txt` and clones the
  `meta-release` repository at `meta_release_ref`.
- Every 6 hours, a timer runs the changelog extractor. The extractor gets new
  source packages from Launchpad and writes `changelog`, `NEWS.Debian`, and
  `copyright` files under `/changelogs/`.
- When Juju checks the unit status (usually every 5 minutes), the charm reports
  if the extractor is running or if the last run failed.

The application needs:

- Network access to Launchpad and the Ubuntu package archive.
- `cache` storage of at least 50 GB.

The application uses these directories:

| Path | Contents |
| --- | --- |
| `/var/www/changelogs.ubuntu.com` | Served files. |
| `/var/cache/ubuntu-changelogs` | Launchpad API cache and temporary downloads. |
| `/var/lib/ubuntu-changelogs` | Extractor state, including the last check time. |

## Source layout

| Path | Purpose |
| --- | --- |
| `src/charm.py` | Handles Juju events and unit status. |
| `src/nginx.py` | Installs, configures, and controls nginx. |
| `src/meta_release.py` | Clones the meta-release repository and publishes its files. |
| `src/changelogs.py` | Manages the timer, the service, and the extractor script. |
| `files/lp-extract-changelogs.py` | Gets package files from Launchpad. |
| `files/nginx.conf` | nginx site configuration. |
| `files/robots.txt` | Crawler rules, served at `/robots.txt`. |
| `files/lp-extract-changelogs.service` | Runs the extractor. |
| `files/lp-extract-changelogs.timer` | Starts the extractor every 6 hours. |

## Deploy locally or on a VM

You need a Juju controller on a cloud that supports machine charms, for example LXD.
You also need `charmcraft` and `tox`.

```shell
make pack
juju deploy ./ubuntu-changelogs_amd64.charm --storage cache=50G
juju expose ubuntu-changelogs
```

`make pack` runs the formatter, the linter, and the unit tests before it builds
the charm. To build without these checks, run `charmcraft pack`. The examples
use the amd64 file. On arm64, use `ubuntu-changelogs_arm64.charm`.

The first changelog extraction can take hours. During this time, the unit
status is `maintenance: extracting changelogs`. A unit with `active` status has
started nginx, but its data can be incomplete. See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) to check the data.

### Optional ingress

An ingress is a proxy that gives the application a public address. To put the
server behind an ingress, connect an application that supports the `ingress`
interface:

```shell
juju integrate ubuntu-changelogs:ingress <ingress-application>
```

Set `hostname` before you connect the ingress. The charm sends the host name to
the ingress when the relation becomes ready. Without an ingress, clients must
connect to port 80 of the unit.

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `hostname` | `changelogs.ubuntu.com` | Host name to give to the ingress. |
| `meta_release_ref` | `main` | Git branch, tag, or commit to publish from the `meta-release` repository. |
| `meta_release_connect_timeout` | `30` | Timeout in seconds for the connectivity check before the charm clones `meta-release`. |

A change to `meta_release_ref` clones the repository again.

## Actions

| Action | Description |
| --- | --- |
| `pull-changelogs` | Starts the extractor. It does nothing if an extraction already runs. The action returns before extraction ends. |
| `pull-meta-release` | Clones and publishes the meta-release files again. |

```shell
juju run ubuntu-changelogs/0 pull-changelogs
juju run ubuntu-changelogs/0 pull-meta-release
```

## Storage

The charm requires the `cache` storage. Juju mounts it at
`/var/cache/ubuntu-changelogs`. The extractor uses it for the Launchpad API
cache and for temporary source package downloads. The minimum size is 50 GB.

## Check the application

```shell
juju status ubuntu-changelogs
juju debug-log --include ubuntu-changelogs
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common problems and log
locations.

## Development

| Command | Purpose |
| --- | --- |
| `make init` | Update the lock file. |
| `make quality` | Format and lint the code. |
| `make unit-tests` | Run the unit tests. |
| `make pack` | Run the checks and build the charm. |
| `make setup-integration-tests` | Setup a Multipass VM for the integration tests. |
| `make integration-tests` | Run the integration tests in the local Multipass VM. |
| `make deploy` | Deploy the local charm to the current Juju model. |
| `make logs` | Follow the Juju log for this application. |

The integration tests need a prepared Multipass VM. See [TESTING.md](TESTING.md)
for the setup and teardown commands.

## Links

- Source: https://github.com/ubuntu/ubuntu-changelogs-operator
- Issues: https://github.com/ubuntu/ubuntu-changelogs-operator/issues
- Juju documentation:
  https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/
