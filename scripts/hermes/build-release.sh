#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
VERSION=$(tr -d '[:space:]' < "$ROOT/VERSION")
SKIP_NODE_INSTALL=0
ALLOW_DIRTY=0
PYTHON_BIN=${PYTHON_BIN:-python3}

# Suppress macOS AppleDouble/xattr metadata. Release provenance is stored in
# RELEASE-METADATA.json; the application payload contains portable plain files.
COPYFILE_DISABLE=1
export COPYFILE_DISABLE

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-node-install) SKIP_NODE_INSTALL=1 ;;
        --allow-dirty) ALLOW_DIRTY=1 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$SKIP_NODE_INSTALL" -eq 0 ]; then
    (cd "$ROOT/display" && npm ci)
fi

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT INT TERM
RELEASE="$STAGING/olympus-$VERSION"
mkdir -p "$RELEASE/core" "$RELEASE/display" "$RELEASE/deploy" "$RELEASE/scripts"
METADATA_ARGS=
if [ "$ALLOW_DIRTY" -eq 1 ]; then
    METADATA_ARGS=--allow-dirty
fi
"$PYTHON_BIN" "$ROOT/scripts/hermes/release_metadata.py" write \
    --root "$ROOT" \
    --output "$RELEASE/RELEASE-METADATA.json" \
    $METADATA_ARGS

(cd "$ROOT/display" && VITE_OLYMPUS_KIOSK=true npm run build)

cp -R "$ROOT/core/olympus_core" "$RELEASE/core/"
cp "$ROOT/core/requirements.txt" "$RELEASE/core/"
cp -R "$ROOT/display/dist/." "$RELEASE/display/"
cp -R "$ROOT/deploy/hermes/." "$RELEASE/deploy/"
cp -R "$ROOT/scripts/hermes" "$RELEASE/scripts/"
cp "$ROOT/docs/hermes-deployment.md" "$RELEASE/README-HERMES.md"
cp "$ROOT/VERSION" "$RELEASE/VERSION"
find "$RELEASE" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$RELEASE" -type f \( -name '*.pyc' -o -name '.DS_Store' -o -name '._*' \) -delete

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
