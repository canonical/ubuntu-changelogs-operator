# Troubleshooting

This page helps you find the cause of common problems. The examples use the
application name `ubuntu-changelogs` and unit `ubuntu-changelogs/0`. Change the
unit number if your deployment is different.

In Juju, an application is a deployed charm. A unit is one machine that runs
the application. Run the `juju` commands on the Juju controller (the management
machine).

## Quick checks

```shell
juju status ubuntu-changelogs
juju debug-log --include ubuntu-changelogs --replay --tail 100
```

`juju status` shows the unit state. Use this table to select the next step.

| Unit state | Meaning | Next step |
| --- | --- | --- |
| `active` | nginx started. | See [No web pages](#no-web-pages). |
| `active: extracting changelogs` | The extractor runs. This is normal. | Wait. The first run can take hours. |
| `active: last changelog extraction failed` | The last extractor run failed. nginx still serves the available data. | See [Changelogs are missing or old](#changelogs-are-missing-or-old). |
| `maintenance: failed rolling out configuration` | A config change did not complete. | See [The configuration does not complete](#the-configuration-does-not-complete). |
| `blocked: nginx is not running` | nginx stopped. | See [No web pages](#no-web-pages). |
| `blocked` | An install step failed. | See [The unit is blocked or in error state](#the-unit-is-blocked-or-in-error-state). |
| `error` | A Juju step failed with an error. | See [The unit is blocked or in error state](#the-unit-is-blocked-or-in-error-state). |

## Logs

For the charm log, run this command on the controller:

```shell
juju debug-log --include ubuntu-changelogs --replay --tail 200
```

For the logs on the unit, open a shell:

```shell
juju ssh ubuntu-changelogs/0
```

| Log | Command |
| --- | --- |
| Extractor | `sudo journalctl -u lp-extract-changelogs.service` |
| Extractor timer | `sudo systemctl list-timers lp-extract-changelogs.timer` |
| nginx service | `sudo journalctl -u nginx` |
| nginx access log | `sudo tail -n 100 /var/log/nginx/access.log` |
| nginx error log | `sudo tail -n 100 /var/log/nginx/error.log` |

If you cannot use SSH, run the commands from the controller with `juju exec`.
Use the unit name:

```shell
juju exec --unit ubuntu-changelogs/0 -- journalctl _SYSTEMD_UNIT=lp-extract-changelogs.service
juju exec --unit ubuntu-changelogs/0 -- tail -n 100 /var/log/nginx/access.log
juju exec --unit ubuntu-changelogs/0 -- tail -n 100 /var/log/nginx/error.log
```

## The unit is blocked or in error state

1. Read the last charm log messages:

   ```shell
   juju debug-log --include ubuntu-changelogs --replay --tail 100
   ```

2. On the unit, test the package archive and the disk:

   ```shell
   juju ssh ubuntu-changelogs/0 -- sudo apt update
   juju ssh ubuntu-changelogs/0 -- df -h / /var/cache/ubuntu-changelogs
   ```

3. Test access to Launchpad:

   ```shell
   juju ssh ubuntu-changelogs/0 -- git ls-remote https://git.launchpad.net/meta-release
   juju ssh ubuntu-changelogs/0 -- curl -fsS -o /dev/null https://api.launchpad.net/devel/
   ```

4. Correct the cause.

5. If the unit is in error state, retry the failed step:

   ```shell
   juju resolve ubuntu-changelogs/0
   ```

If the unit is still blocked, collect the logs in
[Report a problem](#report-a-problem).

## The configuration does not complete

The unit shows `maintenance: failed rolling out configuration`. The usual
causes are a bad `meta_release_ref` or no network access to Launchpad.

1. Check the current value:

   ```shell
   juju config ubuntu-changelogs meta_release_ref
   ```

2. Check that the ref exists:

   ```shell
   juju ssh ubuntu-changelogs/0 -- git ls-remote https://git.launchpad.net/meta-release
   ```

3. Set a valid branch, tag, or commit:

   ```shell
   juju config ubuntu-changelogs meta_release_ref=main
   ```

4. Or clone and publish the files again:

   ```shell
   juju run ubuntu-changelogs/0 pull-meta-release
   ```

The unit status changes at the next Juju status check, usually after 5 minutes.

If the network is slow, the connectivity check can time out. The default timeout
is 30 seconds. Increase it and apply the configuration again:

```shell
juju config ubuntu-changelogs meta_release_connect_timeout=60
```

## No web pages

Run these commands on the unit:

```shell
systemctl is-active nginx
sudo nginx -t
curl -fsS http://localhost/robots.txt
ss -lntp | grep ':80'
ls -la /var/www/changelogs.ubuntu.com
```

| Result | Cause | Action |
| --- | --- | --- |
| `nginx` is not active | The service stopped. | Run `sudo systemctl start nginx`. Then read the nginx log. |
| `nginx -t` fails | The nginx configuration is not valid. | Read `/etc/nginx/sites-enabled/index.conf`. Compare it with `files/nginx.conf` in the repository. Deploy the charm again to replace the file. |
| `curl` fails | nginx cannot read the file or the file is missing. | Read `/var/log/nginx/error.log`. See [Meta-release files are missing or old](#meta-release-files-are-missing-or-old). |
| Port 80 is not open | The cloud firewall blocks the port. | Run `juju expose ubuntu-changelogs`. Check the cloud firewall rules. |
| The directory is empty | The config change did not run. | See [The configuration does not complete](#the-configuration-does-not-complete). |

## The public host name does not work

An ingress is a proxy that gives the application a public address. The
`ingress` relation is optional. Without it, clients must connect to port 80 of
the unit.

```shell
juju status --relations
juju config ubuntu-changelogs hostname
```

| Result | Action |
| --- | --- |
| No ingress relation | Connect an ingress application: `juju integrate ubuntu-changelogs:ingress <ingress-application>`. |
| Wrong host name | Remove the ingress relation. Set the name with `juju config ubuntu-changelogs hostname=<host-name>`. Connect the ingress again. |
| Ingress not ready | Read the ingress logs. When the relation is ready, the charm logs `ingress is ready. URL: ...`. |

## Meta-release files are missing or old

The charm updates these files on config change and when you run the action. It
does not update them on a timer. Start an update:

```shell
juju run ubuntu-changelogs/0 pull-meta-release
```

If the action fails, read the error in the action output. Common causes:

- **Bad ref.** Check `juju config ubuntu-changelogs meta_release_ref`. Use a
  branch, tag, or commit that exists in
  `https://git.launchpad.net/meta-release`.
- **No network access.** Test it with:
  `juju ssh ubuntu-changelogs/0 -- git ls-remote https://git.launchpad.net/meta-release`.
- **Connectivity check timeout.** The check takes longer than
  `meta_release_connect_timeout` seconds (default 30). Increase it with
  `juju config ubuntu-changelogs meta_release_connect_timeout=<seconds>`.
- **A missing file in the repository.** The charm expects these files:
  `EOLReleaseAnnouncement`, `meta-release`, `meta-release-development`,
  `meta-release-lts`, `meta-release-lts-development`,
  `meta-release-lts-proposed`, `meta-release-proposed`,
  `meta-release-unit-testing`, and `raspi`.

The log message `expected published file '<name>' missing` gives the name of
the missing file.

Check the served files:

```shell
juju ssh ubuntu-changelogs/0 -- ls -l /var/www/changelogs.ubuntu.com
```

## Changelogs are missing or old

1. Check the timer and the service:

   ```shell
   juju ssh ubuntu-changelogs/0 -- systemctl status lp-extract-changelogs.timer
   juju ssh ubuntu-changelogs/0 -- systemctl status lp-extract-changelogs.service
   ```

2. Check the log:

   ```shell
   juju ssh ubuntu-changelogs/0 -- sudo journalctl -u lp-extract-changelogs.service --since "24 hours ago"
   ```

3. Start an extraction now:

   ```shell
   juju run ubuntu-changelogs/0 pull-changelogs
   ```

The action returns before the extraction ends. `juju status` shows
`active: extracting changelogs` while it runs.

| Log message | Cause | Action |
| --- | --- | --- |
| `another extractor is running, exiting` | An extraction already runs. | Wait. |
| `assuming last check 30 days ago` | The state file does not exist. | Normal on the first run. Wait. |
| `failed to retrieve ...: HTTP 404` | A source file is no longer on Launchpad. | No action. The run counts the package as failed. |
| `failed to retrieve ...` (other) | A network error or a timeout. | Check the network and the proxy. |
| `has no debian/changelog` | The source package has no changelog. | No action. The run counts the package as failed. |
| `crawl incomplete` | The run had failures. The last check time is not updated. | Read the earlier errors. Start again. |
| `extracted N changelogs in X seconds` | The run completed. | None. |

The timer starts 5 minutes after boot and then every 6 hours. To enable and
start the timer again:

```shell
juju ssh ubuntu-changelogs/0 -- sudo systemctl enable --now lp-extract-changelogs.timer
```

The extractor writes to `/var/www/changelogs.ubuntu.com/changelogs`. The
persistent state is in `/var/lib/ubuntu-changelogs`.

The extractor reads packages that changed since the last successful run. To
read the last 30 days again, remove `/var/lib/ubuntu-changelogs/last_check.txt`
when no extraction runs. Then start the extractor. This operation can take
hours.

### Run the extractor with debug output

Stop the timer first. Then run the script on the unit:

```shell
juju ssh ubuntu-changelogs/0 -- sudo systemctl stop lp-extract-changelogs.timer
juju ssh ubuntu-changelogs/0 -- sudo /usr/local/bin/lp-extract-changelogs --debug \
    --cache-dir /var/cache/ubuntu-changelogs \
    --state-dir /var/lib/ubuntu-changelogs \
    --output-dir /var/www/changelogs.ubuntu.com/changelogs
juju ssh ubuntu-changelogs/0 -- sudo systemctl start lp-extract-changelogs.timer
```

This command can take hours and writes to the live server directory. Do not run
it while an extraction is in progress.

## The cache storage is full

```shell
juju ssh ubuntu-changelogs/0 -- df -h /var/cache/ubuntu-changelogs
juju ssh ubuntu-changelogs/0 -- sudo du -sh /var/cache/ubuntu-changelogs/*
```

The cache storage must be at least 50 GB. If it is full:

- Remove old temporary downloads when no extraction runs:

  ```shell
  juju ssh ubuntu-changelogs/0 -- sudo rm -rf /var/cache/ubuntu-changelogs/downloads/*
  ```

- If the space is still not sufficient, remove the application and deploy it
  again with larger `cache` storage. A new deployment removes the served files
  and builds them again.

## Integration tests fail

- Make sure that one `.charm` file is in the repository root, or set
  `CHARM_PATH`. Run `charmcraft pack` first.
- Make sure that Juju is version 3.6 or later. The controller must have a
  machine cloud. Run `juju version` and `juju clouds`.
- The tests use a temporary model. Read the pytest output and the Juju log for
  that model.
- The extractor test is slow. The tests do not wait for the extraction to end.

See [TESTING.md](TESTING.md) for the full test procedure.

## Report a problem

Collect this information before you open an issue at
https://github.com/ubuntu/ubuntu-changelogs-operator/issues:

```shell
juju status --format yaml > juju-status.yaml
juju debug-log --include ubuntu-changelogs --replay > juju-debug.log
juju ssh ubuntu-changelogs/0 -- sudo journalctl -u lp-extract-changelogs.service --no-pager > extractor.log
juju ssh ubuntu-changelogs/0 -- sudo journalctl -u nginx --no-pager > nginx.log
juju version
charmcraft --version
```
