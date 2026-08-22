#!/usr/bin/env python3
import argparse
import hashlib
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
ENTRYPOINT = AGENTS / "packaging" / "entrypoint.py"
ASSETS = AGENTS / "packaging" / "assets"


def target_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"Unsupported packaging platform: {sys.platform}")


def architecture() -> str:
    value = platform.machine().casefold()
    return {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(value, value.replace(" ", "-"))


def version() -> str:
    source = (AGENTS / "common" / "olympus_agent_common" / "__init__.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'__version__\s*=\s*"([^"]+)"', source)
    if not match:
        raise RuntimeError("Could not determine Olympus Agent version")
    return match.group(1)


def windows_version_file(path: Path, release: str) -> None:
    parts = tuple(int(value) for value in release.split(".")) + (0,)
    major, minor, patch, build = parts[:4]
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({major}, {minor}, {patch}, {build}), prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Olympus'),
    StringStruct('FileDescription', 'Olympus Agent'),
    StringStruct('FileVersion', '{release}'),
    StringStruct('InternalName', 'OlympusAgent'),
    StringStruct('OriginalFilename', 'OlympusAgent.exe'),
    StringStruct('ProductName', 'Olympus Agent'),
    StringStruct('ProductVersion', '{release}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding="utf-8")


def build() -> Path:
    system = target_platform()
    release = version()
    name = "Olympus Agent" if system == "macos" else "OlympusAgent" if system == "windows" else "olympus-agent"
    dist_path = ROOT / "dist" / system
    work_path = ROOT / "build" / "agent" / system
    spec_path = ROOT / "build" / "agent" / "spec"
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir",
        "--name", name,
        "--distpath", str(dist_path),
        "--workpath", str(work_path),
        "--specpath", str(spec_path),
        "--paths", str(AGENTS / "common"),
        "--paths", str(AGENTS / system),
        "--hidden-import", "olympus_agent.main",
        "--hidden-import", "olympus_agent_common.cli",
        "--hidden-import", "websockets.asyncio.client",
    ]
    if system == "windows":
        version_file = work_path / "olympus-agent-version.txt"
        version_file.parent.mkdir(parents=True, exist_ok=True)
        windows_version_file(version_file, release)
        command.extend([
            "--hidden-import", "pynvml",
            "--version-file", str(version_file),
            "--icon", str(ASSETS / "olympus-agent.ico"),
        ])
    elif system == "macos":
        command.extend([
            "--windowed",
            "--osx-bundle-identifier", "com.itzkarlo.olympus.agent",
            "--target-arch", architecture(),
            "--icon", str(ASSETS / "olympus-agent.icns"),
        ])
    command.append(str(ENTRYPOINT))
    environment = {
        **os.environ,
        "PYINSTALLER_CONFIG_DIR": str(work_path / "cache"),
    }
    subprocess.run(command, cwd=ROOT, env=environment, check=True)

    artifact = dist_path / (f"{name}.app" if system == "macos" else name)
    if system == "macos":
        plist_path = artifact / "Contents" / "Info.plist"
        with plist_path.open("rb") as file:
            info = plistlib.load(file)
        info.update({
            "CFBundleDisplayName": "Olympus Agent",
            "CFBundleName": "Olympus Agent",
            "CFBundleShortVersionString": release,
            "CFBundleVersion": release,
            "LSBackgroundOnly": True,
        })
        with plist_path.open("wb") as file:
            plistlib.dump(info, file, sort_keys=True)
    return artifact


def executable_for(artifact: Path) -> Path:
    system = target_platform()
    if system == "macos":
        return artifact / "Contents" / "MacOS" / "Olympus Agent"
    return artifact / ("OlympusAgent.exe" if system == "windows" else "olympus-agent")


def smoke_test(artifact: Path) -> None:
    executable = executable_for(artifact)
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory)
        environment = {
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(home / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(home / "AppData" / "Local"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
        }
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            environment["OLYMPUS_INTEGRATION_PORT"] = str(listener.getsockname()[1])
        version_result = subprocess.run(
            [str(executable), "--version"], env=environment,
            capture_output=True, text=True, check=True,
        )
        if version() not in version_result.stdout:
            raise RuntimeError("Frozen Agent reported the wrong version")
        subprocess.run([
            str(executable), "setup",
            "--core-url", "ws://127.0.0.1:9/ws/agents",
            "--display-name", "Frozen smoke test",
        ], env=environment, capture_output=True, text=True, check=True)
        process = subprocess.Popen(
            [str(executable), "run", "--background"],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                status_result = subprocess.run(
                    [str(executable), "status"], env=environment,
                    capture_output=True, text=True, check=True,
                )
                if "Agent ID    missing" not in status_result.stdout:
                    break
                if process.poll() is not None:
                    raise RuntimeError("Frozen Agent exited during identity smoke test")
                time.sleep(0.25)
            else:
                raise RuntimeError("Frozen Agent did not create its identity in time")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        status_result = subprocess.run(
            [str(executable), "status"], env=environment,
            capture_output=True, text=True, check=True,
        )
        for expected in ("Configuration", "Identity", "Autostart", "Runtime"):
            if expected not in status_result.stdout:
                raise RuntimeError(f"Frozen Agent status omitted {expected}")
        if "Agent ID    missing" in status_result.stdout:
            raise RuntimeError("Frozen Agent did not load its generated identity")
        if str(home) not in status_result.stdout:
            raise RuntimeError("Frozen Agent did not resolve its per-user configuration path")


def archive(artifact: Path) -> tuple[Path, Path]:
    release_dir = ROOT / "dist" / "releases"
    release_dir.mkdir(parents=True, exist_ok=True)
    base = release_dir / f"olympus-agent-{version()}-{target_platform()}-{architecture()}"
    if target_platform() == "windows":
        archive_path = Path(shutil.make_archive(str(base), "zip", artifact.parent, artifact.name))
    else:
        archive_path = Path(shutil.make_archive(str(base), "gztar", artifact.parent, artifact.name))
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = Path(str(archive_path) + ".sha256")
    checksum_path.write_text(f"{checksum}  {archive_path.name}\n", encoding="ascii")
    return archive_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the native Olympus Agent for this platform")
    parser.add_argument("--archive", action="store_true", help="Create a named archive and SHA-256 checksum")
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()
    artifact = build()
    if not args.skip_smoke:
        smoke_test(artifact)
    print(f"Built {artifact}")
    if args.archive:
        archive_path, checksum_path = archive(artifact)
        print(f"Archive {archive_path}")
        print(f"Checksum {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
