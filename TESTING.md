# Testing

All commands run from the repository root. The project uses `tox` with `uv`.
You need `uv`, `tox`, `charmcraft`, and Juju on `PATH`. `uv` installs the
Python dependencies. `tox` creates the test environments.

After you change a dependency, update the lock file:

```shell
uv lock
```

## Environments

| Environment | What it does |
| --- | --- |
| `format` | Formats the code and applies safe ruff fixes. |
| `lint` | Runs codespell, ruff checks, and pyright. |
| `unit` | Runs the unit tests with coverage for `src/` and `files/`. |
| `integration` | Tests the charm in a temporary Juju model. |

`tox` without an environment runs `format`, `lint`, and `unit`.

## Unit tests

```shell
tox run -e unit
```

The command runs pytest with coverage and prints a report. To run one test file
or one test:

```shell
tox run -e unit -- tests/unit/test_changelogs.py
tox run -e unit -- tests/unit/test_charm.py::test_start
```

## Integration tests

The integration tests use Jubilant. They deploy the charm to a temporary Juju
model in a local Multipass virtual machine, wait until the unit is active, and
test the web server, the meta-release files, the actions, the timer, and the
cache storage.

You need Multipass on the host. The Makefile prepares the machine and runs the
tests there:

```shell
make setup-integration-tests
multipass start juju-sandbox-ubuntu-changelogs
make integration-tests
make teardown-integration-tests
```

`make setup-integration-tests` creates a virtual machine named
`juju-sandbox-ubuntu-changelogs`, installs Juju and tox, stops the machine, and
adds the repository mount for the next boot.

`multipass start ...` starts the virtual machine.

`make integration-tests` builds the charm on the host and runs the tests in the
virtual machine. The tests use the `.charm` file in the repository root.

`make teardown-integration-tests` deletes the virtual machine.

Some tests take time:

- The deploy test can wait up to 15 minutes.
- The meta-release tests can wait up to 5 minutes for a file update.
- The last test starts a real changelog extraction. It does not wait for the
  extraction to end.
