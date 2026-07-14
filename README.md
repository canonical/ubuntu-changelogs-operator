# Ubuntu Changelogs Operator

Charmhub package name: ubuntu-changelogs-operator
More information: https://charmhub.io/ubuntu-changelogs-operator

A machine charm that runs the web server behind https://changelogs.ubuntu.com/.
It serves Ubuntu meta-release information and package changelogs.

Source code: https://github.com/ubuntu/ubuntu-changelogs-operator/issues

## Overview

The charm installs and manages an nginx web server and populates its serving
directory (`/var/www/changelogs.ubuntu.com`) from Launchpad. The workload logic is split
into standalone modules under `src/`:

- `nginx.py` — install, configure, and manage the nginx service.

`charm.py` orchestrates these modules in response to Juju events.

## Usage

A Makefile wraps the common `tox`, `charmcraft`, and `juju` commands.

Test, build, deploy, and smoke-test:

```shell
make pack     # build the charm
make deploy   # deploy to the current Juju model
make smoke    # verify the workload responds
```

See [TESTING.md](TESTING.md) for the full development and test loop.

## Other resources

- [Contributing](CONTRIBUTING.md)
- [Juju documentation](https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/)
