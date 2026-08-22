import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

from olympus_core.config import load_core_config
from olympus_core.persistence.database import Database
from olympus_core.persistence.devices import DeviceRepository
from olympus_core.persistence.enrollment import EnrollmentRepository
from olympus_core.persistence.backup import create_backup, prune_backups


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Olympus Core administration")
    groups = parser.add_subparsers(dest="group", required=True)
    enrollment = groups.add_parser("enrollment")
    enrollment_commands = enrollment.add_subparsers(dest="command", required=True)
    create = enrollment_commands.add_parser("create")
    create.add_argument("--ttl-minutes", type=int)
    create.add_argument("--label")
    devices = groups.add_parser("devices")
    device_commands = devices.add_subparsers(dest="command", required=True)
    device_commands.add_parser("list")
    revoke = device_commands.add_parser("revoke")
    revoke.add_argument("agent_id")
    backup = groups.add_parser("backup")
    backup.add_argument("--destination", type=Path)
    backup.add_argument("--retention-days", type=int)
    return parser


def _short_time(value: datetime | None) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S") if value else "never"


def main() -> int:
    args = _parser().parse_args()
    settings = load_core_config()
    if args.group == "backup":
        destination = args.destination or settings.backup.resolved_directory
        retention = (
            args.retention_days
            if args.retention_days is not None
            else settings.backup.retention_days
        )
        try:
            created = create_backup(
                settings.persistence.resolved_database_path,
                destination,
            )
            removed = prune_backups(destination, retention)
        except (OSError, sqlite3.Error, ValueError) as error:
            print(f"Olympus backup failed: {error}", file=sys.stderr)
            return 1
        print(f"Created safe SQLite backup: {created}")
        print(f"Retention cleanup removed {len(removed)} expired backup(s).")
        return 0
    database = Database(settings.persistence.resolved_database_path)
    database.initialize()
    devices = DeviceRepository(database)
    enrollment = EnrollmentRepository(
        database, settings.security.enrollment_token_ttl_minutes
    )
    if args.group == "enrollment" and args.command == "create":
        created = enrollment.create(args.ttl_minutes, args.label)
        print("Olympus enrollment token\n")
        print(created.token)
        print(f"\nExpires: {_short_time(created.expires_at)}")
        print("Single use.")
        return 0
    if args.group == "devices" and args.command == "list":
        rows = devices.list()
        if not rows:
            print("No trusted devices.")
            return 0
        print(f"{'NAME':24} {'AGENT ID':38} {'PLATFORM':12} {'FINGERPRINT':25} {'LAST SEEN':19} STATUS")
        for device in rows:
            status = "revoked" if device.revoked else "trusted"
            print(
                f"{device.display_name[:24]:24} {device.agent_id[:38]:38} "
                f"{device.platform[:12]:12} {device.public_key_fingerprint[:25]:25} "
                f"{_short_time(device.last_seen_at):19} {status}"
            )
        return 0
    if args.group == "devices" and args.command == "revoke":
        if not devices.revoke(args.agent_id):
            print(f"No active trusted device found for {args.agent_id}.")
            return 1
        print(f"Revoked {args.agent_id}.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
