# Olympus 1.1 — live integration reliability

This release uses the existing Agent telemetry WebSocket, Core stores, resolver,
Control at `/control/`, and Display. There is no new service or listener. Hermes
installation and managed configuration migration remain in the existing immutable
release pipeline. No production configuration or credentials were changed during
implementation.

## Audit and data flow

* Media: optional desktop adapter → authenticated Agent telemetry → AgentRegistry
  → MediaStateStore source selection → StateService → ModeResolver → Display.
  SpotifyApi/SpotifyCollector supplies the same store's cloud fallback. The existing
  Display progress hook extrapolates from `observed_at`; it makes no network polls.
* News: RSS conditional HTTP → normalization → bounded NewsEngine clustering and
  factors → NewsCollector presentation scheduling/persistent memory → NewsStateStore
  → resolver → ambient headlines or News scene.
* Football: existing API-Football/football-data provider → normalized snapshot →
  MatchdayPolicy and event reconciliation/analytics → FootballStateStore → resolver
  → existing Matchday scene. Snapshots continue updating the mounted scene.
* Control simulations transform outgoing presentation only. Real collectors and
  stores continue running; RESET ALL removes that transform without a restart.

Confirmed defects included Spotify 3xx falling into JSON parsing, queue failure
invalidating good playback, counting feed IDs/copy text as corroboration, renewing
undated article observation times, per-story-only presentation cooldowns, replaying
newly seen events after outages, and retaining expired Matchday during long retries.
The historical Spotify redirect itself was not reproduced: its cause is unknown.
A 301 is not evidence of rate limiting.

## Local media

Opt in on each desktop Agent with `OLYMPUS_LOCAL_MEDIA_ENABLED=true`.
`OLYMPUS_LOCAL_MEDIA_POLL_SECONDS` defaults to 5 and has a minimum of 5 seconds;
macOS has a minimum of 10 seconds. Existing telemetry transports the results.

| OS | Adapter | Requirements / limitations |
| --- | --- | --- |
| Linux | MPRIS on the user's session D-Bus | Optional `dbus-next`; run in the logged-in user's session. A system service without session-bus access reports unavailable. Players must expose MPRIS. |
| Windows | Windows.Media.Control GSMTC | Optional PyWinRT `winrt-Windows.Media.Control` package and a supported desktop session. No artwork extraction yet. No player-control commands are sent. |
| macOS | Spotify's scripting interface through fixed JXA/osascript | Spotify installed and running, with macOS Automation permission. Does not launch Spotify. Generic system sessions are unsupported. Artwork is included only when an HTTPS URL is supplied. |

For source installations, install the common package's optional extra in the
Agent environment: `python -m pip install -e 'agents/common[local-media]'` from
the repository root. Base packages remain usable without media SDKs. Native
packaged Windows/macOS integration and Automation permission prompts require
on-device verification; the portable tests do not establish native availability.

Normalized observations include source/player, session, track, status, timestamp,
position, available metadata, and read capabilities. Absent duration/position use
existing model zero sentinels; capability flags indicate whether position was
provided. Metadata-derived IDs are explicitly prefixed `metadata:` when an OS
supplies no stable track ID. No album, artist, or scorer metadata is synthesized.

Fresh confirmed local playing wins; an already selected playing device remains
selected while fresh. Initial ties use Agent ID/session ID order. Paused/stopped,
unknown, unavailable, disconnected, or expired local sources cannot suppress
confirmed remote playback. Core `[media]` defaults: `local_stale_seconds=15`,
`cloud_stale_seconds=60`. Timestamp skew over two seconds into the future is
rejected for local selection. There is no generic remote artwork proxy.

## Spotify cloud and credentials

Defaults: `OLYMPUS_SPOTIFY_POLL_SECONDS=15`,
`OLYMPUS_SPOTIFY_ACTIVE_POLL_SECONDS=5`,
`OLYMPUS_SPOTIFY_LOCAL_POLL_SECONDS=60`. Error restrictions override these.
HTTP 204 means no playback; 401 permits one token refresh retry; persistent
401/403, rejected refresh credentials, and unexpected redirects defer requests
for five minutes. 429 honors Retry-After, including HTTP dates. Transient failures
use bounded exponential polling backoff. Invalid JSON, timeout, network failure,
HTTP status and redirect outcomes are separately diagnosable. Enrichment failure
cannot erase a valid playback observation. Context-name cache is bounded.

Core rejects redirects on both token and API requests, even if a supplied HTTP
client normally follows them. It never logs Location, response bodies, tokens,
headers or arbitrary exception strings. Diagnose the status and endpoint class
(authentication versus playback), then check the Spotify application/account
permissions and registered redirect URI in the developer dashboard. Do not copy
sensitive redirect URLs into Control or logs. There is no claimed numerical
Spotify quota: see [Spotify's rate-limit documentation](https://developer.spotify.com/documentation/web-api/concepts/rate-limits).

To renew credentials, run the existing `core/tools/spotify_auth.py` interactively
in a trusted terminal, using the documented OAuth application settings. Keep its
returned token private. Update only the appropriate values in
`/etc/olympus/secrets.env` (development: ignored `core/.env`); do not put credentials
in TOML or Git. Restart Core only after a separately authorized production change.
No authenticated Spotify requests were made during this implementation.

## News importance and interruption policy

AMBIENT is ordinary information. NOTABLE is elevated and non-interruptive.
IMPORTANT requires multiple distinct reporting groups, valid publication dates,
a substantial-development signal and the configured score. MAJOR additionally
requires three reporting groups and stronger severity/score criteria. RSS never
creates CRITICAL; that remains a separate system/safety alert path. Source trust
and personal interest influence ranking, not proof of a claim.

Publisher hostnames (or configured per-feed `editorial_group`), identical
headline/summary text, canonical URLs and explicit wire attribution are collapsed
for corroboration. This is a conservative heuristic, not a truth-verification
system: differently rewritten or unattributed syndicated copy cannot always be
recognized. Configure the same editorial_group for feeds from one publisher or
wire service. Sports/entertainment never exceed NOTABLE. A severe word without a
substantial-development signal cannot independently qualify for interruption.

Canonical URLs, stable article IDs and conservative headline similarity preserve
story identity. Cosmetic edits retain first observation time and presentation
identity. Escalation of importance is the deterministic material-update signal;
there is no semantic fact-change model or LLM classifier. Undated/future-dated
items cannot interrupt. Old stories are never refreshed merely by polling again.

Per-story cooldown defaults to 30 minutes; global presentation cooldown is 300
seconds, with 10-second minimum dwell and at most 30-second presentations. An
escalation of the same active story may preempt after minimum dwell. Ordinary
News cannot preempt Gaming, Development or Matchday. Existing MAJOR priority is
preserved, including live Matchday protection. Presentation history is bounded
in memory and uses the existing persistent repository. Feed diagnostics expose
successful parse time, latest publication, failure count, retry time and staleness.
A failed fetch differs from a successfully parsed empty feed. Conditional requests,
per-feed backoff and provider Retry-After reduce outage traffic.

## Football coverage, lifecycle and freshness

Provider team IDs remain distinct: Bayern is `157` on API-Football and `5` on
football-data.org. Home/away is normalized by those IDs, never display names.
Only provider-reported scores, events, lineups and statistics are displayed.
Existing periods cover second half, extra time and penalties; no timer infers FT.

[API-Football pricing](https://www.api-football.com/pricing) explicitly limits free
plan seasons. [Its coverage page](https://www.api-football.com/coverage) warns that
coverage varies by season/fixture. Access to Bayern 2026/27 was **not authenticated
or verified**. An obsolete configured season is rejected rather than substituted.
Set `season=2026` only if the account actually has 2026/27 access.

[football-data.org pricing](https://www.football-data.org/pricing) lists delayed
scores/schedules for its free tier, with paid live-score and deeper-data tiers.
Its competition coverage is subscription dependent; Bundesliga access does not
establish German cup or European access. Existing interfaces are retained; no
scraping or new fallback provider was added. An empty successful response does
not prove current-season entitlement. Capability fields use null for unknown.
`[football].live_scores_confirmed=false` is the safe default; set true only after
verifying the subscription. This declaration is operator-confirmed, not automated
subscription discovery. Events/lineups/statistics are advertised only when observed.

Outages retain the last observation, mark live context stale after
`live_stale_seconds` (60), and remove Matchday after `unavailable_seconds` (900),
including during long retry waits. Stale results are not treated as confirmed
wins. The Display labels unconfirmed live capability as delayed/last-known data.
Quota backoff honors Retry-After; initial provider failures publish unavailable
state. Known error states distinguish unsupported configured season, quota,
missing key/access denial and generic unavailable provider; some provider-specific
empty/permission responses remain ambiguous without live credentials.

Initial sync and recovery baseline event history. Repeated IDs are not re-emitted;
goal metadata changes without score growth are suppressed. Downward score changes
produce correction events instead of goal celebrations. Provider snapshots replace
the displayed event list, including revoked goals when the provider removes them.
Goal identity does not survive a Core restart as persistent history, but startup
baselining prevents replay. Missing events/statistics remain absent.

## Configuration, diagnostics and compatibility

Defaults are backward compatible with existing files; example configuration adds
media freshness, News global cooldown/minimum dwell, and football live capability.
Unknown production keys and `secrets.env`, `control.json`, authentication, seasonal
world and night behavior are preserved. Existing explicit Spotify interval values
remain effective; update old 1.5-second values manually if desired.

Control status/diagnostic bundles include chosen source, cloud outcome, per-Agent
media capability health, News factors/feed health/cooldown, and football capability,
quota, freshness and last-success fields through the real snapshot. Simulation Lab
adds media local/outage/recovery, News outage/recovery, and football
outage/recovery/score-correction examples. These are presentation fixtures, not
end-to-end provider failure injection.

## Validation scope

Deterministic tests cover HTTP failures and redaction, local/cloud selection,
expired/paused observations, News ordinary-story scene outcomes, syndicated copies,
publication errors, retries/recovery, global cooldown, old-season rejection,
wrong-team fixtures, correction/recovery event suppression, and freshness expiry.
Existing Core/Control/scene, Agent, deployment and Display checks are retained.
Native OS API calls, real OAuth renewal, paid-provider entitlement and real match
latency require live validation. No Hermes deployment was performed.
