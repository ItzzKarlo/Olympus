#!/bin/sh
set -eu

CORE_URL=${OLYMPUS_CORE_URL:-http://127.0.0.1:8000}
PROFILE=${OLYMPUS_KIOSK_PROFILE:-/home/olympus-display/.config/olympus-brave}
DRM_ROOT=${OLYMPUS_DRM_ROOT:-/sys/class/drm}
WAIT_SECONDS=${OLYMPUS_KIOSK_WAIT_SECONDS:-3}
MONITOR_WAIT_SECONDS=${OLYMPUS_KIOSK_MONITOR_WAIT_SECONDS:-10}
MAX_WAIT_ATTEMPTS=${OLYMPUS_KIOSK_MAX_WAIT_ATTEMPTS:-0}
CURL=${CURL_BIN:-curl}
CAGE=${CAGE_BIN:-}
BROWSER=${BROWSER_BIN:-/usr/bin/brave-browser}
PROC_ROOT=${OLYMPUS_PROC_ROOT:-/proc}

if [ -z "$CAGE" ]; then
    CAGE=$(command -v cage || true)
fi
if [ -z "$CAGE" ] || [ -z "$BROWSER" ]; then
    echo "Olympus kiosk requires both Cage and a browser." >&2
    exit 1
fi

monitor_connected() {
    for status in "$DRM_ROOT"/card*-*/status; do
        [ -f "$status" ] || continue
        if grep -qx connected "$status"; then
            return 0
        fi
    done
    return 1
}

profile_in_use() {
    for cmdline in "$PROC_ROOT"/[0-9]*/cmdline; do
        [ -r "$cmdline" ] || continue
        if tr '\000' '\n' < "$cmdline" | grep -Fqx -- "--user-data-dir=$PROFILE"; then
            pid=${cmdline%/cmdline}
            pid=${pid##*/}
            echo "Olympus kiosk profile is already used by live process $pid: $PROFILE" >&2
            return 0
        fi
    done
    return 1
}

clear_stale_singletons() {
    if profile_in_use; then
        echo "Refusing to remove browser singleton markers from an active profile." >&2
        return 1
    fi
    rm -f -- \
        "$PROFILE/SingletonLock" \
        "$PROFILE/SingletonCookie" \
        "$PROFILE/SingletonSocket"
}

if [ "${1:-}" = "--print-command" ] || [ "${OLYMPUS_KIOSK_DRY_RUN:-0}" = "1" ]; then
    printf '%s\n' "$CAGE -d -s -- $BROWSER --ozone-platform=wayland --kiosk --no-first-run --noerrdialogs --disable-session-crashed-bubble --disable-translate --overscroll-history-navigation=0 --user-data-dir=$PROFILE $CORE_URL/"
    exit 0
fi
if [ "${1:-}" = "--check-monitor" ]; then
    monitor_connected
    exit $?
fi

echo "Olympus kiosk waiting for an attached DRM display."
while ! monitor_connected; do
    sleep "$MONITOR_WAIT_SECONDS"
done

echo "Olympus kiosk waiting for local Core at $CORE_URL/health."
attempts=0
until "$CURL" --fail --silent --max-time 3 "$CORE_URL/health" >/dev/null; do
    attempts=$((attempts + 1))
    if [ "$MAX_WAIT_ATTEMPTS" -gt 0 ] && [ "$attempts" -ge "$MAX_WAIT_ATTEMPTS" ]; then
        echo "Olympus kiosk Core wait limit reached." >&2
        exit 75
    fi
    sleep "$WAIT_SECONDS"
done

if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export XDG_RUNTIME_DIR
fi
mkdir -p "$PROFILE"
clear_stale_singletons

exec "$CAGE" -d -s -- "$BROWSER" \
    --ozone-platform=wayland \
    --kiosk \
    --no-first-run \
    --noerrdialogs \
    --disable-session-crashed-bubble \
    --disable-translate \
    --overscroll-history-navigation=0 \
    --user-data-dir="$PROFILE" \
    "$CORE_URL/"
