#!/bin/sh
set -u

ROOT=${OLYMPUS_ROOT:-}
SYSTEMCTL=${OLYMPUS_SYSTEMCTL:-systemctl}
CORE_URL=${OLYMPUS_CORE_URL:-http://127.0.0.1:8000}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
failures=0

pass() { echo "PASS  $*"; }
warn() { echo "WARN  $*"; }
fail() { echo "FAIL  $*"; failures=$((failures + 1)); }

check_file() {
    label=$1
    path=$2
    [ -f "$ROOT$path" ] && pass "$label: $path" || fail "$label missing: $path"
}

check_readable() {
    label=$1
    path=$2
    [ -r "$ROOT$path" ] && pass "$label readable: $path" || fail "$label unreadable: $path"
}

check_file "production config" /etc/olympus/config.toml
check_file "production secrets" /etc/olympus/secrets.env
check_file "Core database" /var/lib/olympus/core.db
check_file "Display entrypoint" /opt/olympus/current/display/index.html
check_file "release VERSION" /opt/olympus/current/VERSION
check_file "release metadata" /opt/olympus/current/RELEASE-METADATA.json
check_file "Core unit" /etc/systemd/system/olympus-core.service
check_file "kiosk unit" /etc/systemd/system/olympus-kiosk.service
check_file "backup timer" /etc/systemd/system/olympus-backup.timer
check_file "health timer" /etc/systemd/system/olympus-healthcheck.timer
check_readable "production config" /etc/olympus/config.toml
check_readable "production secrets" /etc/olympus/secrets.env

if command -v python3 >/dev/null 2>&1 \
    && [ -r "$ROOT/opt/olympus/current/RELEASE-METADATA.json" ] \
    && [ -r "$ROOT/opt/olympus/current/VERSION" ]; then
    if metadata=$(python3 "$SCRIPT_DIR/release_metadata.py" validate \
        --metadata "$ROOT/opt/olympus/current/RELEASE-METADATA.json" \
        --version-file "$ROOT/opt/olympus/current/VERSION" \
        --require-clean 2>&1); then
        version=$(printf '%s' "$metadata" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
        revision=$(printf '%s' "$metadata" | python3 -c 'import json,sys; print(json.load(sys.stdin)["revision"])')
        pass "release metadata valid"
        echo "INFO  release version: $version"
        echo "INFO  release revision: $revision"
    else
        fail "release metadata invalid: $metadata"
    fi
fi

if command -v python3 >/dev/null 2>&1 \
    && [ -r "$ROOT/etc/olympus/config.toml" ] \
    && [ -r "$ROOT/etc/olympus/secrets.env" ]; then
    if validation=$(python3 "$SCRIPT_DIR/validate-config.py" \
        --config "$ROOT/etc/olympus/config.toml" \
        --secrets "$ROOT/etc/olympus/secrets.env" 2>&1); then
        printf '%s\n' "$validation"
    else
        fail "configuration validation failed"
        printf '%s\n' "$validation"
    fi
fi

if command -v python3 >/dev/null 2>&1 && [ -r "$ROOT/var/lib/olympus/core.db" ]; then
    if python3 -c 'import sqlite3,sys; c=sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True); result=c.execute("PRAGMA quick_check").fetchone()[0]; c.close(); raise SystemExit(0 if result == "ok" else 1)' "$ROOT/var/lib/olympus/core.db"; then
        pass "SQLite quick_check"
    else
        fail "SQLite quick_check failed"
    fi
fi

if [ -z "$ROOT" ] && command -v runuser >/dev/null 2>&1 && id olympus >/dev/null 2>&1; then
    runuser -u olympus -- test -w /var/lib/olympus \
        && pass "Core state directory writable by olympus" \
        || fail "Core state directory is not writable by olympus"
elif [ -w "$ROOT/var/lib/olympus" ]; then
    pass "Core state directory writable by diagnostic user"
else
    warn "Core state directory is not writable by diagnostic user"
fi

if find "$ROOT/var/backups/olympus" -maxdepth 1 -type f -name 'core-*.db' -mtime -2 -print -quit 2>/dev/null | grep -q .; then
    pass "recent SQLite backup found (under 48 hours old)"
else
    warn "no SQLite backup newer than 48 hours"
fi

OVERRIDE_DIR="$ROOT/etc/systemd/system/olympus-kiosk.service.d"
if [ -d "$OVERRIDE_DIR" ]; then
    if grep -Rqs '^[[:space:]]*Restart[[:space:]]*=[[:space:]]*no[[:space:]]*$' "$OVERRIDE_DIR"; then
        fail "local kiosk override disables crash recovery (Restart=no)"
    fi
    if grep -Rqs 'olympus-start-kiosk-hotfix.sh' "$OVERRIDE_DIR"; then
        warn "temporary Cage launcher hotfix override is still installed"
    fi
fi

if [ -z "$ROOT" ]; then
    "$SYSTEMCTL" is-active --quiet olympus-core.service \
        && pass "olympus-core.service active" || fail "olympus-core.service inactive"
    curl --fail --silent --max-time 3 "$CORE_URL/health" >/dev/null \
        && pass "local Core /health reachable" || fail "local Core /health unavailable"
    "$SYSTEMCTL" is-enabled --quiet olympus-backup.timer \
        && pass "backup timer enabled" || warn "backup timer disabled"
    "$SYSTEMCTL" is-enabled --quiet olympus-healthcheck.timer \
        && pass "health timer enabled" || warn "health timer disabled"
    "$SYSTEMCTL" is-enabled --quiet olympus-kiosk.service \
        && pass "kiosk enabled" || warn "kiosk disabled"
    "$SYSTEMCTL" is-active --quiet olympus-kiosk.service \
        && pass "kiosk active" || warn "kiosk inactive"

    if command -v timedatectl >/dev/null 2>&1; then
        [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = true ] \
            && pass "system clock synchronized" || warn "system clock is not synchronized"
    fi
    if command -v ip >/dev/null 2>&1 && ip route show default 2>/dev/null | grep -q '^default '; then
        pass "default gateway present"
    else
        warn "default gateway not detected"
    fi
    getent hosts example.com >/dev/null 2>&1 \
        && pass "DNS resolution" || warn "DNS resolution failed"
    curl --fail --silent --head --max-time 5 https://example.com/ >/dev/null \
        && pass "Internet HTTPS reachability" || warn "Internet HTTPS reachability failed"
else
    echo "INFO  rooted filesystem inspection; live service/network/clock probes skipped"
fi

command -v cage >/dev/null 2>&1 && pass "Cage available" || warn "Cage unavailable (kiosk optional)"
if [ -x /usr/bin/brave-browser ]; then
    pass "Brave available"
else
    warn "Brave unavailable (kiosk optional)"
fi
if grep -q '^connected$' "$ROOT"/sys/class/drm/card*-*/status 2>/dev/null; then
    pass "connected DRM display present"
elif [ -e "$ROOT/dev/dri/card0" ]; then
    warn "DRM card present but no connected display reported"
else
    warn "no DRM display currently visible"
fi

AVAILABLE_KB=$(df -Pk "${ROOT:-/}" 2>/dev/null | awk 'NR == 2 {print $4}')
case "$AVAILABLE_KB" in
    ''|*[!0-9]*) warn "disk free space unavailable" ;;
    *)
        echo "INFO  disk free: $AVAILABLE_KB KiB"
        [ "$AVAILABLE_KB" -ge 524288 ] && pass "disk free space above 512 MiB" || warn "disk free space below 512 MiB"
        ;;
esac

if [ "$failures" -gt 0 ]; then
    echo "Olympus doctor found $failures required check failure(s)."
    exit 1
fi
echo "Olympus doctor found no required local deployment failures."
