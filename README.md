# Olympus

Olympus is a local, event-driven home display and automation system.

It runs primarily on a Raspberry Pi and combines data from devices, local services,
external APIs, and machine agents into one context-aware display.

Olympus is designed to automatically change what it displays depending on what is
currently happening.

Examples include:

- idle dashboard
- calendar and weather
- Spotify playback
- development sessions
- gaming telemetry
- network and service monitoring
- alerts
- news
- night mode
- football matchday mode


## System flow

Olympus is split into three main components.

### Core

The Core is the brain of Olympus.

It runs on the central home server, currently Hermes, and is responsible for:

- device registration
- telemetry ingestion
- event processing
- application state
- display mode selection
- external API integrations
- network monitoring
- service monitoring
- communication with the display


### Display

The Display renders the current Olympus state.

It does not decide what should be shown and does not directly communicate with
device agents.

The Display receives state and events from the Core and renders the appropriate UI.


### Agents

Agents run on individual devices.

They are responsible for collecting device-specific information such as:

- CPU usage
- memory usage
- temperatures
- running applications
- development sessions
- active games
- local telemetry

Agents send this information to the Olympus Core.


## Core principle

> Agents observe devices. Core interprets reality. Display renders reality.


## Architecture

```text
Agents · Spotify · Weather · Google Calendar
Network/service monitors · Local app integrations
                         │
                         ▼
                    Olympus Core
                         │
                         │ /ws/display
                         ▼
                       Display
```

Optional local application observers join the same path without bypassing the
machine Agent:

```text
Minecraft + Fabric observer → localhost Agent → Core → Display
```

Olympus v0.7 implements this full local path. Agents own device-specific
observation, Core owns interpretation and monitoring, and the Display consumes
only Core's normalized state.

Primary scene priority remains:

```text
GAMING > DEVELOPMENT > MEDIA > IDLE
```

Alerts do not become another normal mode. They overlay whichever scene is
already active. When Core confirms recovery, it sends a temporary recovery event
with measured downtime, then the Display returns to the unchanged scene below.

## Run Olympus Core

```bash
cd core
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn olympus_core.main:app --reload
```

For agents on other home-LAN devices, run Core on Hermes' LAN interface:

```bash
uvicorn olympus_core.main:app --host 0.0.0.0 --reload
```

Core exposes:

- `GET /health` — service health
- `GET /api/agents` — registered devices and their latest telemetry
- `GET /api/state` — interpreted Olympus mode and machine state
- `WS /ws/agents` — persistent agent connection
- `WS /ws/display` — live interpreted state for displays

State is intentionally held in memory for this milestone. Hermes is the intended
long-term Core host, but running Core on a local development machine remains fully
supported; `core_host` describes whichever machine currently runs Core.

## Monitoring configuration

Core always observes its own host CPU, RAM, disk, and uptime. Network targets and
services are configured locally in TOML so the Display cannot create arbitrary
probes.

```bash
cd core
cp config.example.toml config.toml
```

The ignored `core/config.toml` can configure:

- gateway, external IP, DNS, and HTTPS diagnostics
- important LAN or Meshnet targets using read-only TCP reachability checks
- HTTP, HTTPS, and TCP service health checks
- independent polling intervals, timeouts, and failure/recovery thresholds

The gateway defaults to `auto`. Core resolves the host's current default route
on every network collection cycle, so moving between the home LAN, another
Wi-Fi network, and a hotspot does not require a restart. Set `gateway` to an
explicit IP only when an override is intentional. Display state includes the
resolved host and whether it came from automatic detection or configuration.

Example target:

```toml
[[network.targets]]
id = "nas"
name = "Home NAS"
host = "10.10.0.20"
port = 443
alert = true
```

Example service:

```toml
[[services]]
id = "minecraft"
name = "Minecraft"
type = "tcp"
host = "10.10.0.10"
port = 25565
severity = "warning"
```

Use `OLYMPUS_CONFIG=/absolute/path/to/config.toml` to select another file.
Monitoring operations have fixed timeouts and run independently so one slow
service cannot block host, network, agent, or Spotify updates.

Failures and recoveries are debounced. A single lost request does not produce an
incident; repeated failures create one persistent active alert, and repeated
successes resolve it. A reconnecting Display immediately receives current active
alerts in the full state snapshot.

## Optional Spotify integration

Spotify is entirely optional. Without Spotify credentials, Olympus starts and
runs normally with Idle and Development scenes.

When configured, Core polls the current playback and queue, normalizes that data,
and publishes it to the Display. Media remains available underneath higher
priority activity, so the scene can return immediately when a game or IDE closes.
The relevant transitions are:

```text
Spotify playing → MEDIA
IDE active      → DEVELOPMENT overrides MEDIA
Game active     → GAMING overrides DEVELOPMENT and MEDIA
Game closes     → DEVELOPMENT, MEDIA, or IDLE from current state
IDE closes      → MEDIA resumes
Spotify pauses  → IDLE
```

Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard),
add `http://127.0.0.1:8787/callback` as a redirect URI, and copy the example
configuration:

```bash
cd core
cp .env.example .env
```

Set the client ID and client secret in `core/.env`, export those two variables in
your shell, then run the local authorization helper once:

```bash
export OLYMPUS_SPOTIFY_CLIENT_ID=your_client_id
export OLYMPUS_SPOTIFY_CLIENT_SECRET=your_client_secret
.venv/bin/python tools/spotify_auth.py
```

The helper requests only `user-read-currently-playing` and
`user-read-playback-state`. Put the returned refresh token in `core/.env`, then
enable the collector:

```dotenv
OLYMPUS_SPOTIFY_ENABLED=true
OLYMPUS_SPOTIFY_CLIENT_ID=your_client_id
OLYMPUS_SPOTIFY_CLIENT_SECRET=your_client_secret
OLYMPUS_SPOTIFY_REFRESH_TOKEN=your_refresh_token
OLYMPUS_SPOTIFY_POLL_SECONDS=5
```

Start Core with the environment file:

```bash
uvicorn olympus_core.main:app --reload --env-file .env
```

The available settings are:

- `OLYMPUS_SPOTIFY_ENABLED` — opt in to Spotify collection (default `false`)
- `OLYMPUS_SPOTIFY_CLIENT_ID` — Spotify application client ID
- `OLYMPUS_SPOTIFY_CLIENT_SECRET` — Spotify application client secret
- `OLYMPUS_SPOTIFY_REFRESH_TOKEN` — user authorization refresh token
- `OLYMPUS_SPOTIFY_POLL_SECONDS` — polling interval in seconds (default `5`)

Credentials and tokens remain in the ignored `core/.env` file. If Spotify is
temporarily unreachable, Core keeps the last good playback state briefly and
continues serving agents and displays normally. If Spotify later reports an
expired or revoked refresh token, rerun the authorization helper.

## Ambient Idle

Idle is Olympus' calm room overview. It keeps the timezone-aware clock and date
visually dominant, then adds optional current Weather, a short forecast, the
next relevant Calendar event, and limited Today/Tomorrow schedules. Approaching
events receive restrained emphasis without becoming alerts. Core, Internet,
target, and service health remain a quiet footer rather than competing with the
day's context.

Weather and Calendar enrich Idle only. They do not create new modes or change:

```text
GAMING > DEVELOPMENT > MEDIA > IDLE
```

Other scenes continue receiving the global state but deliberately remain
uncluttered. If either optional source is disabled, its section is omitted. If
a working source later becomes stale, the last useful data remains briefly with
a subtle age label; external-data staleness is not an infrastructure alert.

## Weather setup

Olympus uses the [Open-Meteo forecast API](https://open-meteo.com/en/docs),
which requires no account for this use. Location always comes from coordinates
in the ignored `core/config.toml`; Olympus does not use browser geolocation or
IP-based location.

```toml
[olympus]
timezone = "Europe/Berlin"

[weather]
enabled = true
latitude = 48.137
longitude = 11.575
timezone = "Europe/Berlin"
location_name = "Home"
poll_minutes = 10
```

Use an IANA timezone name so daylight-saving transitions are handled by the
timezone database. Weather defaults to ten-minute polling, becomes subtly stale
after thirty minutes without a successful refresh, and remains optional if
coordinates are absent or invalid.

## Calendar setup

Olympus uses Google Calendar's read-only event scope and asks Google to expand
recurring events into ordinary instances. The runtime refreshes access through
a long-lived refresh token on Hermes; authentication never occurs in Display.

1. In Google Cloud, enable the Google Calendar API and configure the OAuth
   consent screen.
2. Create OAuth credentials that permit
   `http://127.0.0.1:8788/callback` (or use Google's loopback-capable desktop
   application client).
3. Copy `core/.env.example` to the ignored `core/.env`, set the client ID and
   secret in your shell, then run the one-time helper:

```bash
cd core
export OLYMPUS_GOOGLE_CLIENT_ID=your_client_id
export OLYMPUS_GOOGLE_CLIENT_SECRET=your_client_secret
.venv/bin/python tools/google_calendar_auth.py
```

The helper requests offline access and prints only the refresh token value to
place in `core/.env`:

```dotenv
OLYMPUS_GOOGLE_CLIENT_ID=your_client_id
OLYMPUS_GOOGLE_CLIENT_SECRET=your_client_secret
OLYMPUS_GOOGLE_REFRESH_TOKEN=your_refresh_token
```

Enable the provider and choose one or more calendars in `core/config.toml`:

```toml
[calendar]
enabled = true
provider = "google"
timezone = "Europe/Berlin"
lookahead_days = 7
poll_minutes = 5
calendar_ids = ["primary", "another-calendar-id"]
```

Then start Core with `--env-file .env`. Google recommends offline access for a
service that must refresh tokens while its user is absent; Olympus uses the
official [OAuth refresh-token flow](https://developers.google.com/identity/protocols/oauth2/web-server)
and [Calendar events endpoint](https://developers.google.com/calendar/api/v3/reference/events/list).

Only title, start/end, all-day state, optional location, and Calendar label are
normalized into Olympus. Descriptions, attendees and their email addresses,
conferencing data, attachments, and notes are neither requested nor exposed.
Cancelled events are excluded; Google expands recurring instances. Calendar
defaults to a seven-day lookahead and five-minute polling.

## Run the macOS agent

```bash
cd agents/macos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m olympus_agent.main
```

The agent generates a permanent random identity in `~/.olympus/agent-id`, keeps
one WebSocket open, sends richer machine telemetry every two seconds, and
reconnects when Core is unavailable. It reports development activity when a
supported IDE process is running.

For local development, the agent connects to localhost. When Core is running on
Hermes on the home LAN, point it at Hermes explicitly:

```bash
OLYMPUS_CORE_WS=ws://10.10.0.10:8000/ws/agents python -m olympus_agent.main
```

Optional settings:

- `OLYMPUS_TELEMETRY_INTERVAL` — telemetry interval in seconds (default `2`)
- `OLYMPUS_RECONNECT_DELAY` — retry delay in seconds (default `3`)
- `OLYMPUS_AGENT_ID_PATH` — identity file override for development/testing
- `OLYMPUS_INTEGRATION_PORT` — local observer TCP port (default `38765`)
- `OLYMPUS_INTEGRATION_STALE_SECONDS` — time before disconnected rich state
  expires (default `5`)

## Run the Windows agent

In PowerShell:

```powershell
cd agents\windows
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OLYMPUS_CORE_WS = "ws://10.10.0.10:8000/ws/agents"
python -m olympus_agent.main
```

The permanent random identity is stored in
`%LOCALAPPDATA%\Olympus\agent-id`. Windows detects the shared IDE set plus
Visual Studio 2022 (`devenv.exe`). NVIDIA metrics use NVML when the supported
driver and binding are available; missing NVIDIA support never stops the agent.
Known games are matched against their actual client process rather than their
launcher, then confirmed against the foreground window. A configurable grace
period keeps the session stable during brief Alt-Tabs.

## Run the Linux agent

```bash
cd agents/linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OLYMPUS_CORE_WS=ws://10.10.0.10:8000/ws/agents python -m olympus_agent.main
```

The permanent random identity is stored under
`~/.local/state/olympus/agent-id` (or `$XDG_STATE_HOME`). Linux uses available
system sensor interfaces for CPU temperature and omits temperature data when no
reliable sensor exists.

All agents report CPU, RAM, uptime, root storage, network byte counters, and IDE
activity. GPU and temperature fields are optional and are omitted when the local
platform cannot provide a trustworthy reading. Olympus never substitutes fake
zero values for unavailable hardware metrics.

## Gaming mode

Gaming is a normalized activity, not a collection of executable checks inside
Core. Windows and Linux agents identify a game through small, testable platform
profiles and report its stable ID and name. Core chooses the active gaming
machine, tracks the in-memory session start, and applies this priority:

```text
GAMING > DEVELOPMENT > MEDIA > IDLE
```

The first profiles cover Fortnite, Minecraft, Among Us, Goat Simulator, and Goat
Simulator 3 where each title can be identified safely. Minecraft matching is
deliberately conservative: a generic Java process is never enough. On Windows,
the Epic launcher and other launchers do not trigger Gaming mode.

The Display has a separate presentation registry. Fortnite, Minecraft, Among Us,
and Goat Simulator each receive a distinct Olympus theme, ambient motif, and
restrained particle behavior. An unknown normalized game receives a stable theme
derived from its ID instead of failing. The Gaming scene shows only available
CPU, RAM, GPU, temperature, VRAM, FPS, and network readings. Generic network
diagnostic latency is explicitly labeled `Internet`; it is not presented as
in-game server ping.

Optional gaming settings:

- `OLYMPUS_GAME_BACKGROUND_GRACE_SECONDS` — seconds a foreground game remains
  active after an Alt-Tab (default `15`)
- `OLYMPUS_PRESENTMON_CSV` — Windows path to a continuously updated external
  PresentMon CSV file; unset by default

FPS is optional. When `OLYMPUS_PRESENTMON_CSV` is set, the Windows agent reads
recent `FrameTime` or `MsBetweenPresents` rows for the active game and derives a
short rolling frame rate. Olympus does not launch PresentMon, and a missing,
stale, unreadable, or incompatible file simply omits FPS. PresentMon is an
external ETW-based tool; see its [official project](https://github.com/GameTechDev/PresentMon)
and [console documentation](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md)
for installation and capture options.

The generic gaming foundation is intentionally anti-cheat-conscious. It uses external
process observation, Windows foreground APIs, ordinary system telemetry, and
optional external presentation data. It does not inject code, hook DirectX,
scan protected memory, or bypass anti-cheat. Deep state is provided only by an
explicit application-level observer such as the optional Minecraft Fabric mod.

## Minecraft deep integration

Minecraft process detection remains built into the normal Windows/Linux agent.
It activates the generic Minecraft Gaming scene whether or not the optional
Fabric observer is installed. The observer only enriches an already detected
Minecraft session, and the Display returns to that generic scene within a few
seconds if the observer disconnects.

The client-only observer reports, where Minecraft exposes the value reliably:

- multiplayer server or singleplayer world context
- position, dimension, and biome
- health, food, and armor
- XP level/progress and game mode
- damage, healing, low-health, death, dimension, join, and leave events

It deliberately does not collect chat, private messages, player lists,
inventory, screenshots, or input. It has no commands and cannot control the
game. Its only network connection is persistent loopback TCP to the local
Olympus Agent; the existing Agent WebSocket carries normalized state and events
onward to Core.

### Build and install the Fabric observer

The project targets Java 21 and keeps all Minecraft/Fabric versions in
`integrations/minecraft-fabric/gradle.properties`, independent of Olympus Core.
With Gradle 9.5 or newer available:

```bash
cd integrations/minecraft-fabric
gradle build
```

Copy `build/libs/olympus-minecraft-0.1.0.jar` into the Minecraft client's
`mods` directory alongside the matching Fabric Loader and Fabric API. It is a
client-only mod; multiplayer servers do not install it. To update Minecraft,
Loader, Loom, or Fabric API later, change only the pinned values in
`gradle.properties`, then rebuild and run the tests.

The observer reconnects automatically if the Agent starts later or restarts.
It publishes deduplicated state at roughly four updates per second and sends
events immediately. If the Agent port is customized, start Minecraft with
`-Dolympus.integration.port=<port>` or set `OLYMPUS_INTEGRATION_PORT` in the
Minecraft process environment to the same value.

## Run the Display

```bash
cd display
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The Display connects to
`ws://127.0.0.1:8000/ws/display` by default and automatically reconnects if Core
is unavailable or restarts.

When the Display is not running on Hermes itself, configure the Core endpoint:

```bash
VITE_OLYMPUS_CORE_WS=ws://10.10.0.10:8000/ws/display npm run dev
```

For v0.7, the Display is a browser-based development UI. It is not yet packaged
or deployed as a kiosk.

## Test

```bash
cd core
python -m unittest discover -s tests

cd ../agents/macos
python -m unittest discover -s tests

cd ../windows
python -m unittest discover -s tests

cd ../linux
python -m unittest discover -s tests

cd ../../display
npm run build

cd ../integrations/minecraft-fabric
gradle build
```

The current milestone does not include a database, Olympus authentication,
Docker, kiosk packaging, application control, audio/RGB output, Night Mode,
Matchday, or News. FPS remains an optional external Windows input, and
unavailable metrics are omitted. macOS and Windows CPU temperature remain
unavailable unless a future reliable local provider is added.
