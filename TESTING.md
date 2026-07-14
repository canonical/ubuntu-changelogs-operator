# Testing runbook

Commands for linting, type-checking, and testing the charm. All commands run
from the repository root. This project uses [`tox`](https://tox.wiki/) with
[`uv`](https://docs.astral.sh/uv/) to manage environments.

## Prerequisites

- `uv` and `tox` on `PATH`.
- `charmcraft` and a configured `juju` (with a machine cloud, e.g. LXD) for
  building the charm and running integration tests.

Refresh the lockfile after changing dependencies:

```shell
uv lock
```

## Environments

| Environment    | Purpose                                          |
| -------------- | ------------------------------------------------ |
| `format`       | Auto-format and auto-fix code with ruff.         |
| `lint`         | codespell, ruff checks, and pyright type checks. |
| `unit`         | Unit tests with coverage.                        |
| `integration`  | Jubilant integration tests against a live model. |

## Format the code

```shell
tox run -e format
```

## Lint and type-check

Runs codespell, `ruff check`, `ruff format --check`, and `pyright`:

```shell
tox run -e lint
```

Note: `pyright` downloads a Node.js runtime on first run and needs network
access.

## Unit tests

```shell
tox run -e unit
```

Run a single test:

```shell
tox run -e unit -- tests/unit/test_charm.py::test_start
```

Run everything except integration (format, lint, unit):

```shell
tox
```

## Integration tests

Integration tests deploy the charm to a temporary Juju model using Jubilant.
Build the charm first, then run the tests.

```shell
charmcraft pack
tox run -e integration
```

By default the tests look for a `*.charm` file in the repository root. To point
at a specific artifact:

```shell
CHARM_PATH=./ubuntu-changelogs-operator_amd64.charm tox run -e integration
```

## Manual smoke check after deploy

```shell
./tests/smoke.sh
```
