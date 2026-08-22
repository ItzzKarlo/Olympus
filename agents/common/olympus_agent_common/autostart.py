from dataclasses import dataclass
import getpass
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import tempfile
from typing import Callable
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from olympus_agent_common.paths import AgentPaths


LAUNCH_AGENT_LABEL = "com.itzkarlo.olympus.agent"
WINDOWS_TASK_NAME = "Olympus Agent"
LINUX_UNIT_NAME = "olympus-agent.service"
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class AutostartStatus:
    mechanism: str
    installed: bool
    enabled: bool | None
    active: bool | None


def render_windows_task(command: list[str], user_id: str) -> str:
    executable, *arguments = command
    args = subprocess.list2cmdline(arguments)
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Olympus Agent for the interactive user session.</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{escape(user_id)}</UserId></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>{escape(user_id)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RestartOnFailure><Interval>PT30S</Interval><Count>5</Count></RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(executable)}</Command><Arguments>{escape(args)}</Arguments></Exec></Actions>
</Task>
'''


def render_launch_agent(command: list[str]) -> bytes:
    return plistlib.dumps({
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": command,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Interactive",
    }, sort_keys=True)


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_systemd_user_unit(command: list[str]) -> str:
    executable = " ".join(_systemd_quote(value) for value in command)
    return f"""[Unit]
Description=Olympus Agent
After=network-online.target

[Service]
Type=simple
ExecStart={executable}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""


def _atomic_write(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    try:
        temporary.chmod(mode)
    except OSError:
        pass
    temporary.replace(path)


class AutostartManager:
    def __init__(self, paths: AgentPaths, command: list[str], runner: Runner = subprocess.run) -> None:
        self.paths = paths
        self.command = command
        self._run = runner

    def _execute(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self._run(command, capture_output=True, text=True, check=False)

    def install(self) -> None:
        if self.paths.platform == "windows":
            user = getpass.getuser()
            domain = os.environ.get("USERDOMAIN")
            user_id = f"{domain}\\{user}" if domain else user
            xml = render_windows_task(self.command, user_id)
            with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-16", delete=False) as file:
                file.write(xml)
                temporary = Path(file.name)
            try:
                result = self._execute([
                    "schtasks", "/create", "/tn", WINDOWS_TASK_NAME,
                    "/xml", str(temporary), "/f",
                ])
            finally:
                temporary.unlink(missing_ok=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Could not create Windows Scheduled Task")
            return
        if self.paths.platform == "macos":
            _atomic_write(self.paths.autostart_path, render_launch_agent(self.command))
            domain = f"gui/{os.getuid()}"
            self._execute(["launchctl", "bootout", f"{domain}/{LAUNCH_AGENT_LABEL}"])
            result = self._execute(["launchctl", "bootstrap", domain, str(self.paths.autostart_path)])
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Could not load macOS LaunchAgent")
            self._execute(["launchctl", "kickstart", "-k", f"{domain}/{LAUNCH_AGENT_LABEL}"])
            return
        if not shutil_which("systemctl"):
            raise RuntimeError("systemd --user is required for automatic startup on this build")
        _atomic_write(
            self.paths.autostart_path,
            render_systemd_user_unit(self.command).encode("utf-8"),
        )
        reload_result = self._execute(["systemctl", "--user", "daemon-reload"])
        enable_result = self._execute([
            "systemctl", "--user", "enable", "--now", LINUX_UNIT_NAME
        ])
        if reload_result.returncode != 0 or enable_result.returncode != 0:
            raise RuntimeError(
                enable_result.stderr.strip()
                or reload_result.stderr.strip()
                or "Could not enable systemd user service"
            )

    def uninstall(self) -> None:
        if self.paths.platform == "windows":
            result = self._execute(["schtasks", "/delete", "/tn", WINDOWS_TASK_NAME, "/f"])
            if result.returncode != 0 and "cannot find" not in (result.stderr + result.stdout).lower():
                raise RuntimeError(result.stderr.strip() or "Could not remove Windows Scheduled Task")
            return
        if self.paths.platform == "macos":
            domain = f"gui/{os.getuid()}"
            self._execute(["launchctl", "bootout", f"{domain}/{LAUNCH_AGENT_LABEL}"])
            self.paths.autostart_path.unlink(missing_ok=True)
            return
        if shutil_which("systemctl"):
            self._execute(["systemctl", "--user", "disable", "--now", LINUX_UNIT_NAME])
        self.paths.autostart_path.unlink(missing_ok=True)
        if shutil_which("systemctl"):
            self._execute(["systemctl", "--user", "daemon-reload"])

    def status(self) -> AutostartStatus:
        if self.paths.platform == "windows":
            result = self._execute(["schtasks", "/query", "/tn", WINDOWS_TASK_NAME, "/xml"])
            if result.returncode != 0:
                return AutostartStatus("Scheduled Task", False, False, False)
            enabled: bool | None = None
            try:
                root = ElementTree.fromstring(result.stdout)
                node = root.find(".//{*}Settings/{*}Enabled")
                enabled = node is None or node.text == "true"
            except ElementTree.ParseError:
                pass
            return AutostartStatus("Scheduled Task", True, enabled, None)
        if self.paths.platform == "macos":
            installed = self.paths.autostart_path.exists()
            if not installed:
                return AutostartStatus("LaunchAgent", False, False, False)
            domain = f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"
            active = self._execute(["launchctl", "print", domain]).returncode == 0
            return AutostartStatus("LaunchAgent", True, True, active)
        installed = self.paths.autostart_path.exists()
        if not shutil_which("systemctl"):
            return AutostartStatus("systemd --user", installed, None, None)
        enabled = self._execute([
            "systemctl", "--user", "is-enabled", LINUX_UNIT_NAME
        ]).returncode == 0
        active = self._execute([
            "systemctl", "--user", "is-active", LINUX_UNIT_NAME
        ]).returncode == 0
        return AutostartStatus("systemd --user", installed, enabled, active)


def shutil_which(command: str) -> str | None:
    # Local wrapper keeps platform checks easy to replace in tests.
    import shutil

    return shutil.which(command)


def development_command(module: str = "olympus_agent.main") -> list[str]:
    import sys

    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve()), "run", "--background"]
    return [str(Path(sys.executable).resolve()), "-m", module, "run", "--background"]
