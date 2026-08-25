import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
HERMES_SCRIPTS = ROOT / "scripts" / "hermes"
UNITS = ROOT / "deploy" / "hermes" / "systemd"
REVISION = "a" * 40


class HermesScriptTests(unittest.TestCase):
    def test_product_and_component_version_declarations_are_synchronized(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
        self.assertEqual(version, "1.0.0")
        self.assertEqual(json.loads((ROOT / "display" / "package.json").read_text())["version"], version)
        common_package = tomllib.loads(
            (ROOT / "agents" / "common" / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(common_package["project"]["version"], version)
        for declaration in (
            ROOT / "agents" / "common" / "olympus_agent_common" / "__init__.py",
            ROOT / "agents" / "macos" / "olympus_agent" / "__init__.py",
            ROOT / "agents" / "windows" / "olympus_agent" / "__init__.py",
            ROOT / "agents" / "linux" / "olympus_agent" / "__init__.py",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(f'__version__ = "{version}"', declaration.read_text(encoding="utf-8"))

    def test_all_shell_helpers_have_valid_posix_syntax(self) -> None:
        scripts = sorted(HERMES_SCRIPTS.glob("*.sh"))
        self.assertGreaterEqual(len(scripts), 6)
        for script in scripts:
            with self.subTest(script=script.name):
                subprocess.run(["/bin/sh", "-n", script], check=True)

    def test_release_builder_uses_product_version_and_generates_provenance(self) -> None:
        builder = (HERMES_SCRIPTS / "build-release.sh").read_text(encoding="utf-8")
        self.assertIn('$ROOT/VERSION', builder)
        self.assertIn('RELEASE-METADATA.json', builder)
        self.assertNotIn('agents/common', builder)

    def test_kiosk_command_keeps_chromium_sandbox_and_uses_wayland(self) -> None:
        environment = {
            **os.environ,
            "CAGE_BIN": "/usr/bin/cage",
            "BROWSER_BIN": "/snap/bin/chromium",
            "OLYMPUS_KIOSK_PROFILE": "/home/kiosk/profile",
        }
        result = subprocess.run(
            [HERMES_SCRIPTS / "start-kiosk.sh", "--print-command"],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--ozone-platform=wayland", result.stdout)
        self.assertIn("--kiosk", result.stdout)
        self.assertIn("http://127.0.0.1:8000/", result.stdout)
        self.assertNotIn("--no-sandbox", result.stdout)

    def test_kiosk_detects_monitor_and_bounds_core_wait_in_test_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            drm = Path(directory) / "card0-HDMI-A-1"
            drm.mkdir()
            status = drm / "status"
            status.write_text("disconnected\n", encoding="ascii")
            environment = {
                **os.environ,
                "CAGE_BIN": "/usr/bin/cage",
                "BROWSER_BIN": "/snap/bin/chromium",
                "OLYMPUS_DRM_ROOT": directory,
            }
            disconnected = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh", "--check-monitor"],
                env=environment,
            )
            self.assertNotEqual(disconnected.returncode, 0)
            status.write_text("connected\n", encoding="ascii")
            connected = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh", "--check-monitor"],
                env=environment,
            )
            self.assertEqual(connected.returncode, 0)
            bounded = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh"],
                env={
                    **environment,
                    "CURL_BIN": "/usr/bin/false",
                    "OLYMPUS_KIOSK_WAIT_SECONDS": "0",
                    "OLYMPUS_KIOSK_MAX_WAIT_ATTEMPTS": "2",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(bounded.returncode, 75)
            self.assertIn("wait limit reached", bounded.stderr)

    def test_installer_dry_run_resolves_versioned_paths_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / "release"
            helper = release / "scripts" / "hermes" / "release_metadata.py"
            helper.parent.mkdir(parents=True)
            shutil.copy(HERMES_SCRIPTS / "release_metadata.py", helper)
            (release / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (release / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": REVISION,
                "source_tree": "clean",
                "version": "1.0.0",
            }), encoding="ascii")
            before = sorted(release.iterdir())
            result = subprocess.run(
                [
                    HERMES_SCRIPTS / "install.sh",
                    "--release-dir", release,
                    "--install-kiosk-packages",
                    "--enable-kiosk",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("/opt/olympus/releases/1.0.0", result.stdout)
            self.assertIn(f"Revision: {REVISION}", result.stdout)
            self.assertIn("Kiosk enable requested: 1", result.stdout)
            self.assertEqual(before, sorted(release.iterdir()))

    def test_doctor_rooted_mode_is_observational(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            required = (
                "etc/olympus/config.toml",
                "var/lib/olympus/core.db",
                "opt/olympus/current/display/index.html",
                "opt/olympus/current/RELEASE-METADATA.json",
                "etc/systemd/system/olympus-core.service",
                "etc/systemd/system/olympus-backup.timer",
                "etc/systemd/system/olympus-healthcheck.timer",
            )
            for relative in required:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                content = json.dumps({
                    "revision": REVISION,
                    "source_tree": "clean",
                    "version": "1.0.0",
                }, indent=2, sort_keys=True) if path.name == "RELEASE-METADATA.json" else "test"
                path.write_text(content, encoding="utf-8")
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            result = subprocess.run(
                [HERMES_SCRIPTS / "doctor.sh"],
                env={**os.environ, "OLYMPUS_ROOT": str(root)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("live service probes skipped", result.stdout)
            self.assertIn("release version: 1.0.0", result.stdout)
            self.assertIn(f"release revision: {REVISION}", result.stdout)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)

    def test_release_metadata_records_clean_revision_and_rejects_dirty_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            (root / "VERSION").write_text("1.0.0\n", encoding="ascii")
            marker = root / "tracked.txt"
            marker.write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", root], check=True)
            subprocess.run(["git", "-C", root, "config", "user.name", "Olympus Tests"], check=True)
            subprocess.run(["git", "-C", root, "config", "user.email", "tests@olympus.invalid"], check=True)
            subprocess.run(["git", "-C", root, "add", "VERSION", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", root, "commit", "-qm", "test source"], check=True)
            revision = subprocess.run(
                ["git", "-C", root, "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            metadata = Path(directory) / "clean.json"
            subprocess.run([
                sys.executable, HERMES_SCRIPTS / "release_metadata.py", "write",
                "--root", root,
                "--output", metadata,
            ], check=True, capture_output=True, text=True)
            value = json.loads(metadata.read_text(encoding="ascii"))
            self.assertEqual(value, {
                "revision": revision,
                "source_tree": "clean",
                "version": "1.0.0",
            })

            marker.write_text("development change\n", encoding="utf-8")
            rejected = subprocess.run([
                sys.executable, HERMES_SCRIPTS / "release_metadata.py", "write",
                "--root", root,
                "--output", Path(directory) / "dirty.json",
            ], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("dirty source tree", rejected.stderr)

            dirty = Path(directory) / "dirty.json"
            subprocess.run([
                sys.executable, HERMES_SCRIPTS / "release_metadata.py", "write",
                "--root", root,
                "--output", dirty,
                "--allow-dirty",
            ], check=True, capture_output=True, text=True)
            install_rejected = subprocess.run([
                sys.executable, HERMES_SCRIPTS / "release_metadata.py", "validate",
                "--metadata", dirty,
                "--version-file", root / "VERSION",
                "--require-clean",
            ], capture_output=True, text=True)
            self.assertNotEqual(install_rejected.returncode, 0)
            self.assertIn("cannot be installed", install_rejected.stderr)

    def test_source_archive_build_accepts_explicit_full_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source-archive"
            root.mkdir()
            (root / "VERSION").write_text("1.0.0\n", encoding="ascii")
            metadata = Path(directory) / "archive-metadata.json"
            revision = "c" * 40
            subprocess.run([
                sys.executable, HERMES_SCRIPTS / "release_metadata.py", "write",
                "--root", root,
                "--output", metadata,
            ], env={**os.environ, "OLYMPUS_SOURCE_REVISION": revision},
                check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(metadata.read_text(encoding="ascii")), {
                "revision": revision,
                "source_tree": "clean",
                "version": "1.0.0",
            })


class SystemdTemplateTests(unittest.TestCase):
    def test_core_is_unprivileged_hardened_and_not_wan_ordered(self) -> None:
        unit = (UNITS / "olympus-core.service").read_text(encoding="utf-8")
        self.assertIn("User=olympus", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("CapabilityBoundingSet=\n", unit)
        self.assertIn("ReadWritePaths=/var/lib/olympus /var/backups/olympus", unit)
        self.assertNotIn("network-online.target", unit)
        self.assertNotIn("--reload", unit)
        self.assertNotIn("workers 2", unit)

    def test_watchdog_can_only_target_olympus_core(self) -> None:
        unit = (UNITS / "olympus-healthcheck.service").read_text(encoding="utf-8")
        implementation = (ROOT / "core" / "olympus_core" / "healthcheck.py").read_text(
            encoding="utf-8"
        )
        combined = unit + implementation
        self.assertIn("olympus-core.service", combined)
        for forbidden in ("reboot", "shutdown", "pterodactyl", "docker", "pihole"):
            self.assertNotIn(forbidden, combined.casefold())

    def test_kiosk_is_independent_low_priority_and_sandbox_preserving(self) -> None:
        unit = (UNITS / "olympus-kiosk.service").read_text(encoding="utf-8")
        self.assertIn("User=olympus-display", unit)
        self.assertIn("Restart=always", unit)
        self.assertIn("CPUWeight=50", unit)
        self.assertIn("OOMScoreAdjust=200", unit)
        self.assertNotIn("Requires=olympus-core", unit)
        self.assertNotIn("--no-sandbox", unit)

    def test_units_never_manage_unrelated_services_or_host_power(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(UNITS.iterdir())
        ).casefold()
        for forbidden in (
            "reboot.target", "poweroff.target", "suspend.target",
            "pterodactyl.service", "docker.service", "pihole",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
