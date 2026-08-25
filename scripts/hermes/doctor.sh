#!/bin/sh
set -u

ROOT=${OLYMPUS_ROOT:-}
SYSTEMCTL=${OLYMPUS_SYSTEMCTL:-systemctl}
CORE_URL=${OLYMPUS_CORE_URL:-http://127.0.0.1:8000}
failures=0

check_file() {
    label=$1
    path=$2
    if [ -f "$ROOT$path" ]; then
        echo "PASS  $label: $path"
    else
        echo "FAIL  $label missing: $path"
        failures=$((failures + 1))
    fi
}

check_file "production config" /etc/olympus/config.toml
check_file "Core database" /var/lib/olympus/core.db
check_file "Display entrypoint" /opt/olympus/current/display/index.html
check_file "release metadata" /opt/olympus/current/RELEASE-METADATA.json
check_file "Core unit" /etc/systemd/system/olympus-core.service
check_file "backup timer" /etc/systemd/system/olympus-backup.timer
check_file "health timer" /etc/systemd/system/olympus-healthcheck.timer

if [ -r "$ROOT/opt/olympus/current/RELEASE-METADATA.json" ]; then
    sed -n \
        -e 's/^  "version": "\([^"]*\)",\{0,1\}$/INFO  release version: \1/p' \
        -e 's/^  "revision": "\([0-9a-f]*\)",\{0,1\}$/INFO  release revision: \1/p' \
        "$ROOT/opt/olympus/current/RELEASE-METADATA.json"
fi

if [ -r "$ROOT/var/lib/olympus/core.db" ]; then
    echo "PASS  Core database readable"
else
    echo "FAIL  Core database is not readable"
    failures=$((failures + 1))
fi
if [ -z "$ROOT" ] && command -v runuser >/dev/null 2>&1 && id olympus >/dev/null 2>&1; then
    if runuser -u olympus -- test -w /var/lib/olympus; then
        echo "PASS  Core state directory writable by olympus"
    else
        echo "FAIL  Core state directory is not writable by olympus"
        failures=$((failures + 1))
    fi
elif [ -w "$ROOT/var/lib/olympus" ]; then
    echo "PASS  Core state directory writable by current diagnostic user"
else
    echo "WARN  Core state directory is not writable by current diagnostic user"
fi

if [ -z "$ROOT" ]; then
    if "$SYSTEMCTL" is-active --quiet olympus-core.service; then
        echo "PASS  olympus-core.service active"
    else
        echo "FAIL  olympus-core.service inactive"
        failures=$((failures + 1))
    fi
    if curl --fail --silent --max-time 3 "$CORE_URL/health" >/dev/null; then
        echo "PASS  local /health reachable"
    else
        echo "FAIL  local /health unavailable"
        failures=$((failures + 1))
    fi
    "$SYSTEMCTL" is-enabled --quiet olympus-backup.timer && echo "PASS  backup timer enabled" || echo "WARN  backup timer disabled"
    "$SYSTEMCTL" is-enabled --quiet olympus-healthcheck.timer && echo "PASS  health timer enabled" || echo "WARN  health timer disabled"
    "$SYSTEMCTL" is-enabled --quiet olympus-kiosk.service && echo "INFO  kiosk enabled" || echo "INFO  kiosk disabled"
else
    echo "INFO  rooted filesystem inspection; live service probes skipped"
fi

command -v cage >/dev/null 2>&1 && echo "PASS  Cage available" || echo "WARN  Cage unavailable (kiosk optional)"
if command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1; then
    echo "PASS  Chromium available"
else
    echo "WARN  Chromium unavailable (kiosk optional)"
fi
[ -e "$ROOT/dev/dri/card0" ] && echo "PASS  DRM card present" || echo "INFO  no DRM card currently visible"
df -Pk "${ROOT:-/}" | awk 'NR == 2 {print "INFO  disk free: " $4 " KiB"}'

if [ "$failures" -gt 0 ]; then
    echo "Olympus doctor found $failures required check failure(s)."
    exit 1
fi
echo "Olympus doctor found no required local deployment failures."
