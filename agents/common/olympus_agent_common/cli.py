import argparse
import asyncio
from dataclasses import dataclass
import getpass
import os
from pathlib import Path
import sys
from typing import Callable
from urllib.parse import urlsplit

from olympus_agent_common.autostart import AutostartManager, development_command
from olympus_agent_common.config import AgentConfig, DEFAULT_CORE_WS, write_config_file
from olympus_agent_common.identity import (
    migrate_legacy_identity,
    read_agent_id,
    read_device_fingerprint,
)
from olympus_agent_common.instance import SingleInstance, is_instance_running
from olympus_agent_common.logging_config import configure_logging
from olympus_agent_common.paths import AgentPaths
from olympus_agent_common.runtime import TelemetryCollector, enroll_once, run_agent


@dataclass(frozen=True, slots=True)
class AgentApplication:
    identity_prefix: str
    platform_name: str
    platform_version: str
    version: str
    collect_telemetry: TelemetryCollector
    paths: AgentPaths
    module_name: str = "olympus_agent.main"
    configure: Callable[[AgentConfig], None] | None = None


def _parser(version: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="olympus-agent")
    parser.add_argument("--version", action="version", version=f"Olympus Agent {version}")
    commands = parser.add_subparsers(dest="command")

    run = commands.add_parser("run", help="Run the Agent")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--foreground", action="store_true")
    mode.add_argument("--background", action="store_true")
    run.add_argument("--core-url")
    run.add_argument("--display-name")

    setup = commands.add_parser("setup", help="Configure Core and device name")
    setup.add_argument("--core-url")
    setup.add_argument("--display-name")

    enroll = commands.add_parser("enroll", help="Enroll this device with Core")
    enroll.add_argument("--core-url")
    enroll.add_argument("--display-name")

    commands.add_parser("status", help="Inspect local Agent state")
    commands.add_parser("install-autostart", help="Start Agent with this user session")
    commands.add_parser("uninstall-autostart", help="Remove Agent user-session startup")
    commands.add_parser("version", help="Show Agent version")
    return parser


def _migrate(application: AgentApplication) -> None:
    paths = application.paths
    migrate_legacy_identity(
        paths.identity_path,
        paths.key_path,
        paths.legacy_identity_path,
        paths.legacy_key_path,
    )


def _config(
    application: AgentApplication,
    core_url: str | None = None,
    display_name: str | None = None,
) -> AgentConfig:
    return AgentConfig.from_sources(
        application.paths,
        core_url_override=core_url,
        display_name_override=display_name,
    )


def _setup(application: AgentApplication, args: argparse.Namespace) -> int:
    existing = _config(application)
    core_url = args.core_url
    display_name = args.display_name
    if core_url is None:
        response = input(f"Olympus Core WebSocket URL [{existing.core_ws_url}]: ").strip()
        core_url = response or existing.core_ws_url
    if display_name is None:
        response = input(f"Display name [{existing.display_name}]: ").strip()
        display_name = response or existing.display_name
    write_config_file(application.paths.config_path, core_url, display_name)
    print(f"Olympus Agent configuration saved to {application.paths.config_path}")
    return 0


def _enroll(application: AgentApplication, args: argparse.Namespace) -> int:
    config = _config(application, args.core_url, args.display_name)
    token = os.environ.get("OLYMPUS_ENROLLMENT_TOKEN")
    if not token:
        token = getpass.getpass("Enrollment token: ").strip()
    if not token:
        raise ValueError("Enrollment token is required")
    try:
        agent_id, fingerprint = asyncio.run(enroll_once(
            config,
            application.identity_prefix,
            application.platform_name,
            application.platform_version,
            application.version,
            token,
        ))
    finally:
        os.environ.pop("OLYMPUS_ENROLLMENT_TOKEN", None)
        token = ""
    print("Olympus Agent enrolled successfully.\n")
    print(f"Device:      {config.display_name}")
    print(f"Core:        {urlsplit(config.core_ws_url).hostname}")
    print(f"Agent ID:    {agent_id}")
    print(f"Fingerprint: {fingerprint}")
    print("\nFuture connections authenticate automatically.")
    return 0


def _status(application: AgentApplication) -> int:
    paths = application.paths
    config = _config(application)
    manager = AutostartManager(paths, development_command(application.module_name))
    autostart = manager.status()
    identity = read_agent_id(config.identity_path)
    key_path = config.key_path or paths.key_path
    fingerprint = read_device_fingerprint(key_path)
    print(f"Olympus Agent {application.version}\n")
    print("Configuration")
    print(f"Core        {config.core_ws_url}")
    print(f"Device      {config.display_name}")
    print(f"Config      {paths.config_path}")
    print(f"Agent ID    {identity or 'missing'}")
    print(f"Identity    {'present' if identity and fingerprint else 'missing'}")
    if fingerprint:
        print(f"Fingerprint {fingerprint}")
    print("\nAutostart")
    print(f"Installed   {'yes' if autostart.installed else 'no'}")
    print(f"Platform    {autostart.mechanism}")
    print(f"Enabled     {_fact(autostart.enabled)}")
    print(f"Active      {_fact(autostart.active)}")
    print("\nRuntime")
    print(f"Running     {'yes' if is_instance_running(paths.lock_path) else 'no'}")
    return 0


def _fact(value: bool | None) -> str:
    return "unknown" if value is None else "yes" if value else "no"


def _hide_windows_console() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        window = ctypes.windll.kernel32.GetConsoleWindow()
        if window:
            ctypes.windll.user32.ShowWindow(window, 0)
    except Exception:
        pass


def _run(application: AgentApplication, args: argparse.Namespace) -> int:
    background = bool(args.background)
    if background:
        _hide_windows_console()
    configure_logging(background, application.paths.log_dir)
    lock = SingleInstance(application.paths.lock_path)
    if not lock.acquire():
        print("Olympus Agent is already running.")
        return 0
    try:
        config = _config(application, args.core_url, args.display_name)
        if application.configure is not None:
            application.configure(config)
        import logging

        logging.getLogger("olympus-agent").info(
            "Olympus Agent %s starting as %s", application.version, config.display_name
        )
        run_agent(
            config,
            application.identity_prefix,
            application.platform_name,
            application.platform_version,
            application.version,
            application.collect_telemetry,
        )
    finally:
        lock.release()
    return 0


def run_cli(application: AgentApplication, argv: list[str] | None = None) -> int:
    parser = _parser(application.version)
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments = ["run", "--foreground"]
    args = parser.parse_args(arguments)
    try:
        _migrate(application)
        if args.command == "setup":
            return _setup(application, args)
        if args.command == "enroll":
            return _enroll(application, args)
        if args.command == "status":
            return _status(application)
        if args.command == "install-autostart":
            AutostartManager(
                application.paths, development_command(application.module_name)
            ).install()
            print("Olympus Agent autostart installed for the current user.")
            return 0
        if args.command == "uninstall-autostart":
            AutostartManager(
                application.paths, development_command(application.module_name)
            ).uninstall()
            print("Olympus Agent autostart removed. Identity and configuration were preserved.")
            return 0
        if args.command == "version":
            print(f"Olympus Agent {application.version}")
            return 0
        return _run(application, args)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Olympus Agent: {error}", file=sys.stderr)
        return 2
