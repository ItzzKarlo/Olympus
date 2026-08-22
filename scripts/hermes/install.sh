#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
DEFAULT_RELEASE=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
RELEASE_DIR=$DEFAULT_RELEASE
INSTALL_CORE_PACKAGES=0
INSTALL_KIOSK_PACKAGES=0
ENABLE_KIOSK=0
NO_START=0
DRY_RUN=0

usage() {
    cat <<'EOF'
Usage: install.sh [options]
  --release-dir PATH        extracted Olympus release (default: this release)
  --install-core-packages   apt-install declared Core prerequisites
  --install-kiosk-packages  apt-install Cage, Chromium transition package, fonts, PAM
  --enable-kiosk            enable the tty1 kiosk after installing it
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
        --no-start) NO_START=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

RELEASE_DIR=$(CDPATH= cd -- "$RELEASE_DIR" && pwd)
VERSION=$(tr -d '[:space:]' < "$RELEASE_DIR/VERSION")
case "$VERSION" in
    ''|*[!0-9A-Za-z.-]*) echo "Invalid release version." >&2; exit 1 ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Olympus Hermes deployment plan"
    echo "Release: $RELEASE_DIR ($VERSION)"
    echo "Target:  /opt/olympus/releases/$VERSION"
    echo "State:   /var/lib/olympus (preserved)"
    echo "Config:  /etc/olympus (preserved)"
    echo "Backups: /var/backups/olympus (preserved; pre-update backup required)"
    echo "Core packages requested: $INSTALL_CORE_PACKAGES"
    echo "Kiosk packages requested: $INSTALL_KIOSK_PACKAGES"
    echo "Kiosk enable requested: $ENABLE_KIOSK"
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
    apt-get install --no-install-recommends cage chromium-browser fonts-noto-core fonts-noto-color-emoji libpam-systemd
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }

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
        /opt/olympus/current/core/.venv/bin/python -m olympus_core.admin backup
fi

AVAILABLE_KB=$(df -Pk /opt | awk 'NR == 2 {print $4}')
RELEASE_KB=$(du -sk "$RELEASE_DIR" | awk '{print $1}')
REQUIRED_KB=$((RELEASE_KB * 3 + 262144))
if [ "$AVAILABLE_KB" -lt "$REQUIRED_KB" ]; then
    echo "Insufficient free space for a safe side-by-side Olympus release." >&2
    exit 1
fi

TARGET=/opt/olympus/releases/$VERSION
install -d -o root -g olympus -m 0755 "$TARGET"
if [ "$RELEASE_DIR" != "$TARGET" ]; then
    cp -a "$RELEASE_DIR/." "$TARGET/"
fi
python3 -m venv "$TARGET/core/.venv"
"$TARGET/core/.venv/bin/python" -m pip install --upgrade pip
"$TARGET/core/.venv/bin/python" -m pip install -r "$TARGET/core/requirements.txt"
chown -R root:root "$TARGET"
find "$TARGET/scripts" -type f -name '*.sh' -exec chmod 0755 {} +

ln -sfn "releases/$VERSION" /opt/olympus/current.next
mv -Tf /opt/olympus/current.next /opt/olympus/current

for unit in "$TARGET"/deploy/systemd/*; do
    install -o root -g root -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
done
install -o root -g root -m 0644 "$TARGET/deploy/pam/olympus-kiosk" /etc/pam.d/olympus-kiosk
systemctl daemon-reload
systemctl enable olympus-core.service olympus-backup.timer olympus-healthcheck.timer

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
    if [ "$NO_START" -eq 0 ]; then
        systemctl restart olympus-kiosk.service
    fi
fi

echo "Olympus $VERSION installed. Existing /etc, /var/lib, and backups were preserved."
echo "No unrelated Hermes service was modified."
