#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
DEFAULT_RELEASE=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
RELEASE_DIR=$DEFAULT_RELEASE
INSTALL_CORE_PACKAGES=0
INSTALL_KIOSK_PACKAGES=0
ENABLE_KIOSK=0
RESTART_KIOSK=0
NO_START=0
DRY_RUN=0
PARTIAL_TARGET=
BRAVE_KEY_TEMP=
BRAVE_SOURCE_TEMP=

cleanup_partial_release() {
    if [ -n "$PARTIAL_TARGET" ] && [ -d "$PARTIAL_TARGET" ]; then
        rm -rf -- "$PARTIAL_TARGET"
    fi
    [ -z "$BRAVE_KEY_TEMP" ] || rm -f -- "$BRAVE_KEY_TEMP"
    [ -z "$BRAVE_SOURCE_TEMP" ] || rm -f -- "$BRAVE_SOURCE_TEMP"
}
trap cleanup_partial_release EXIT
trap 'exit 130' INT TERM

usage() {
    cat <<'EOF'
Usage: install.sh [options]
  --release-dir PATH        extracted Olympus release (default: this release)
  --install-core-packages   apt-install declared Core prerequisites
  --install-kiosk-packages  apt-install Cage, native Brave, fonts, and PAM
  --enable-kiosk            enable the tty1 kiosk after installing it
  --restart-kiosk           intentionally restart the installed kiosk
  --no-start                install files and units without starting Olympus
  --dry-run                 print the resolved plan without changing the host
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --release-dir) RELEASE_DIR=$2; shift 2 ;;
        --install-core-packages) INSTALL_CORE_PACKAGES=1; shift ;;
        --install-kiosk-packages) INSTALL_KIOSK_PACKAGES=1; shift ;;
        --enable-kiosk) ENABLE_KIOSK=1; shift ;;
        --restart-kiosk) RESTART_KIOSK=1; shift ;;
        --no-start) NO_START=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ "$RESTART_KIOSK" -eq 1 ] && [ "$NO_START" -eq 1 ]; then
    echo "--restart-kiosk and --no-start cannot be used together." >&2
    exit 2
fi

RELEASE_DIR=$(CDPATH= cd -- "$RELEASE_DIR" && pwd)
VERSION=$(tr -d '[:space:]' < "$RELEASE_DIR/VERSION")
case "$VERSION" in
    ''|*[!0-9A-Za-z.-]*) echo "Invalid release version." >&2; exit 1 ;;
esac
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
METADATA=$RELEASE_DIR/RELEASE-METADATA.json
METADATA_JSON=$(python3 "$RELEASE_DIR/scripts/hermes/release_metadata.py" validate \
    --metadata "$METADATA" \
    --version-file "$RELEASE_DIR/VERSION" \
    --require-clean)
REVISION=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["revision"])' "$METADATA_JSON")
TARGET=/opt/olympus/releases/$VERSION
TARGET_EXISTS=0
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
    if [ -L "$TARGET" ] || [ ! -d "$TARGET" ]; then
        echo "Existing release target is not an immutable release directory: $TARGET" >&2
        exit 1
    fi
    if ! EXISTING_METADATA_JSON=$(python3 "$RELEASE_DIR/scripts/hermes/release_metadata.py" validate \
        --metadata "$TARGET/RELEASE-METADATA.json" \
        --version-file "$TARGET/VERSION" \
        --require-clean); then
        echo "Existing release $TARGET has invalid provenance; refusing to modify it." >&2
        exit 1
    fi
    if [ "$EXISTING_METADATA_JSON" != "$METADATA_JSON" ]; then
        echo "Release $VERSION already exists with different provenance; refusing to overwrite it." >&2
        exit 1
    fi
    TARGET_EXISTS=1
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Olympus Hermes deployment plan"
    echo "Release: $RELEASE_DIR ($VERSION)"
    echo "Revision: $REVISION"
    echo "Target:  /opt/olympus/releases/$VERSION"
    echo "State:   /var/lib/olympus (preserved)"
    echo "Config:  /etc/olympus (preserved)"
    echo "Backups: /var/backups/olympus (preserved; pre-update backup required)"
    echo "Core packages requested: $INSTALL_CORE_PACKAGES"
    echo "Kiosk packages requested: $INSTALL_KIOSK_PACKAGES"
    echo "Kiosk enable requested: $ENABLE_KIOSK"
    echo "Kiosk restart requested: $RESTART_KIOSK"
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Run the Hermes installer as root." >&2
    exit 1
fi

if [ "$INSTALL_CORE_PACKAGES" -eq 1 ] || [ "$INSTALL_KIOSK_PACKAGES" -eq 1 ]; then
    apt-get update
fi
if [ "$INSTALL_CORE_PACKAGES" -eq 1 ]; then
    apt-get install --no-install-recommends python3 python3-venv python3-pip curl ca-certificates
fi
if [ "$INSTALL_KIOSK_PACKAGES" -eq 1 ]; then
    ARCHITECTURE=$(dpkg --print-architecture)
    case "$ARCHITECTURE" in
        arm64|amd64) ;;
        *) echo "Brave kiosk packages require an arm64 or amd64 host (found $ARCHITECTURE)." >&2; exit 1 ;;
    esac

    apt-get install --no-install-recommends curl ca-certificates
    BRAVE_KEYRING=/usr/share/keyrings/brave-browser-archive-keyring.gpg
    BRAVE_SOURCE=/etc/apt/sources.list.d/brave-browser-release.sources
    BRAVE_KEY_TEMP=$(mktemp)
    BRAVE_SOURCE_TEMP=$(mktemp)
    curl --fail --silent --show-error --location \
        --output "$BRAVE_KEY_TEMP" \
        https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
    curl --fail --silent --show-error --location \
        --output "$BRAVE_SOURCE_TEMP" \
        https://brave-browser-apt-release.s3.brave.com/brave-browser.sources
    [ -s "$BRAVE_KEY_TEMP" ] || { echo "Downloaded Brave signing key is empty." >&2; exit 1; }
    [ -s "$BRAVE_SOURCE_TEMP" ] || { echo "Downloaded Brave apt source is empty." >&2; exit 1; }
    install -d -o root -g root -m 0755 /usr/share/keyrings /etc/apt/sources.list.d
    if ! cmp -s "$BRAVE_KEY_TEMP" "$BRAVE_KEYRING"; then
        install -o root -g root -m 0644 "$BRAVE_KEY_TEMP" "$BRAVE_KEYRING"
    fi
    if ! cmp -s "$BRAVE_SOURCE_TEMP" "$BRAVE_SOURCE"; then
        install -o root -g root -m 0644 "$BRAVE_SOURCE_TEMP" "$BRAVE_SOURCE"
    fi
    rm -f -- "$BRAVE_KEY_TEMP" "$BRAVE_SOURCE_TEMP"
    BRAVE_KEY_TEMP=
    BRAVE_SOURCE_TEMP=
    apt-get update
    apt-get install --no-install-recommends cage brave-browser fonts-noto-core fonts-noto-color-emoji libpam-systemd
    [ -x /usr/bin/brave-browser ] || { echo "Brave installation did not provide /usr/bin/brave-browser." >&2; exit 1; }
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
if [ "$ENABLE_KIOSK" -eq 1 ] || [ "$RESTART_KIOSK" -eq 1 ]; then
    command -v cage >/dev/null 2>&1 || { echo "Cage is required before managing kiosk." >&2; exit 1; }
    [ -x /usr/bin/brave-browser ] || { echo "/usr/bin/brave-browser is required before managing kiosk." >&2; exit 1; }
fi

if ! id olympus >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/olympus --shell /usr/sbin/nologin olympus
fi
if ! id olympus-display >/dev/null 2>&1; then
    useradd --create-home --home-dir /home/olympus-display --shell /bin/bash olympus-display
    passwd --lock olympus-display >/dev/null
fi
KIOSK_GROUPS=
for group in video render; do
    if getent group "$group" >/dev/null; then
        KIOSK_GROUPS="${KIOSK_GROUPS}${KIOSK_GROUPS:+,}$group"
    fi
done
if [ -n "$KIOSK_GROUPS" ]; then
    usermod -a -G "$KIOSK_GROUPS" olympus-display
fi

install -d -o root -g root -m 0755 /opt/olympus/releases
install -d -o root -g olympus -m 0750 /etc/olympus
install -d -o olympus -g olympus -m 0700 /var/lib/olympus
install -d -o olympus -g olympus -m 0700 /var/backups/olympus
install -d -o olympus-display -g olympus-display -m 0700 /home/olympus-display/.config

if [ ! -f /etc/olympus/config.toml ]; then
    install -o root -g olympus -m 0640 "$RELEASE_DIR/deploy/config.toml" /etc/olympus/config.toml
fi
if [ ! -f /etc/olympus/secrets.env ]; then
    install -o root -g olympus -m 0640 "$RELEASE_DIR/deploy/secrets.env.example" /etc/olympus/secrets.env
fi
if [ ! -f /etc/olympus/kiosk.env ]; then
    install -o root -g olympus-display -m 0640 "$RELEASE_DIR/deploy/kiosk.env.example" /etc/olympus/kiosk.env
fi

# A live-WAL-safe backup is mandatory before replacing an existing release.
if [ -f /var/lib/olympus/core.db ] && [ -x /opt/olympus/current/core/.venv/bin/python ]; then
    echo "Creating pre-update SQLite backup."
    OLYMPUS_CONFIG=/etc/olympus/config.toml \
        "$RELEASE_DIR/scripts/hermes/admin.sh" \
        --core-dir /opt/olympus/current/core backup
fi

if [ "$TARGET_EXISTS" -eq 0 ]; then
    AVAILABLE_KB=$(df -Pk /opt | awk 'NR == 2 {print $4}')
    RELEASE_KB=$(du -sk "$RELEASE_DIR" | awk '{print $1}')
    REQUIRED_KB=$((RELEASE_KB * 3 + 262144))
    if [ "$AVAILABLE_KB" -lt "$REQUIRED_KB" ]; then
        echo "Insufficient free space for a safe side-by-side Olympus release." >&2
        exit 1
    fi

    PARTIAL_TARGET="${TARGET}.installing.$$"
    if [ -e "$PARTIAL_TARGET" ] || [ -L "$PARTIAL_TARGET" ]; then
        echo "Partial release staging path already exists: $PARTIAL_TARGET" >&2
        exit 1
    fi
    install -d -o root -g olympus -m 0755 "$PARTIAL_TARGET"
    cp -a "$RELEASE_DIR/." "$PARTIAL_TARGET/"
    python3 -m venv "$PARTIAL_TARGET/core/.venv"
    "$PARTIAL_TARGET/core/.venv/bin/python" -m pip install -r "$PARTIAL_TARGET/core/requirements.txt"
    chown -R root:root "$PARTIAL_TARGET"
    find "$PARTIAL_TARGET/scripts" -type f -name '*.sh' -exec chmod 0755 {} +
    if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
        echo "Release target appeared during installation; refusing to replace it: $TARGET" >&2
        exit 1
    fi
    mv "$PARTIAL_TARGET" "$TARGET"
    PARTIAL_TARGET=
else
    echo "Release $VERSION already exists with identical provenance; reusing it unchanged."
fi

for unit in "$TARGET"/deploy/systemd/*; do
    install -o root -g root -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
done
install -o root -g root -m 0644 "$TARGET/deploy/pam/olympus-kiosk" /etc/pam.d/olympus-kiosk
systemctl daemon-reload
systemctl enable olympus-core.service olympus-backup.timer olympus-healthcheck.timer

ln -sfn "releases/$VERSION" /opt/olympus/current.next
mv -Tf /opt/olympus/current.next /opt/olympus/current

if [ "$NO_START" -eq 0 ]; then
    systemctl restart olympus-core.service
    systemctl restart olympus-backup.timer olympus-healthcheck.timer
    attempts=0
    until curl --fail --silent --max-time 3 http://127.0.0.1:8000/health >/dev/null; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 20 ]; then
            echo "Olympus Core did not become healthy; inspect journalctl -u olympus-core." >&2
            exit 1
        fi
        sleep 3
    done
fi
if [ "$ENABLE_KIOSK" -eq 1 ]; then
    systemctl enable olympus-kiosk.service
fi
if [ "$NO_START" -eq 0 ]; then
    if [ "$RESTART_KIOSK" -eq 1 ]; then
        systemctl restart olympus-kiosk.service
    elif [ "$ENABLE_KIOSK" -eq 1 ] && ! systemctl is-active --quiet olympus-kiosk.service; then
        systemctl start olympus-kiosk.service
    fi
fi

echo "Olympus $VERSION installed. Existing /etc, /var/lib, and backups were preserved."
echo "No unrelated Hermes service was modified."
