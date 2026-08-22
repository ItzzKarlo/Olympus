#!/bin/sh
set -eu

case "${1:-}" in
    enable)
        systemctl enable --now olympus-kiosk.service
        ;;
    disable)
        systemctl disable --now olympus-kiosk.service
        ;;
    status)
        systemctl status olympus-kiosk.service
        ;;
    *)
        echo "Usage: kiosk-control.sh enable|disable|status" >&2
        exit 2
        ;;
esac
