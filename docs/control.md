# Olympus Control

Olympus Control is the low-level administration, preview, simulation, and diagnostics console built directly into Olympus Core. It is **not** a separate service, container, or application. Control ships inside the same immutable Olympus release as Core and is served by the existing Core HTTP server.

## URL and lifecycle

On Hermes, open:

```text
http://hermes.karmtin:8000/control/
```

Control deliberately shares the lifecycle of `olympus-core.service`. If Core is stopped or crashes, Control is unavailable too. Restarting the kiosk does not affect Control.

When Control requests a Core restart, the HTTP response is returned first. The browser then switches to a reconnecting state and polls Core until `/health` becomes available again.

## First login

Control is locked until a password is configured locally on Hermes. Set or rotate it with:

```bash
sudo /opt/olympus/current/scripts/hermes/admin.sh control-password
```

The password is stored as a scrypt record in `/etc/olympus/control.json`; the plaintext password is never written to disk. Rotating the password invalidates existing Control sessions.

Control uses an HttpOnly, SameSite=Strict session cookie, same-origin checks, CSRF tokens for state-changing requests, login rate limiting, and a restrictive Content Security Policy. Control credentials and `/etc/olympus/secrets.env` are never exposed through the browser API.

## Preview overrides

Preview state is intentionally separate from persistent configuration. Runtime overrides live under:

```text
/run/olympus-control/control-overrides.json
```

They are schema validated, written atomically, and disappear on reboot. Core ignores malformed override state and continues normal operation. Preview overrides can expire after 15, 30, or 60 minutes, or remain active until reset for the current boot.

The Preview page supports:

- seasonal date previews without changing the real wall clock/date
- AUTO / FORCE DAY / FORCE NIGHT
- AUTO / IDLE / NIGHT / MEDIA / DEVELOPMENT / GAMING / MATCHDAY / NEWS
- environment enable/intensity/animation controls
- reduced-motion simulation

The WALL receives these changes through the existing Core display state/WebSocket path. Previewing does **not** require restarting Core or the kiosk.

Use **RETURN TO NORMAL OPERATION** or **Reset All** to remove all temporary Control overrides without touching persistent config or real collector state.

Emergency CLI fallback:

```bash
sudo rm -f /run/olympus-control/control-overrides.json
```

The Core watcher notices the removal and the Display returns to normal state. If you want an immediate refresh as well, restart only Core:

```bash
sudo systemctl restart olympus-core.service
```

## Simulation Lab

Simulation overlays presentation state while preserving the real collector state returned by the normal Core API. Real critical incidents retain precedence.

Supported simulation families include:

- News: notable, important, major, critical, custom headline/source
- System: blocker, warning, critical, DNS degraded/down, gateway down, Internet down, monitored service down, agent offline
- Football: pre-match, kickoff, live, Bayern/opponent goal, halftime, second half, full time, victory, defeat, draw
- Media: fake Spotify playing/paused with title, artist, album, progress, and duration
- Gaming: Fortnite, Minecraft, Among Us, Goat Simulator, custom title/FPS
- Development: simulated active machine/application with CPU and RAM

Only presentation output is changed. Collectors continue to collect real data.

## Services

Control exposes only an explicit Olympus allowlist:

- `olympus-core.service`
- `olympus-kiosk.service`
- `olympus-healthcheck.service`
- `olympus-healthcheck.timer`
- `olympus-backup.service`
- `olympus-backup.timer`

No generic systemd endpoint exists and unrelated Hermes workloads are not controllable from Olympus Control.

Core remains unprivileged. Service management uses the existing systemd D-Bus/PolicyKit path with a root-owned PolicyKit rule installed from:

```text
/etc/polkit-1/rules.d/49-olympus-control.rules
```

The rule authorizes only the `olympus` service user, the approved Olympus units, and the supported verbs. There is no arbitrary shell/exec API.

## Persistent config editor

The Config page edits the production Olympus config through the existing Olympus parser and validation rules. Preview overrides do not modify this file.

On first Control-capable installation, the Hermes installer preserves the original config as:

```text
/etc/olympus/config.pre-control.toml
```

and migrates the writable config to:

```text
/etc/olympus/managed-config/config.toml
```

`/etc/olympus/config.toml` becomes a compatibility symlink to that managed file. Only the managed-config directory is writable by Core; the rest of `/etc/olympus` remains protected by the systemd sandbox.

Config apply flow:

1. load current config and checksum
2. edit structured fields or raw TOML
3. validate with Olympus Core/monitoring parsers
4. review the unified diff
5. explicitly confirm
6. create a timestamped backup under `/var/backups/olympus/config/`
7. atomically replace the managed config
8. restart Core when ready

Invalid TOML is never installed. A stale browser draft is rejected when the on-disk checksum changed. Inline credentials are deliberately kept out of the browser editor; credentials belong in the existing secrets environment file.

## Logs and diagnostics

The Logs page reads only approved Olympus service journals. Line count, priority, and a text filter are supported. The Core service receives only the `systemd-journal` supplementary group required for this purpose.

Diagnostics includes release metadata, current/presented state, service status, config validity, Hermes telemetry, network state, agents, and Display connection information. Diagnostic output is passed through Control's redaction layer before being returned to the browser.

## Devices and enrollment

Control reuses the existing Olympus repositories for trusted devices and enrollment. It can:

- list trusted/revoked agents
- show last-seen and current online state
- create a short-lived single-use enrollment token
- revoke a device after confirmation

No enrollment cryptography is implemented in JavaScript.

## Backups

Control reuses the existing live-WAL-safe SQLite backup implementation. The dashboard lists backups and can create one immediately. Database restore is intentionally not exposed by this version.

Config history is separate from SQLite database backups.

## Releases

The Releases page is read-only in the initial Control implementation. It shows the active immutable release, VERSION, revision/provenance metadata, and installed release directories under `/opt/olympus/releases`.

Rollback is intentionally deferred until it can be implemented without weakening the immutable release model.

## Deployment

Control uses the normal Olympus release path. Nothing is installed as a separate application.

Build on Zeus:

```bash
cd ~/dev/Olympus
scripts/hermes/build-release.sh --skip-node-install
cd dist/hermes
sha256sum -c olympus-1.0.9-hermes-arm64.tar.gz.sha256
```

Transfer to Hermes:

```bash
ssh karlo@hermes.karmtin 'mkdir -p ~/olympus-deploy/v1.0.9'
scp olympus-1.0.9-hermes-arm64.tar.gz \
    olympus-1.0.9-hermes-arm64.tar.gz.sha256 \
    karlo@hermes.karmtin:~/olympus-deploy/v1.0.9/
```

Install on Hermes:

```bash
ssh karlo@hermes.karmtin
cd ~/olympus-deploy/v1.0.9
sha256sum -c olympus-1.0.9-hermes-arm64.tar.gz.sha256
tar -xzf olympus-1.0.9-hermes-arm64.tar.gz
cd olympus-1.0.9
sudo ./scripts/hermes/install.sh --dry-run --restart-kiosk
sudo ./scripts/hermes/install.sh --restart-kiosk
```

Then configure the Control password if this is the first Control deployment:

```bash
sudo /opt/olympus/current/scripts/hermes/admin.sh control-password
```

and open `http://hermes.karmtin:8000/control/`.

No Node/npm installation is required on Hermes.

## Troubleshooting

Core status:

```bash
systemctl status olympus-core.service --no-pager
curl -s http://127.0.0.1:8000/health | jq
```

Control authentication record:

```bash
sudo ls -l /etc/olympus/control.json
```

Control runtime state:

```bash
sudo ls -la /run/olympus-control/
```

Config migration state:

```bash
ls -l /etc/olympus/config.toml /etc/olympus/managed-config/config.toml
```

PolicyKit rule:

```bash
sudo cat /etc/polkit-1/rules.d/49-olympus-control.rules
```

If Core cannot perform an approved service action, inspect the Core journal and PolicyKit/systemd authorization rather than weakening the Core sandbox.

## Design rule

Olympus Control is part of Olympus Core. It is not a new product beside Olympus and not another container/service to operate.

> A true Captain goes down with his ship. ⚓
