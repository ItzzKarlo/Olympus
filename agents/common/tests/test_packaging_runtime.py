from contextlib import redirect_stdout
import asyncio
import io
import logging
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from olympus_agent_common.autostart import (
    AutostartManager,
    render_launch_agent,
    render_systemd_user_unit,
    render_windows_task,
)
from olympus_agent_common.cli import AgentApplication, run_cli
from olympus_agent_common.config import AgentConfig, read_config_file, validate_core_url, write_config_file
from olympus_agent_common.identity import migrate_legacy_identity
from olympus_agent_common.instance import SingleInstance, is_instance_running
from olympus_agent_common.logging_config import configure_logging
from olympus_agent_common.paths import AgentPaths, agent_paths
from olympus_agent_common.runtime import run_forever


def temporary_paths(root: Path, platform: str = "linux") -> AgentPaths:
    return AgentPaths(
        platform=platform,
        config_dir=root / "config",
        data_dir=root / "data",
        log_dir=root / "data" / "logs",
        config_path=root / "config" / "agent.toml",
        identity_path=root / "data" / "agent-id",
        key_path=root / "data" / "agent-key.pem",
        lock_path=root / "data" / "agent.lock",
        autostart_path=root / "autostart" / "definition",
    )


class PathAndConfigTests(unittest.TestCase):
    def test_platform_paths_are_per_user_and_xdg_aware(self) -> None:
        home = Path("/users/test")
        linux = agent_paths("linux", home=home, environ={
            "XDG_CONFIG_HOME": "/config", "XDG_STATE_HOME": "/state",
        })
        self.assertEqual(linux.config_path, Path("/config/olympus/agent.toml"))
        self.assertEqual(linux.identity_path, Path("/state/olympus/agent-id"))
        self.assertEqual(linux.autostart_path, Path("/config/systemd/user/olympus-agent.service"))
        mac = agent_paths("macos", home=home, environ={})
        self.assertEqual(mac.config_path, home / "Library/Application Support/Olympus/agent.toml")
        windows = agent_paths("windows", home=home, environ={
            "APPDATA": "C:/Roaming", "LOCALAPPDATA": "C:/Local",
        })
        self.assertEqual(windows.config_path, Path("C:/Roaming/Olympus/agent.toml"))
        self.assertEqual(windows.key_path, Path("C:/Local/Olympus/agent-key.pem"))

    def test_config_precedence_cli_environment_file_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = temporary_paths(Path(directory))
            default_config = AgentConfig.from_sources(paths, environ={})
            self.assertEqual(default_config.core_ws_url, "ws://127.0.0.1:8000/ws/agents")
            write_config_file(paths.config_path, "ws://file:8000/ws/agents", "File Device")
            file_config = AgentConfig.from_sources(paths, environ={})
            self.assertEqual(file_config.core_ws_url, "ws://file:8000/ws/agents")
            env_config = AgentConfig.from_sources(paths, environ={
                "OLYMPUS_CORE_URL": "wss://environment/ws/agents",
                "OLYMPUS_AGENT_DISPLAY_NAME": "Environment Device",
            })
            self.assertEqual(env_config.core_ws_url, "wss://environment/ws/agents")
            cli_config = AgentConfig.from_sources(
                paths,
                core_url_override="ws://cli:9000/ws/agents",
                display_name_override="CLI Device",
                environ={"OLYMPUS_CORE_URL": "ws://environment/ws/agents"},
            )
            self.assertEqual(cli_config.core_ws_url, "ws://cli:9000/ws/agents")
            self.assertEqual(cli_config.display_name, "CLI Device")

    def test_malformed_config_and_invalid_urls_fail_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = temporary_paths(Path(directory))
            paths.config_path.parent.mkdir(parents=True)
            paths.config_path.write_text("not = [valid", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration is invalid"):
                AgentConfig.from_sources(paths, environ={})
        for value in ("http://core", "ws://user:secret@core/ws", "ws://core/ws?q=1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_core_url(value)
        with self.assertRaisesRegex(ValueError, "printable"):
            write_config_file(Path("unused.toml"), "ws://core/ws/agents", "bad\nname")

    def test_legacy_identity_is_copied_verified_and_not_destroyed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_id = root / "legacy" / "agent-id"
            legacy_key = root / "legacy" / "agent-key.pem"
            legacy_id.parent.mkdir()
            legacy_id.write_text("mac-existing\n", encoding="utf-8")
            legacy_key.write_bytes(b"existing-key")
            destination_id = root / "new" / "agent-id"
            destination_key = root / "new" / "agent-key.pem"
            self.assertEqual(
                migrate_legacy_identity(destination_id, destination_key, legacy_id, legacy_key),
                (True, True),
            )
            self.assertEqual(destination_id.read_bytes(), legacy_id.read_bytes())
            self.assertEqual(destination_key.read_bytes(), legacy_key.read_bytes())
            self.assertTrue(legacy_id.exists())
            self.assertEqual(
                migrate_legacy_identity(destination_id, destination_key, legacy_id, legacy_key),
                (False, False),
            )


class SingleInstanceTests(unittest.TestCase):
    def test_lock_releases_with_process_lifetime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.lock"
            first = SingleInstance(path)
            second = SingleInstance(path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            self.assertTrue(is_instance_running(path))
            first.release()
            first.release()
            self.assertTrue(second.acquire())
            second.release()
            second.release()
            self.assertFalse(is_instance_running(path))


class RuntimeResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_core_outage_retries_without_terminating_the_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = asyncio.Event()
            attempts = 0

            async def connection(*_: object, **__: object) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError("Core is offline")
                stop.set()

            config = AgentConfig(
                core_ws_url="ws://127.0.0.1:8000/ws/agents",
                telemetry_interval=0.01,
                reconnect_delay=0.01,
                identity_path=root / "agent-id",
                key_path=root / "agent-key.pem",
            )
            with patch("olympus_agent_common.runtime.run_connection", connection):
                await asyncio.wait_for(run_forever(
                    config,
                    "test",
                    "linux",
                    "test",
                    "1.0.0",
                    lambda: {},
                    stop=stop,
                ), timeout=1)
            self.assertEqual(attempts, 2)


class AutostartTests(unittest.TestCase):
    def test_windows_task_is_interactive_single_instance_and_restartable(self) -> None:
        xml = render_windows_task(
            ["C:/Olympus/OlympusAgent.exe", "run", "--background"], "TEST\\user"
        )
        root = ElementTree.fromstring(xml)
        self.assertEqual(root.find(".//{*}LogonType").text, "InteractiveToken")
        self.assertEqual(root.find(".//{*}MultipleInstancesPolicy").text, "IgnoreNew")
        self.assertEqual(root.find(".//{*}RestartOnFailure/{*}Interval").text, "PT30S")
        self.assertIn("--background", root.find(".//{*}Arguments").text)

    def test_launch_agent_and_systemd_unit_use_interactive_user_models(self) -> None:
        plist = plistlib.loads(render_launch_agent([
            "/Applications/Olympus Agent.app/Contents/MacOS/Olympus Agent",
            "run", "--background",
        ]))
        self.assertTrue(plist["RunAtLoad"])
        self.assertTrue(plist["KeepAlive"])
        self.assertEqual(plist["ProcessType"], "Interactive")
        unit = render_systemd_user_unit([
            "/home/test/.local/lib/olympus-agent/olympus-agent",
            "run", "--background",
        ])
        self.assertIn("WantedBy=default.target", unit)
        self.assertIn("Restart=always", unit)
        self.assertNotIn("loginctl", unit)

    def test_macos_install_and_uninstall_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = temporary_paths(Path(directory), "macos")
            calls: list[list[str]] = []

            def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            manager = AutostartManager(paths, ["/agent", "run", "--background"], runner)
            with patch("olympus_agent_common.autostart.os.getuid", return_value=501, create=True):
                manager.install()
                manager.install()
                self.assertTrue(paths.autostart_path.exists())
                manager.uninstall()
                manager.uninstall()
            self.assertFalse(paths.autostart_path.exists())
            self.assertEqual(sum(call[:2] == ["launchctl", "bootstrap"] for call in calls), 2)
            self.assertEqual(
                [call[2] for call in calls if call[:2] == ["launchctl", "bootstrap"]],
                ["gui/501", "gui/501"],
            )


class LoggingAndCliTests(unittest.TestCase):
    def tearDown(self) -> None:
        root = logging.getLogger()
        for handler in root.handlers:
            handler.close()
        root.handlers.clear()

    def test_background_log_is_rotating_and_redacts_enrollment_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = logging.getLogger()
            try:
                log_path = configure_logging(True, Path(directory))
                logging.getLogger("test").warning("token OLYMPUS-thisIsASecretToken123456")
                for handler in root.handlers:
                    handler.flush()
                content = log_path.read_text(encoding="utf-8")
                self.assertIn("[REDACTED]", content)
                self.assertNotIn("thisIsASecret", content)
                handler = root.handlers[0]
                self.assertEqual(handler.backupCount, 5)
            finally:
                for handler in root.handlers[:]:
                    root.removeHandler(handler)
                    handler.close()

    def test_foreground_logging_uses_the_console_without_a_log_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(configure_logging(False, Path(directory)))
            handler = logging.getLogger().handlers[0]
            self.assertIsInstance(handler, logging.StreamHandler)
            self.assertFalse(hasattr(handler, "backupCount"))
            self.assertFalse(Path(directory, "agent.log").exists())

    def test_headless_setup_and_version_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = temporary_paths(Path(directory))
            application = AgentApplication(
                "linux", "linux", "test", "1.0.0",
                lambda: {}, paths,
            )
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(run_cli(application, [
                    "setup", "--core-url", "wss://hermes/ws/agents",
                    "--display-name", "Main PC",
                ]), 0)
                self.assertEqual(run_cli(application, ["version"]), 0)
            parsed = read_config_file(paths.config_path)
            self.assertEqual(parsed["core"]["url"], "wss://hermes/ws/agents")
            self.assertIn("Olympus Agent 1.0.0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
