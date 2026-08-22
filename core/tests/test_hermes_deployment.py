import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HERMES_SCRIPTS = ROOT / "scripts" / "hermes"
UNITS = ROOT / "deploy" / "hermes" / "systemd"


class HermesScriptTests(unittest.TestCase):
    def test_all_shell_helpers_have_valid_posix_syntax(self) -> None:
        scripts = sorted(HERMES_SCRIPTS.glob("*.sh"))
        self.assertGreaterEqual(len(scripts), 6)
        for script in scripts:
            with self.subTest(script=script.name):
                subprocess.run(["/bin/sh", "-n", script], check=True)

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
            release.mkdir()
            (release / "VERSION").write_text("0.14.0\n", encoding="ascii")
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
            self.assertIn("/opt/olympus/releases/0.14.0", result.stdout)
            self.assertIn("Kiosk enable requested: 1", result.stdout)
            self.assertEqual(before, sorted(release.iterdir()))

    def test_doctor_rooted_mode_is_observational(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            required = (
                "etc/olympus/config.toml",
                "var/lib/olympus/core.db",
                "opt/olympus/current/display/index.html",
                "etc/systemd/system/olympus-core.service",
                "etc/systemd/system/olympus-backup.timer",
                "etc/systemd/system/olympus-healthcheck.timer",
            )
            for relative in required:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test", encoding="utf-8")
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            result = subprocess.run(
                [HERMES_SCRIPTS / "doctor.sh"],
                env={**os.environ, "OLYMPUS_ROOT": str(root)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("live service probes skipped", result.stdout)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)


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
