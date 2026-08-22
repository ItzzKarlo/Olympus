#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
VERSION=$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$ROOT/agents/common/olympus_agent_common/__init__.py")
if [ -z "$VERSION" ]; then
    echo "Could not determine Olympus version." >&2
    exit 1
fi

if [ "${1:-}" != "--skip-node-install" ]; then
    (cd "$ROOT/display" && npm ci)
fi
(cd "$ROOT/display" && VITE_OLYMPUS_KIOSK=true npm run build)

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT INT TERM
RELEASE="$STAGING/olympus-$VERSION"
mkdir -p "$RELEASE/core" "$RELEASE/display" "$RELEASE/deploy" "$RELEASE/scripts"
cp -R "$ROOT/core/olympus_core" "$RELEASE/core/"
cp "$ROOT/core/requirements.txt" "$RELEASE/core/"
cp -R "$ROOT/display/dist/." "$RELEASE/display/"
cp -R "$ROOT/deploy/hermes/." "$RELEASE/deploy/"
cp -R "$ROOT/scripts/hermes" "$RELEASE/scripts/"
printf '%s\n' "$VERSION" > "$RELEASE/VERSION"
find "$RELEASE" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$RELEASE" -type f \( -name '*.pyc' -o -name '.DS_Store' \) -delete

OUTPUT="$ROOT/dist/hermes"
mkdir -p "$OUTPUT"
ARCHIVE="$OUTPUT/olympus-$VERSION-hermes-arm64.tar.gz"
tar -C "$STAGING" -czf "$ARCHIVE" "olympus-$VERSION"
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$OUTPUT" && sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256")
else
    (cd "$OUTPUT" && shasum -a 256 "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256")
fi
echo "Built $ARCHIVE"
echo "Checksum $ARCHIVE.sha256"
