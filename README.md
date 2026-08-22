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


## Architecture

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


## Initial architecture

```text
macOS Agent ──/ws/agents──> Olympus Core ──/ws/display──> Display
    │                              │                          │
    └─ observes CPU, RAM, and IDEs  └─ interprets global mode └─ renders state
```

Olympus v0.3 implements this full local path. The agent owns device-specific
observation, Core owns mode selection and media collection, and the Display
consumes only Core's interpreted state.

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

State is intentionally held in memory for this milestone.

## Optional Spotify integration

Spotify is entirely optional. Without Spotify credentials, Olympus starts and
runs normally with Idle and Development scenes.

When configured, Core polls the current playback and queue, normalizes that data,
and publishes it to the Display. Scene priority is:

```text
Spotify playing → MEDIA
IDE active      → DEVELOPMENT overrides MEDIA
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

## Run the macOS agent

```bash
cd agents/macos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m olympus_agent.main
```

The agent generates a permanent random identity in `~/.olympus/agent-id`, keeps
one WebSocket open, sends CPU/RAM telemetry every two seconds, and reconnects when
Core is unavailable. It reports development activity when a supported IDE process
is running.

For local development, the agent connects to localhost. When Core is running on
Hermes on the home LAN, point it at Hermes explicitly:

```bash
OLYMPUS_CORE_WS=ws://10.10.0.10:8000/ws/agents python -m olympus_agent.main
```

Optional settings:

- `OLYMPUS_TELEMETRY_INTERVAL` — telemetry interval in seconds (default `2`)
- `OLYMPUS_RECONNECT_DELAY` — retry delay in seconds (default `3`)
- `OLYMPUS_AGENT_ID_PATH` — identity file override for development/testing

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

For v0.3, the Display is a browser-based development UI. It is not yet packaged
or deployed as a kiosk.

## Test

```bash
cd core
python -m unittest discover -s tests

cd ../agents/macos
python -m unittest discover -s tests

cd ../../display
npm run build
```

The current milestone does not include a database, Olympus authentication,
Docker, kiosk packaging, or future scenes and integrations. Windows and Linux
agents remain future work.
