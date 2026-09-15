# Display world (1.0.8)

## Composition

Idle uses equal reserved wings around a 2.2fr center. Calendar context occupies
its left wing; the next match occupies its right wing. Neither wing controls
clock/weather alignment. News and agendas have explicit full-width rows below.
Below 1000px the center goes above the wings; below 600px the wings stack.
Incident overlays remain independent of this grid, above the scene.

`AmbientWorld.tsx` supplies a bounded SVG garden: distant terrain, a house, paths,
fence, layered trees, shrubs, bench, smoke, pedestrian, birds and a squirrel.
The existing `SeasonalEnvironment` supplies snow, leaves, flowers, festive lights,
Halloween props and fireworks. World colors come from `world.css`; no image or
font downloads, animation libraries, WebGL or JS frame loop are required.

Environment intensity is resolved in one `data-intensity` attribute:

- full: Idle
- calm: Night / night policy
- reduced: Development and Media
- minimal: Gaming, Matchday and News
- retreat: any active incident (highest priority)

Focused modes pause decorative animations and omit moving weather/actors using
CSS. Reduced motion stops all world animations while retaining scenery and a
stationary pedestrian. The world sits at z-index 1, scene at 2, seasonal label at
3, health at 7 and incident overlays at 10. The central veil is a static gradient,
not a full-screen blur. The old decorative canvas and emoji field are no longer
mounted during active scenes. Startup retains its existing particle treatment.

The SVG summit mark uses `--logo-primary` and `--logo-secondary`, derived from
the resolved text/accent palette. Dark seasonal events now explicitly supply
light text and a matching panel surface. The standalone `assets/logo.svg` uses
color-scheme contrast. Typography uses local Avenir Next / Segoe UI / Helvetica
Neue / DejaVu Sans fallbacks and a consistent monospace metadata stack. The
Core status label is the infrastructure role name Hermes; hostname data is intact.

## Preview without Core

```sh
cd ~/dev/Olympus
npm --prefix display ci
npm --prefix display run dev -- --host 127.0.0.1
```

Open any of these URLs (or use the commands from a second terminal):

```sh
brave 'http://127.0.0.1:5173/?preview=idle&seasonal_date=2026-12-31'
brave 'http://127.0.0.1:5173/?preview=idle&seasonal_date=2026-11-11'
brave 'http://127.0.0.1:5173/?preview=idle&seasonal_date=2026-12-24'
brave 'http://127.0.0.1:5173/?preview=idle&seasonal_date=2026-12-01'
brave 'http://127.0.0.1:5173/?preview=idle&seasonal_date=2026-07-15'
brave 'http://127.0.0.1:5173/?preview=idle&seasonal_date=2026-04-15'
```

Add `&panels=left`, `right`, `both` or `none`; add `&alert=critical` for an
incident. Use `preview=night` for Night. Halloween: 2026-10-31; Easter: 2026-04-05.
This fixture is development-only and Vite removes it from production builds.
Without `preview`, configure `VITE_OLYMPUS_CORE_WS` to the Core websocket when
using Vite directly. Production `seasonal_date` and the launcher's existing
`OLYMPUS_SEASONAL_DATE` remain supported; neither changes the real clock/date.

## Browser regression checks

With the development server running, optional Playwright can live outside the
repo. It is not a Display dependency:

```sh
npm install --prefix /tmp/olympus-browser playwright --no-audit --no-fund
NODE_PATH=/tmp/olympus-browser/node_modules BROWSER_PATH=/usr/bin/brave \
  node display/tests/world.cjs
```

The suite checks clock alignment for four panel combinations at five sizes,
horizontal overflow, eight seasonal dates, clock independence, a <300-node
world budget, critical layering and reduced motion. Set `SCREENSHOT_DIR` to an
existing directory to save the seasonal renders.

## Wall follow-up

Review font fallback on Hermes, physical viewing distance, display brightness,
actor scale and the density of real news/calendar data. Browser measurements
are not a Pi GPU/frame-time or 24-hour thermal soak test. Actor timings are
intentionally sparse (pedestrian 173s, plane 241s, squirrel 79s). The design
uses a shared neighborhood rather than separate bespoke artwork per holiday.
