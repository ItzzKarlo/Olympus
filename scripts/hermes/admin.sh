#!/bin/sh
set -eu

CORE_DIR=/opt/olympus/current/core
OLYMPUS_CONFIG=${OLYMPUS_CONFIG:-/etc/olympus/config.toml}
export OLYMPUS_CONFIG

if [ "${1:-}" = "--core-dir" ]; then
    if [ "$#" -lt 3 ]; then
        echo "Usage: admin.sh [--core-dir PATH] <backup|enrollment|devices> [arguments...]" >&2
        exit 2
    fi
    CORE_DIR=$2
    shift 2
fi
if [ "$#" -eq 0 ]; then
    echo "Usage: admin.sh [--core-dir PATH] <backup|enrollment|devices> [arguments...]" >&2
    exit 2
fi
if [ ! -d "$CORE_DIR/olympus_core" ]; then
    echo "Olympus Core source is not available at $CORE_DIR." >&2
    exit 1
fi
if [ ! -x "$CORE_DIR/.venv/bin/python" ]; then
    echo "Olympus Core Python is not available at $CORE_DIR/.venv/bin/python." >&2
    exit 1
fi

cd "$CORE_DIR"
exec "$CORE_DIR/.venv/bin/python" -m olympus_core.admin "$@"
