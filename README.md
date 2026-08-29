# Olympus

Olympus is a local, event-driven home display and automation system.

**Olympus v1.0 is the accepted production baseline.** The complete system is
physically deployed on the WALL display and runs from Hermes. Earlier v0.1–v0.14
milestones remain part of the project history documented below.

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
Agents · Spotify · Weather · Google Calendar · API-Football
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

The Olympus v1.0 production baseline implements this full local path. Agents own device-specific
observation, Core owns interpretation and monitoring, and the Display consumes
only Core's normalized state.

Normal scene priority is explicit and phase-aware:

```text
LIVE MATCHDAY > MAJOR NEWS > GAMING > DEVELOPMENT
              > PRE/POST MATCHDAY > IMPORTANT NEWS > MEDIA
```

When no activity is active, Core chooses `NIGHT` during the configured night
period and `IDLE` during the day. Night is an environmental policy, not another
user activity.

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

For the unattended Raspberry Pi production deployment, including the compiled
same-origin Display, safe backups, health watchdog, and optional Cage/Brave
kiosk, see [Hermes production deployment](docs/hermes-deployment.md).

High-frequency observations remain intentionally in memory. Durable device trust,
incident lifecycle history, and short News presentation memory live in a small
local SQLite database. Hermes is the intended long-term Core host, but running
Core on a local development machine remains fully supported; `core_host`
describes whichever machine currently runs Core.

## Persistence

Olympus v0.12 opens and migrates SQLite before it accepts Agent connections.
The default database is `~/.local/share/olympus/core.db`; set
`persistence.database_path` in the ignored `core/config.toml` to choose another
location. Parent directories and sensitive files use owner-only permissions on
Unix-like systems where supported. SQLite runs with foreign keys, WAL, a busy
timeout, and reliability-oriented synchronous writes so Core and the local admin
CLI can safely coexist.

The database contains only state whose identity or history matters:

- trusted Agent public keys, fingerprints, enrollment and lifecycle timestamps
- hashed, expiring, one-use enrollment credentials
- infrastructure incident start, recovery, duration, and bounded metadata
- short-lived News presentation fingerprints and highest presented level
- explicit numbered schema-migration history

Recovered incidents default to 30 days of retention and News presentation
memory to seven days. Cleanup runs at startup and infrequently during operation.
An active incident keeps its original start time through a Core restart. If its
monitor was removed from configuration, startup resolves it as interrupted by
configuration removal instead of recreating a ghost alert.

Olympus does not persist high-frequency telemetry. CPU, RAM, GPU, temperature,
network rates, FPS, Minecraft state, Spotify progress, weather, calendar,
football clocks, News feed contents, particles, and Display broadcasts remain
ephemeral and are reconstructed from their authoritative sources.

Database-open or migration failure stops Core startup. Persistence failure never
falls back to unauthenticated operation. `GET /health` reports persistence
availability without exposing the database path.

## Trusted device enrollment

Agent authentication is secure by default. Each Agent keeps its existing
permanent Agent ID and creates a persistent Ed25519 private key alongside it.
The private key never leaves that device. Core stores the public key and binds it
to the Agent ID. Each later connection signs a fresh, connection-specific
challenge containing the protocol purpose, Agent ID, and random nonce. Captured
signatures cannot be replayed against a new challenge, and telemetry is rejected
until authentication succeeds.

Create one short-lived enrollment credential locally on Core:

```bash
cd core
.venv/bin/python -m olympus_core.admin enrollment create
```

Supply the printed value to an unenrolled Agent for one start only. Prefer a
temporary environment variable rather than a command-line argument so the
credential is not placed in a process listing or saved as Agent configuration:

```bash
OLYMPUS_ENROLLMENT_TOKEN='OLYMPUS-...' python -m olympus_agent.main
```

Core stores only its SHA-256 hash, consumes it atomically, and never logs the
plaintext value. The default expiry is ten minutes. Remove the environment
variable after enrollment; normal reconnects and Core restarts are automatic.

Manage trust with the local CLI—there is deliberately no Web admin API:

```bash
.venv/bin/python -m olympus_core.admin devices list
.venv/bin/python -m olympus_core.admin devices revoke <agent-id>
```

Revocation retains historical metadata, disconnects an active device within the
configured refresh window, and rejects future reconnects. Re-trusting a revoked
Agent requires a new token and explicit enrollment. If an Agent private key is
lost, revoke the old binding, allow the Agent to generate or receive a new local
key, create a new token, and re-enroll. Never delete its permanent Agent ID just
to rotate the key. A second device claiming the same ID with a different key is
rejected.

For isolated legacy development only, `security.require_agent_auth = false`
restores the old handshake and emits a clear startup warning. This is never the
default and does not create a wall alert.

> Device authentication verifies Agent identity. Plain `ws://` transport is not
> encrypted. Use an encrypted transport such as `wss://` or a trusted encrypted
> network when confidentiality against local network interception is required.

The Display WebSocket and the loopback-only Minecraft-to-Agent protocol are not
enrolled in v0.12.

### Upgrade from v0.11 to v0.12

1. Upgrade Core and the Agents; keep every existing `agent-id` file.
2. Start Core so it creates and migrates SQLite.
3. Create one enrollment token per Agent with the admin command above.
4. Start each Agent once with `OLYMPUS_ENROLLMENT_TOKEN` in its environment.
5. Remove the token variable. Future Agent and Core restarts need no manual step.

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

Core also normalizes a small shared-host health model for Hermes: CPU/RAM/swap,
load average, disk, uptime, CPU temperature when the platform exposes it, and
Raspberry Pi throttling/undervoltage flags when `vcgencmd` is available. The
Display renders this with network, Agent, and selected service state in a quiet
persistent bottom strip. Missing metrics remain absent. Olympus does not label
PMIC/firmware signals as total wall power and does not invent current or wattage.

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
Game closes     → DEVELOPMENT, MEDIA, NIGHT, or IDLE from current state
IDE closes      → MEDIA resumes
Spotify pauses  → NIGHT or IDLE from the current time policy
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

Weather and Calendar enrich the ambient Idle and Night scenes. They do not
create activity modes or change:

```text
GAMING > DEVELOPMENT > MEDIA
```

Other scenes continue receiving the global state but deliberately remain
uncluttered. If either optional source is disabled, its section is omitted. If
a working source later becomes stale, the last useful data remains briefly with
a subtle age label; external-data staleness is not an infrastructure alert.

## Night Mode

Night Mode is Olympus' calm, dim fallback when the room has no higher-priority
activity. Its scene emphasizes the clock and date, then current temperature,
the next event and tomorrow's short agenda, with system health kept to a quiet
footer. Missing Weather or Calendar data simply removes that section.

Night is an environmental policy, not an activity mode. Gaming, Development,
and Media still override the Night scene. While any of those activities remains
active, its scene identity stays intact and receives a lower-brightness,
lower-saturation Night adaptation. When the activity ends during the configured
period, Olympus returns to `NIGHT` instead of `IDLE`.

The default policy is:

```text
Sunday–Thursday evening   22:00 → 07:30
Friday–Saturday evening   00:00 → 07:30
```

Midnight starts belong to the end of the named evening. With the defaults,
Friday remains day policy through 23:59, transitions to Night at Saturday
00:00, and returns to day policy at 07:30. Saturday behaves the same way into
Sunday. All boundaries use the `[olympus]` IANA timezone, including daylight-
saving transitions; the browser and Core host timezone do not decide policy.

Configure the schedule in the ignored `core/config.toml`:

```toml
[olympus]
timezone = "Europe/Berlin"

[night]
enabled = true
weekday_start = "22:00"
weekend_start = "00:00"
end = "07:30"
weekend_days = ["friday", "saturday"]
```

Times must use 24-hour `HH:MM` values and weekend days must be valid weekday
names. Set `enabled = false` for the v0.7 fallback behavior:

```text
GAMING > DEVELOPMENT > MEDIA > IDLE
```

Night currently changes software presentation only. It does not control
physical monitor brightness, audio, HDMI/display power, or any room hardware.

## Matchday

Olympus provides an optional, read-only FC Bayern München match center backed by
either [football-data.org v4](https://docs.football-data.org/general/v4/index.html)
or [API-Football v3](https://www.api-football.com/documentation-v3). Core owns
the provider boundary and converts provider responses into the same Olympus
models before anything reaches the Display. Provider-specific response shapes,
team IDs, and credentials never reach the browser.

Enable the provider in the ignored `core/config.toml`:

```toml
[football]
enabled = true
provider = "football-data"
# football-data.org team ID for FC Bayern München. This is not interchangeable
# with API-Football's team ID.
team_id = "5"
tracked_id = "bayern"
team_name = "FC Bayern München"
team_short_name = "Bayern"
team_code = "FCB"
timezone = "Europe/Berlin"
poll_upcoming_minutes = 30
poll_near_match_minutes = 5
poll_pre_match_seconds = 60
poll_live_seconds = 15
poll_half_time_seconds = 30
poll_post_match_seconds = 60
poll_team_stats_seconds = 60
poll_player_stats_seconds = 60
live_stale_seconds = 60
unavailable_seconds = 900
low_quota_remaining = 25
critical_quota_remaining = 5
max_history_samples = 96

[football.matchday]
pre_match_minutes = 60
post_match_minutes = 20

[football.players]
# football-data.org does not provide Olympus' rich player-performance contract
# on the free fixture path, so watched-player analytics remain unavailable.
watched = []
rating_change_threshold = 0.25
```

Put the dedicated API key in `core/.env`, never in TOML or browser code:

```dotenv
OLYMPUS_FOOTBALL_DATA_API_KEY=your_football_data_org_key
```

Then start Core with `--env-file .env`. The football-data.org provider supports
current and upcoming fixtures, home/away teams, competitions, kickoff times,
match phases, and running/final scores. FC Bayern München is team `5` in
football-data.org. Optional unfolded goals, cards, substitutions, and lineups
are normalized when the response includes them. Missing free-tier coverage
leaves events, lineups, team statistics, and player analytics empty or
unavailable without disabling basic Matchday.

Paid API-Football support remains available with its separate credential and
provider-specific team ID:

```toml
[football]
enabled = true
provider = "api-football"
team_id = "157"
# API-Football season values are starting years; this is optional for backward
# compatibility but should be set when the provider requires the Season field.
season = 2025
tracked_id = "bayern"
team_name = "FC Bayern München"
team_short_name = "Bayern"
team_code = "FCB"
timezone = "Europe/Berlin"
```

```dotenv
OLYMPUS_FOOTBALL_API_KEY=your_api_football_key
```

API-Football player performance uses the provider's
fixture player-statistics data, including available minutes, ratings, goals,
assists, shots, passing, defending, duels, dribbles, cards, and penalties for
both teams. Every field is optional. Missing coverage removes the corresponding
presentation rather than manufacturing a zero or an error panel. Ratings are
always described as provider performance ratings, not objective judgments or an
official Player of the Match award.

Polling adapts to match proximity. API-Football score, status, and events keep
the configured fast live cadence (15 seconds by default), while team and player
analytics are sampled at their slower 60-second update cadence. A combined
fixture response avoids extra endpoint calls; Core freezes a usable lineup and
does not duplicate unchanged history samples. Provider quota headers are
retained in diagnostics. Low quota stretches analytics first, then the fast poll
only when the budget is critical.
football-data.org is clamped to at most one request per minute, including live
matches, and slows to five minutes after full-time to stay comfortably inside
its free-tier rate limit. `429` responses respect provider reset guidance.
Timeouts and outages retain the last trusted state, mark it stale, and recover
without destabilizing Core.

More than 60 minutes before kickoff, Idle and Night may show a subtle next-match
note without a scene takeover. During pre-match and the 20-minute post-match
window, Gaming and Development still win, Matchday wins over Media and the
fallback scenes, and Night only affects the surrounding time policy. Once the
provider declares the match live, Matchday becomes the highest normal scene
priority. Full-time stays visible through the configured post-match window.

The 1080p-oriented Display shows both starting XIs before kickoff, with subtle
watched-player status. Live, half-time, and full-time retain the dominant score
and clock while adding watched-player cards, current/final top-rated performers,
meaningful team statistics, substitutions, cards, scorers, and assists. Full-time
atmosphere responds to the normalized Bayern-relative `win`, `draw`, or `loss`.
Transient goal events never increment the score themselves and never wait for a
slower rating refresh.

### Match Flow

Core keeps bounded, in-memory team-stat and watched-player rating histories for
the current fixture. Match Flow is an Olympus-derived, smoothed activity view.
It weights changes in shots, shots on target, and corners, blends available
possession context, and adds bounded emphasis for supported match events such as
goals and cards. Values are relative visualization weights—not possession,
probabilities, xG, or provider-supplied tracking. With only events, it renders a
reduced flow; with no honest input, it is omitted.

Olympus does not currently know the exact physical position of the ball. Match
Flow visualizes match evolution from supported statistics and events. Olympus
does not scrape OneFootball or private APIs, invent spatial coordinates, use
betting odds, or make predictions. Coverage and update timing vary by competition
and provider plan.

Histories live only in memory for one active fixture. After a mid-match Core
restart, current score, events, lineup, statistics, and ratings recover from the
provider without replaying historical goals or rating changes. Match Flow starts
an honest new observation history; older event markers remain available, but
past stat snapshots are not reconstructed or faked.

For development without live football or an API quota, use the supported local
fixture provider. It exercises the real collector, state resolver, event hub,
WebSocket, and Display path:

```bash
cd core
export OLYMPUS_CONFIG=/absolute/path/to/simulation-config.toml
export OLYMPUS_FOOTBALL_FIXTURE_PATH=/tmp/olympus-football.json
.venv/bin/python tools/football_simulator.py upcoming --output "$OLYMPUS_FOOTBALL_FIXTURE_PATH"
.venv/bin/python -m uvicorn olympus_core.main:app --reload
```

Set `football.provider = "fixture"` in that simulation config, then advance a
single phase or run the complete flow in another terminal:

```bash
.venv/bin/python tools/football_simulator.py ratings --output /tmp/olympus-football.json
.venv/bin/python tools/football_simulator.py goal --output /tmp/olympus-football.json
.venv/bin/python tools/football_simulator.py sequence --delay 16 --output /tmp/olympus-football.json
```

The sequence covers pre-match lineups, evolving ratings and statistics, goals,
half-time, substitutions, opponent events, a red card, win/loss full-time states,
missing player coverage, quota pressure, and an outage. For fast local sequences,
set the two analytics polling intervals to one second in the simulation-only
configuration. The fixture provider remains development-only; fake match data is
not built into production state. Matchday deliberately excludes audio, lighting,
betting, predictions, controls, and standings.

## News

Olympus v0.11 adds optional News awareness without turning the room into a
scrolling news site. Production collection is RSS/Atom-first. Feeds are fetched
by Core, parsed with `feedparser`, and normalized into Olympus-owned articles and
story clusters. Display never contacts publishers directly.

Enable News and add reputable public feeds in the ignored `core/config.toml`:

```toml
[news]
enabled = true
provider = "rss"
poll_minutes = 5
retention_hours = 48
stale_minutes = 15
unavailable_minutes = 60
default_language = "en"
local_regions = ["DE"]

[news.presentation]
ambient_limit = 3
news_scene_seconds = 20
major_scene_seconds = 45
cooldown_minutes = 30
notable_threshold = 0.55
important_threshold = 0.68
major_threshold = 0.86

[news.interests]
technology = 1.1
germany = 1.2
world = 1.0

[[news.feeds]]
id = "publisher-world"
name = "Publisher World"
url = "https://publisher.example/world.xml"
language = "en"
region = "DE"
topic = "world"
trust = 1.0
```

Feed URLs are configuration, never Core logic. `trust` and interest multipliers
are local ranking preferences—not truth, credibility verdicts, or political
judgments. Olympus never infers location from an IP address. German and English
headlines retain their original language; v0.11 does not translate them.

Core sends `ETag` and `Last-Modified` validators after a successful response and
accepts `304 Not Modified` without reprocessing the feed. Each feed has isolated
health state, so a timeout, malformed document, `404`, `429`, or server failure
does not stop healthy publishers. If all feeds remain unavailable, recent News
first becomes stale and then disappears quietly from Idle/Night—never as an
infrastructure alert.

Olympus retains feed contents only in a bounded recent in-memory window. It keeps
publisher headlines, short publisher-supplied summaries, source, topic metadata,
timestamp, and canonical URL there. SQLite remembers only a short stable story
fingerprint, highest presented level, and presentation time so a restart cannot
annoyingly replay the same takeover. Summary HTML becomes length-limited plain
text; obvious tracking parameters are removed. Olympus does not download article
bodies, persist an article archive, scrape publisher pages, bypass paywalls, or
claim authorship of publisher text.

### Clustering and importance

Exact GUID/URL/title matches and conservative headline token/sequence similarity
group likely duplicate reports into one story cluster. False negatives are
preferred over merging loosely related stories. A representative publisher
headline is chosen deterministically; Olympus does not rewrite it.

Importance uses a local, deterministic score based on recentness, independent
source count, configured source weight, broad topic, configured regional
relevance, conservative developing-event terms, source velocity, and age decay.
The factor breakdown remains in Core state for tuning. Multiple trusted sources
matter substantially more than punctuation or a lone “breaking” keyword, and a
single article cannot reach `major` from sensational wording alone.

> Olympus importance is a local heuristic used to decide presentation priority.
> It is not an objective assessment of journalistic importance or truth.

News ranking and clustering are local and deterministic. No LLM, embeddings API,
cloud AI, betting data, or private semantic service is required. GDELT is not a
v0.11 dependency; the deliberately smaller RSS baseline is complete on its own.

### Presentation policy

Ambient and Notable stories never take over the room. Idle shows at most three
compact headlines and Night shows one subdued headline. Important stories may
temporarily replace Idle, Night, or Media. Major stories may also replace Gaming
and Development. Pre/post Matchday remains protected from Important News, and a
live Bayern match remains protected even from generic Major News:

```text
LIVE MATCHDAY > MAJOR NEWS > GAMING > DEVELOPMENT
              > PRE/POST MATCHDAY > IMPORTANT NEWS > MEDIA > NIGHT/IDLE
```

Core owns the exact 20/45-second presentation interval. Reconnecting Displays
receive the active story and its actual end time. A higher-priority context may
interrupt News while its timer continues in the background. Cooldown and
durable highest-presented-level memory prevent repeated polls, Core restarts, or
a burst of stories from creating a presentation queue. `important → major`
escalation may present again. Existing clusters also establish a silent baseline
on Core startup, so restarts never replay old “breaking” stories.

Routine Bayern reporting is capped below takeover level because Matchday is the
specialized authority. Routine forecasts similarly defer to the Weather
integration; genuinely corroborated emergency weather reporting may still rank
as News. v0.11 also introduces a small generic `LiveEvent` model for future
structured providers such as elections or launches, but ships no election or
other live-event provider. Structured integrations will outrank generic News for
the same event.

For a complete development-only sequence through the real collector, resolver,
event hub, WebSocket, and Display path, set `news.provider = "fixture"`, configure
`OLYMPUS_NEWS_FIXTURE_PATH`, and run:

```bash
cd core
.venv/bin/python tools/news_simulator.py ordinary --output /tmp/olympus-news.json
.venv/bin/python tools/news_simulator.py sequence --delay 5 --output /tmp/olympus-news.json
```

The simulator covers exact duplication, cross-source clustering, Notable,
Important and Major escalation, unchanged/cooldown behavior, simultaneous
stories, stale feeds, and recovery. Fake articles remain fixture-provider data
and never enter production News state.

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

## Install the native Agent

Olympus v0.13 introduced the self-contained, per-user Agent application retained
in v0.14 for
Windows x86_64, macOS arm64, and Linux x86_64. Python is not required on the
target machine. Core and Display remain source deployments in this milestone.

The Agent deliberately runs inside the signed-in user's interactive session. It
needs to observe foreground applications and gaming activity, so it is not a
Windows service, macOS daemon, root process, or system-wide Linux service.

Each release archive contains the native build produced on its matching operating
system plus a `.sha256` checksum. Extract or copy it to a stable per-user path
before installing autostart:

- Windows: `%LOCALAPPDATA%\Programs\Olympus Agent\OlympusAgent.exe`
- macOS: `~/Applications/Olympus Agent.app`
- Linux: `~/.local/lib/olympus-agent/olympus-agent`

The builds are currently unsigned. Windows SmartScreen or macOS Gatekeeper may
therefore ask for confirmation on first launch. Olympus does not claim code
signing, notarization, or an automatic updater in v0.14.
The current macOS process-based activity detection does not require Accessibility
permission, and the Agent does not request it.

### First-time setup and enrollment

Run commands with the installed executable. The examples below use
`olympus-agent` as shorthand for that full platform-specific path.

```bash
olympus-agent setup --core-url ws://10.10.0.10:8000/ws/agents \
  --display-name "Main PC"
olympus-agent enroll
olympus-agent install-autostart
olympus-agent status
```

`setup` is interactive when either option is omitted and fully headless when both
are supplied. `enroll` reads its one-use token with hidden input. Automation may
instead supply `OLYMPUS_ENROLLMENT_TOKEN` for that process; the token is removed
from the Agent process environment after use and is never written to configuration.
Create the token locally on Core as described in
[Trusted device enrollment](#trusted-device-enrollment).

Configuration precedence is command-line option, environment variable, saved
configuration, then built-in default. `OLYMPUS_CORE_URL` is the preferred Core
override; the v0.12 `OLYMPUS_CORE_WS` name remains compatible. Use `wss://` when
the network path is not already trusted and encrypted.

`install-autostart` creates only a current-user startup definition:

- Windows Scheduled Task with an interactive logon trigger
- macOS LaunchAgent in `~/Library/LaunchAgents`
- Linux `systemd --user` service enabled for the normal login session

Linux does not enable lingering, so the Agent stops when the user's session ends.
If `systemd --user` is unavailable, installation reports that fact and the Agent
can still be started manually. Autostart installation and removal are idempotent;
`uninstall-autostart` preserves configuration, device ID, and private key.

### Local files

| Platform | Configuration | Identity, key, lock, and logs |
| --- | --- | --- |
| Windows | `%APPDATA%\Olympus\agent.toml` | `%LOCALAPPDATA%\Olympus\` |
| macOS | `~/Library/Application Support/Olympus/agent.toml` | `~/Library/Application Support/Olympus/` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/olympus/agent.toml` | `${XDG_STATE_HOME:-~/.local/state}/olympus/` |

Background logs are written to `logs/agent.log`, rotate at 3 MiB, and retain five
older files. Enrollment credentials are redacted. `olympus-agent status` reports
the configured Core and name, identity presence and public-key fingerprint,
autostart state, and whether another Agent process owns the runtime lock. It never
prints the private key or enrollment credential.

When v0.13 first sees a v0.12 identity in the legacy location, it copies and
verifies the ID and private key into the platform's current state directory. The
original files remain in place, and an existing destination is never overwritten.
That preserves the Core trust binding through the upgrade.

### Updating or removing the Agent

There is no in-place auto-updater. To update, stop the user startup entry, replace
the installed application directory with the new same-platform archive, run
`olympus-agent --version`, and install autostart again. Keep the configuration and
state directories; they are intentionally separate from program files.

To stop automatic startup without losing trust:

```bash
olympus-agent uninstall-autostart
```

For a complete reset, first revoke the device on Core, stop the Agent, remove the
autostart entry, and only then delete the local configuration and state directories.
Deleting the private key without revoking its old Core binding requires a fresh
enrollment token.

### Troubleshooting

- Agent absent in Display: run `olympus-agent status`, confirm Core's URL, then
  inspect `logs/agent.log`. Core outages do not terminate the Agent; it reconnects.
- “Enrollment required”: create a new one-use Core token and run
  `olympus-agent enroll` before starting the background process.
- “Already running”: the per-user OS lock is working. Inspect `status` rather than
  launching a second collector.
- Autostart inactive: reinstall it while signed in as the intended user. On Linux,
  confirm a working `systemd --user` session; manual startup remains supported.
- Lost key: revoke the old Agent ID/key binding on Core, retain the permanent Agent
  ID when possible, then enroll the regenerated key.
- Missing GPU, temperature, FPS, or Minecraft detail: these inputs remain optional.
  NVIDIA requires a compatible NVML stack, PresentMon CSV must be supplied
  externally, and Minecraft detail requires the Fabric observer. Their absence
  never prevents ordinary CPU/RAM/activity telemetry.

### Build native release archives

Build each artifact on the operating system and CPU architecture it targets;
the build does not cross-compile. After installing that platform Agent's normal
requirements:

```bash
python -m pip install -r agents/packaging/requirements.txt
python scripts/build-agent.py --archive
```

The script creates an onedir application, checks `--version` and `status` from the
frozen executable, then writes the native archive and checksum to `dist/releases`.
The packaging workflow repeats the build on native Windows, macOS, and Linux CI
runners and uploads the resulting archives; it does not publish a release.

## Development: run the macOS agent

```bash
cd agents/macos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m olympus_agent.main
```

The agent uses the current macOS configuration and state paths documented above,
and safely imports an existing identity from the legacy `~/.olympus` directory.
It keeps one WebSocket open, authenticates every connection, sends richer machine
telemetry every two seconds, and reconnects when Core is unavailable. It reports
development activity when a supported IDE process is running.

For local development, the agent connects to localhost. When Core is running on
Hermes on the home LAN, point it at Hermes explicitly:

```bash
OLYMPUS_CORE_WS=ws://10.10.0.10:8000/ws/agents python -m olympus_agent.main
```

Optional settings:

- `OLYMPUS_TELEMETRY_INTERVAL` — telemetry interval in seconds (default `2`)
- `OLYMPUS_RECONNECT_DELAY` — retry delay in seconds (default `3`)
- `OLYMPUS_AGENT_ID_PATH` — identity file override for development/testing
- `OLYMPUS_AGENT_KEY_PATH` — private-key file override for development/testing
- `OLYMPUS_ENROLLMENT_TOKEN` — one-use enrollment input; do not save permanently
- `OLYMPUS_INTEGRATION_PORT` — local observer TCP port (default `38765`)
- `OLYMPUS_INTEGRATION_STALE_SECONDS` — time before disconnected rich state
  expires (default `5`)

## Development: run the Windows agent

In PowerShell:

```powershell
cd agents\windows
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OLYMPUS_CORE_WS = "ws://10.10.0.10:8000/ws/agents"
python -m olympus_agent.main
```

The permanent random identity and device key are stored in
`%LOCALAPPDATA%\Olympus\agent-id` and `agent-key.pem`. Windows detects the shared IDE set plus
Visual Studio 2022 (`devenv.exe`). NVIDIA metrics use NVML when the supported
driver and binding are available; missing NVIDIA support never stops the agent.
Known games are matched against their actual client process rather than their
launcher, then confirmed against the foreground window. A configurable grace
period keeps the session stable during brief Alt-Tabs.

## Development: run the Linux agent

```bash
cd agents/linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OLYMPUS_CORE_WS=ws://10.10.0.10:8000/ws/agents python -m olympus_agent.main
```

The permanent random identity and device key are stored under
`~/.local/state/olympus/agent-id` and `agent-key.pem` (or `$XDG_STATE_HOME`). Linux uses available
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
machine, tracks the in-memory session start, and applies this activity priority:

```text
GAMING > DEVELOPMENT > MEDIA
```

The inactive fallback remains `NIGHT` or `IDLE` according to Core's time policy;
crossing a policy boundary does not reset a game session.

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
No global Gradle installation is required. Install a Java 21 JDK, then use the
committed, checksum-pinned wrapper:

```bash
cd integrations/minecraft-fabric
./gradlew build
```

On Windows, run `gradlew.bat build` from the same directory.

Copy the distributable `build/libs/olympus-minecraft-0.1.0.jar` into the
Minecraft client's `mods` directory alongside the matching Fabric Loader and
Fabric API. Do not install `olympus-minecraft-0.1.0-sources.jar`; that artifact
is for source inspection and IDE use. The observer is a
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

For v1.0, the same Display remains available through Vite during development and
is compiled into static assets served directly by Core in production. The
accepted WALL deployment launches those assets through the minimal
Cage/Brave kiosk on Hermes.

## Test

```bash
cd core
python -m unittest discover -s tests

cd ../agents/common
python -m unittest discover -s tests

cd ../macos
python -m unittest discover -s tests

cd ../windows
python -m unittest discover -s tests

cd ../linux
python -m unittest discover -s tests

cd ../../display
npm run build

cd ..
scripts/hermes/build-release.sh --skip-node-install

cd integrations/minecraft-fabric
./gradlew build
```

The root `VERSION` file is the product release source of truth. A deployable
Hermes build requires a clean Git tree and includes `RELEASE-METADATA.json` with
the version and exact full source revision. For local packaging experiments only,
`--allow-dirty` creates a clearly marked development artifact; the Hermes
installer rejects such an artifact.

The v1.0 baseline includes Hermes production release tooling and a minimal kiosk
without packaging Core as a native binary or adding Docker, a full
desktop, automatic online updates, application control, audio/RGB output,
physical display power control, or a Web administration surface. FPS remains an
optional external Windows input, and unavailable metrics are omitted. macOS and
Windows CPU temperature remain unavailable unless a future reliable local
provider is added.
