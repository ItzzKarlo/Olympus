#!/bin/sh
set -eu

CORE_URL=${OLYMPUS_CORE_URL:-http://127.0.0.1:8000}
PROFILE=${OLYMPUS_KIOSK_PROFILE:-/home/olympus-display/.config/olympus-chromium}
CAGE=${CAGE_BIN:-}
BROWSER=${BROWSER_BIN:-}

if [ -z "$CAGE" ]; then
    CAGE=$(command -v cage || true)
fi
if [ -z "$BROWSER" ]; then
    BROWSER=$(command -v chromium || command -v chromium-browser || true)
fi
if [ -z "$CAGE" ] || [ -z "$BROWSER" ]; then
    echo "Olympus kiosk requires both Cage and Chromium." >&2
    exit 1
fi

if [ "${1:-}" = "--print-command" ] || [ "${OLYMPUS_KIOSK_DRY_RUN:-0}" = "1" ]; then
    printf '%s\n' "$CAGE -d -s -x -- $BROWSER --ozone-platform=wayland --kiosk --no-first-run --noerrdialogs --disable-session-crashed-bubble --disable-translate --overscroll-history-navigation=0 --user-data-dir=$PROFILE $CORE_URL/"
    exit 0
fi

monitor_connected() {
    for status in /sys/class/drm/card*-*/status; do
        [ -f "$status" ] || continue
        if grep -qx connected "$status"; then
            return 0
        fi
    done
    return 1
}

echo "Olympus kiosk waiting for an attached DRM display."
while ! monitor_connected; do
    sleep 10
done

echo "Olympus kiosk waiting for local Core at $CORE_URL/health."
until curl --fail --silent --max-time 3 "$CORE_URL/health" >/dev/null; do
    sleep 3
done

if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export XDG_RUNTIME_DIR
fi
mkdir -p "$PROFILE"

exec "$CAGE" -d -s -x -- "$BROWSER" \
    --ozone-platform=wayland \
    --kiosk \
    --no-first-run \
    --noerrdialogs \
    --disable-session-crashed-bubble \
    --disable-translate \
    --overscroll-history-navigation=0 \
    --user-data-dir="$PROFILE" \
    "$CORE_URL/"
