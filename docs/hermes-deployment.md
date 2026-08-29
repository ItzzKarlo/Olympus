# Hermes production deployment

This document installs Olympus 1.0.3 as one respectful workload on the existing
Hermes host. WALL originally launched and was accepted as 1.0.0; 1.0.1 was the
deployed post-WALL stabilization and observability patch; 1.0.2 added defensive
browser-profile lifecycle handling; and 1.0.3 freezes the hardware-proven native
Brave kiosk runtime. The earlier v0.14.1 deployment remains the immediate
pre-baseline predecessor.

> **Hermes is shared infrastructure.** The Olympus installer does not remove,
> stop, replace, or reconfigure Pi-hole, Pterodactyl, Docker, SSH, Wake-on-LAN,
> networking, firewall policy, or any other unrelated service. It never reboots,
> shuts down, suspends, or thermally powers off the host.

The target is Raspberry Pi 5, Ubuntu Server 26.04 (ARM64). Core, Cage/Brave,
DRM, HDMI hotplug, and the unattended visual path have been accepted on the real
WALL hardware. The same release remains usable headlessly when no monitor is
attached.

## Production shape

```text
/opt/olympus/releases/1.0.3/   immutable application release
/opt/olympus/current           atomic symlink to the active release
/opt/olympus/current/RELEASE-METADATA.json  immutable build provenance
/etc/olympus/config.toml       non-secret production configuration
/etc/olympus/secrets.env       integration credentials
/etc/olympus/kiosk.env         optional kiosk overrides
/var/lib/olympus/core.db       durable SQLite state and device trust
/var/backups/olympus/          safe, retained SQLite backups
/home/olympus-display/         isolated Brave profile
```

Core runs as the locked, low-privilege `olympus` system account. Cage and native
Brave run as the separate, password-locked `olympus-display` account. Neither
process runs as root. Application releases contain no database, credentials,
virtual environment, Node modules, Python caches, or developer environment file.

Core serves the compiled Display at the same origin as `/api/*` and `/ws/*`.
The local kiosk therefore uses `http://127.0.0.1:8000/` and remains independent
of DNS, Atlas, Meshnet, Cloudflare, and the WAN. Core still binds to the
configurable LAN address for trusted Agents.

## Package availability and dependencies

Package names were checked against the Ubuntu 26.04 “Resolute” ARM64 archive:

- Core: `python3`, `python3-venv`, `python3-pip`, `curl`, `ca-certificates`
- Kiosk: `cage`, `brave-browser`, `fonts-noto-core`,
  `fonts-noto-color-emoji`, `libpam-systemd`

Ubuntu provides Cage 0.2.1 for ARM64 in `universe`. Brave's official release
repository supports native ARM64 and supplies `brave-browser`; Olympus does not
install the Ubuntu `chromium-browser` Snap transition package. The installer
downloads Brave's signing key and deb822 `.sources` file to temporary files,
installs them only when their content changes, refreshes apt metadata, installs
the native package, and verifies `/usr/bin/brave-browser`. It never pipes a
network response into a shell. See [Brave's official Linux installation
instructions](https://brave.com/linux/) and the [Ubuntu Cage
package](https://packages.ubuntu.com/resolute/cage).

The installer changes apt state only when an explicit package flag is supplied.
`--install-kiosk-packages` idempotently configures only Brave's official release
repository. The installer never runs `apt upgrade` or `apt autoremove`, and it
never removes packages. If `universe` is not already enabled, enable it
deliberately before requesting the kiosk packages.

## Build a transferable release

Build on the development machine. Node is used only here; Hermes does not run a
Vite or Node server.

```bash
scripts/hermes/build-release.sh
```

If `display/node_modules` is already an exact `npm ci` installation:

```bash
scripts/hermes/build-release.sh --skip-node-install
```

The result is:

```text
dist/hermes/olympus-1.0.3-hermes-arm64.tar.gz
dist/hermes/olympus-1.0.3-hermes-arm64.tar.gz.sha256
```

Verify the checksum after transferring both files to Hermes, then extract:

```bash
sha256sum -c olympus-1.0.3-hermes-arm64.tar.gz.sha256
tar -xzf olympus-1.0.3-hermes-arm64.tar.gz
cd olympus-1.0.3
```

The archive contains portable Python source and static browser assets. The
installer creates the Linux ARM64 virtual environment on Hermes; never copy a
macOS or x86 virtual environment onto the Pi.

`VERSION` is the product version source of truth. The build also writes a
deterministic `RELEASE-METADATA.json` containing the version, exact 40-character
Git revision, and whether the source tree was clean. Deployable builds require a
clean tree. An explicit `--allow-dirty` is available only for local packaging
experiments, and the installer rejects the resulting dirty artifact. Source
archives without `.git` must provide `OLYMPUS_SOURCE_REVISION`; no timestamp,
credential, host identity, or source diff is embedded.

## First installation: Core only

Inspect the exact plan without changing Hermes:

```bash
./scripts/hermes/install.sh --dry-run --install-core-packages
```

Then install Core and its declared prerequisites:

```bash
sudo ./scripts/hermes/install.sh --install-core-packages
```

The operation is idempotent. It creates missing accounts/directories, installs
the isolated venv, preserves any existing `/etc` and `/var` data, installs the
Olympus units, enables Core and the two timers, and waits for loopback health.
The kiosk unit is installed but remains disabled until explicitly requested.

Check the result:

```bash
systemctl status olympus-core
curl http://127.0.0.1:8000/health
journalctl -u olympus-core -n 100 --no-pager
```

The health response includes `version`, `revision`, and `source_tree`. The
read-only doctor prints the same packaged version and revision from
`RELEASE-METADATA.json`.

Core uses one Uvicorn worker and never enables reload. It starts after ordinary
`network.target`, not `network-online.target`, so router, DNS, or WAN absence
does not block local startup.

## Configuration and secrets

Edit `/etc/olympus/config.toml`. The installed template uses:

```toml
[server]
host = "0.0.0.0"
port = 8000

[display]
directory = "/opt/olympus/current/display"

[persistence]
database_path = "/var/lib/olympus/core.db"

[backup]
directory = "/var/backups/olympus"
retention_days = 14

[security]
require_agent_auth = true
```

Changing `server.port` also changes the default healthcheck URL. Update
`OLYMPUS_CORE_URL` in `/etc/olympus/kiosk.env` and when running `doctor.sh` if a
non-default port is selected.

Keep Spotify, Google, and football credentials in
`/etc/olympus/secrets.env`, never in the release. The file is installed as
`root:olympus` mode `0640`. Optional integrations are disabled by default and
missing credentials do not prevent local Core, Display, Night policy, Agents,
or monitoring from starting.

### Football provider on Hermes

football-data.org is the recommended free fixture provider for current FC
Bayern matches. Its team ID for FC Bayern München is `5`; API-Football's `157`
is a different provider namespace and must not be reused.

Configure the repository-installed `/etc/olympus/config.toml` only during the
normal deployment/configuration procedure:

```toml
[football]
enabled = true
provider = "football-data"
team_id = "5"
tracked_id = "bayern"
team_name = "FC Bayern München"
team_short_name = "Bayern"
team_code = "FCB"
timezone = "Europe/Berlin"
```

Add the credential separately to `/etc/olympus/secrets.env`:

```dotenv
OLYMPUS_FOOTBALL_DATA_API_KEY=replace_with_the_real_key_on_hermes
```

The provider uses the official v4 team-matches resource and `X-Auth-Token`
authentication. Basic fixtures, status, kickoff, and scores remain operational
when the free tier omits rich lineups, events, statistics, or player ratings.
Its polling cadence never exceeds one request per minute, slows after full-time,
and honors rate-limit reset guidance. Existing API-Football deployments continue
to use team `157`, `OLYMPUS_FOOTBALL_API_KEY`, and may set `season` to the
competition season's starting year when API-Football requires that field.

After a configuration change:

```bash
sudo systemctl restart olympus-core
```

That command affects Olympus Core only.

## Device enrollment

Create enrollment tokens locally on Hermes and use the packaged desktop Agent
workflow from the main README:

```bash
sudo -u olympus /opt/olympus/current/scripts/hermes/admin.sh enrollment create
```

Use the same wrapper for other production administration, for example
`sudo -u olympus /opt/olympus/current/scripts/hermes/admin.sh devices list`.
The wrapper selects the active release's Core source, production virtual
environment, and `/etc/olympus/config.toml` independently of the caller's current
working directory.

The production database normally starts clean. Do not silently import a
development Mac database. Existing enrolled devices reconnect after Core
restarts because `/var/lib/olympus/core.db` is outside release directories.

## Safe backups and restore

`olympus-backup.timer` runs daily with a randomized delay and retains fourteen
days by default. It uses SQLite's online backup API and validates
`PRAGMA integrity_check`; it never copies a live WAL database with plain `cp`.
The installer and backup unit invoke the same production admin wrapper, so the
mandatory pre-update backup does not depend on the invoking shell's directory.

Run and inspect a backup:

```bash
sudo systemctl start olympus-backup.service
journalctl -u olympus-backup -n 50 --no-pager
ls -l /var/backups/olympus
sqlite3 /var/backups/olympus/core-YYYYMMDD-HHMMSS.db 'PRAGMA integrity_check;'
```

Restore is deliberately manual and destructive operations are never automated:

1. `sudo systemctl stop olympus-core`
2. Preserve the suspect DB, WAL, and SHM files under a dated diagnostic name.
3. Copy the selected backup to a temporary file in `/var/lib/olympus`.
4. Run `sqlite3 temporary.db 'PRAGMA integrity_check;'`.
5. Install it as `/var/lib/olympus/core.db`, owned by `olympus:olympus`, mode
   `0600`.
6. `sudo systemctl start olympus-core`
7. Verify `/health`, the Core journal, trusted devices, and Display state.

Rehearse this with a copied test database, not the live database.

## Health watchdog

`olympus-healthcheck.timer` checks loopback health once per minute after boot.
One or two failures only update `/run/olympus/health-failures`. Three consecutive
failures request exactly:

```text
systemctl restart olympus-core.service
```

A healthy response resets the counter. An inactive Core service is treated as a
deliberate operator state and is never restarted by the watchdog. The watchdog
never touches the kiosk, Docker, Pi-hole, Pterodactyl, SSH, networking, or host
power. A normal deliberate
`systemctl stop olympus-core` therefore stays stopped. The timer can also be
stopped during extended maintenance:

```bash
sudo systemctl stop olympus-healthcheck.timer
sudo systemctl stop olympus-core
```

## Minimal kiosk

Cage is a single-application Wayland compositor and can run directly from a TTY
with KMS/DRM. Its upstream systemd guidance requires a logind/PAM session and
controlling TTY; Olympus installs both without a display manager or desktop
environment. See Cage's [systemd boot guidance](https://github.com/cage-kiosk/cage/wiki/Starting-Cage-on-boot-with-systemd).

Install only the declared kiosk packages:

```bash
sudo ./scripts/hermes/install.sh --install-kiosk-packages --enable-kiosk
```

The packaged defaults are:

```dotenv
BROWSER_BIN=/usr/bin/brave-browser
OLYMPUS_KIOSK_PROFILE=/home/olympus-display/.config/olympus-brave
```

`BROWSER_BIN` remains configurable in `/etc/olympus/kiosk.env`. Enabling is not
the same as restarting: `--enable-kiosk` enables the unit and starts it only when
it is not already active. To intentionally replace a running physical kiosk
process, request that action explicitly:

```bash
sudo ./scripts/hermes/install.sh --restart-kiosk
```

Or control it independently later:

```bash
sudo scripts/hermes/kiosk-control.sh enable
sudo scripts/hermes/kiosk-control.sh disable
scripts/hermes/kiosk-control.sh status
```

The launcher:

1. waits without a restart loop until a DRM connector reports `connected`;
2. waits for local Core health;
3. starts Cage on tty1;
4. starts native Brave in kiosk mode with a dedicated profile and native Wayland;
5. lets systemd restart only the kiosk when Brave/Cage exits.

Immediately before launching Cage, the launcher checks live process command
lines for the exact configured kiosk `--user-data-dir`. If that profile is active,
startup fails without modifying it. Otherwise the launcher removes only stale
`SingletonLock`, `SingletonCookie`, and `SingletonSocket` entries left by an
earlier browser process; history, preferences, cookies, cache, and all other
profile data remain untouched.

Cage supports output hotplug and exits after its final output is removed, so the
service restart returns to the monitor-wait loop rather than rebooting Hermes.
The packaged unit uses a ten-second restart delay and limits starts to six in
five minutes. This recovers ordinary Cage/Brave exits while preventing a
persistent configuration error from creating a tight restart storm.
After a rate-limit hit, an operator deliberately clears and starts the unit with:

```bash
sudo systemctl reset-failed olympus-kiosk.service
sudo systemctl start olympus-kiosk.service
```

The browser uses Chromium's documented `--ozone-platform=wayland` selection; see
the [Chromium Ozone overview](https://chromium.googlesource.com/chromium/src/+/main/docs/ozone_overview.md).

The launcher does **not** use `--no-sandbox`. Brave runs as the ordinary
`olympus-display` user with its sandbox available. The launcher uses the Cage
0.2.1-compatible `cage -d -s -- /usr/bin/brave-browser ...` form; it does not
request the unsupported `-x` option. Brave already uses native Wayland, so Olympus does
not require an XWayland control flag. No GDM, SDDM, LightDM, GNOME, KDE, XFCE,
X11 desktop session, or cursor-hiding daemon is installed. Production CSS hides
the pointer and selection artifacts. Cage supports Wayland idle inhibition;
Olympus does not globally disable CPU power saving or add DDC/CI, HDMI power,
host suspend, or thermal shutdown behavior.

If no monitor is attached, Core and all other Hermes services remain unaffected.
The accepted WALL baseline runs the kiosk on the attached display; kiosk
enable/disable remains an independent operator choice for other installations.

The packaged unit is authoritative and includes journald output plus a private,
mode-0700 `/run/olympus-kiosk` runtime directory owned for the service account.
After 1.0.3 production acceptance, `98-debug-output.conf` is redundant and may
be removed. Inspect `wall.conf` with `systemctl cat olympus-kiosk.service`; remove
it only if its effective settings are limited to the runtime-directory behavior
now present in the packaged unit. Never discard an administrator override whose
remaining settings have not been audited. The old Cage hotfix and its drop-in
remain retired.

### Migration from the accepted 1.0.2 WALL

The live WALL already has native Brave and the two values above in
`/etc/olympus/kiosk.env`. Leave that preserved configuration in place. Deploy
1.0.3 normally, without `--enable-kiosk` or `--restart-kiosk`; the installer
backs up the database, stages and switches the release, restarts Core, and leaves
the healthy Cage/Brave process alone. Confirm the Display reconnects to Core.

At a separately chosen maintenance moment, compare the packaged unit and local
drop-ins with `systemctl cat olympus-kiosk.service`. Remove the redundant
`98-debug-output.conf`; remove `wall.conf` only after confirming it contains no
behavior beyond the packaged runtime-directory settings. Then run `systemctl
daemon-reload` and use `--restart-kiosk` once to accept the clean packaged unit.
Do not remove the existing Brave profile or its data. The singleton cleanup is
defensive lifecycle hardening and was not the cause or solution of the rejected
Snap cgroup failure.

## Diagnostics and logs

The doctor is read-only. It does not install, restart, repair, or modify anything:

```bash
sudo scripts/hermes/doctor.sh
```

It validates deployed provenance, config/secrets syntax without printing secret
values, SQLite health and writability, backup recency, Core and kiosk state,
conflicting kiosk drop-ins, clock synchronization, gateway/DNS/HTTPS reachability,
browser/compositor availability, DRM presence, and disk space. Rooted filesystem
inspection skips live probes. Primary logs remain in journald:

```bash
journalctl -u olympus-core
journalctl -u olympus-kiosk
journalctl -u olympus-healthcheck
journalctl -u olympus-backup
```

Olympus does not change global journald retention and does not create another
unbounded production log archive.

## Updates and rollback limits

Extract the new release and inspect the update plan:

```bash
./scripts/hermes/update.sh --dry-run
sudo ./scripts/hermes/update.sh
```

Before changing the active symlink, update tooling requires a successful safe
SQLite backup when a current production DB exists. It installs the new release
side by side, builds its Linux ARM64 venv, switches `/opt/olympus/current`
atomically, and verifies Core health. It never deletes prior releases or durable
state, so at least the previous application tree remains available.

A normal update never starts or restarts `olympus-kiosk.service`. Core and the
same-origin Display may change while the already-running browser remains on
`http://127.0.0.1:8000/` and reconnects. Initial provisioning may use
`--enable-kiosk`; physical-runtime maintenance must use `--restart-kiosk`.

A versioned release directory is immutable once created. Reinstalling an artifact
with identical version, revision, and source-tree provenance reuses it without
modification. A different revision using the same version is rejected before the
existing directory or `current` symlink can change; assign a new version instead.

Application rollback means repointing `current` to a known release and restarting
Core. Do not roll application code backward across an incompatible database
migration. Restore a compatible tested DB backup only through the deliberate
manual procedure above. Olympus never performs automatic database or application
rollback.

## Resource and shared-host behavior

The Core unit uses an empty capability bounding set, strict read-only system
paths with explicit state/backup write paths, and moderate CPU/IO weights. The
kiosk is lower priority (`CPUWeight=50`, `IOWeight=50`, modest positive
`OOMScoreAdjust`) so severe memory pressure prefers it over shared infrastructure.
No hard memory ceiling or CPU affinity is imposed without real Hermes
measurements. Core's `/proc` visibility remains available because existing host
telemetry needs it.

Normal Olympus deployment and recovery actions must be limited to:

```text
olympus-core.service
olympus-kiosk.service
olympus-healthcheck.service/timer
olympus-backup.service/timer
```

After installation, perform a read-only sanity check of Pi-hole, Pterodactyl,
Docker, and SSH using their existing operator procedures. Do not automate
invasive restarts as an “acceptance test.”

## WALL production acceptance record

The physical ARM64 WALL deployment completed hardware acceptance before Olympus
v1.0 was designated the production baseline. The retained acceptance coverage
was:

1. Install Core with kiosk disabled; verify health and production Display over a
   local browser.
2. Reboot Hermes; verify Core and timers return without SSH intervention.
3. Enroll a real packaged Agent; reboot and confirm authentication reconnects.
4. Attach HDMI, install kiosk packages, and enable `olympus-kiosk`.
5. Verify Cage/Brave fullscreen with no desktop, login screen, or browser UI.
6. Kill Core; verify systemd restart and WebSocket recovery without browser
   restart.
7. Kill Brave and then Cage; verify kiosk-only recovery.
8. Disconnect/restore WAN; verify local Display/Core/Agents remain alive and
   collectors recover.
9. Unplug/replug HDMI; verify kiosk service recovery without host reboot.
10. Run a manual backup, integrity check, and restore rehearsal on a copied DB.
11. Confirm Pi-hole, Pterodactyl, Docker, WOL, and SSH remain operational during
    ordinary Olympus restart/update activity.

WALL hardware acceptance is complete. Future releases should repeat the relevant
checks when changing startup, kiosk, display, backup, watchdog, or host-integration
behavior. The 1.0.3 procedure below is the required acceptance for the finalized
native-browser runtime.

### 1.0.3 final real-Hermes acceptance

1. Verify the archive checksum and metadata, then record `systemctl cat
   olympus-kiosk.service`, the two known drop-ins, current Core health, and
   `systemctl show olympus-kiosk.service -p ActiveState -p SubState -p Result
   -p NRestarts -p ExecMainStatus`.
2. Run `install.sh --dry-run`, then deploy 1.0.3 normally with no kiosk flag.
   Confirm the database backup, immutable release switch, healthy 1.0.3 Core,
   and that the kiosk main PID did not change.
3. Confirm the WALL reconnects and renders correctly; inspect
   `journalctl -u olympus-kiosk.service` and verify the service is still active
   with no deployment-induced restart.
4. Verify `/usr/bin/brave-browser`, the Brave profile path, the exact effective
   `cage -d -s --` command, journal output, runtime directory ownership/mode,
   `Restart=always`, `RestartSec=10s`, and the 5-minute/6-start limit.
5. Audit and remove only redundant Olympus drop-ins as described above, run
   `systemctl daemon-reload`, then intentionally run `install.sh
   --restart-kiosk` once. Confirm a new Cage/Brave process becomes active with
   `Result=success` and `ExecMainStatus=0`.
6. Send SIGKILL to Cage once. Confirm systemd records the failure, waits ten
   seconds, launches a new process, and returns the WALL to active/running with
   `NRestarts` incremented.
7. In a controlled maintenance window, repeat rapid manual starts to confirm the
   sixth start is rate-limited, then recover with `systemctl reset-failed
   olympus-kiosk.service` followed by `systemctl start olympus-kiosk.service`.
8. Reconfirm Core health, WALL rendering, backup integrity, Agent reconnection,
   and read-only status of Pi-hole, Pterodactyl, Docker, SSH, networking, and WOL.
