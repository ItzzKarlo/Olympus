import json
import os
from pathlib import Path
import shutil
import shlex
import sqlite3
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
    def production_core_fixture(self, root: Path) -> Path:
        core = root / "active" / "core"
        shutil.copytree(ROOT / "core" / "olympus_core", core / "olympus_core")
        python = core / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        return core

    def production_config(self, root: Path) -> tuple[Path, Path, Path]:
        database = root / "state" / "core.db"
        backups = root / "backups"
        config = root / "config.toml"
        config.write_text(
            "\n".join((
                "[persistence]",
                f'database_path = "{database}"',
                "[backup]",
                f'directory = "{backups}"',
                "retention_days = 14",
                "",
            )),
            encoding="utf-8",
        )
        return config, database, backups

    def installer_fixture(
        self,
        root: Path,
        core: Path,
        database: Path,
        config: Path,
        *,
        version: str = "1.0.0",
        revision: str = REVISION,
    ) -> tuple[Path, dict[str, str], Path]:
        release = root / "release"
        scripts = release / "scripts" / "hermes"
        scripts.mkdir(parents=True)
        shutil.copy(HERMES_SCRIPTS / "admin.sh", scripts / "admin.sh")
        shutil.copy(HERMES_SCRIPTS / "release_metadata.py", scripts / "release_metadata.py")
        installer = (HERMES_SCRIPTS / "install.sh").read_text(encoding="utf-8")
        installer = installer.replace("/opt/olympus/current/core", str(core))
        installer = installer.replace("/opt/olympus", str(root / "opt" / "olympus"))
        installer = installer.replace("/var/lib/olympus/core.db", str(database))
        installer = installer.replace("/etc/olympus/config.toml", str(config))
        installer = installer.replace("/usr/bin/brave-browser", str(root / "fake-bin" / "brave-browser"))
        install_path = scripts / "install.sh"
        install_path.write_text(installer, encoding="utf-8")
        install_path.chmod(0o755)
        (scripts / "admin.sh").chmod(0o755)
        (release / "VERSION").write_text(f"{version}\n", encoding="ascii")
        (release / "RELEASE-METADATA.json").write_text(json.dumps({
            "revision": revision,
            "source_tree": "clean",
            "version": version,
        }), encoding="ascii")

        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        commands = {
            "id": "#!/bin/sh\nif [ \"${1:-}\" = -u ]; then echo 0; fi\nexit 0\n",
            "install": (
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = -d ]; then\n"
                "    for target in \"$@\"; do :; done\n"
                "    mkdir -p \"$target\"\n"
                "fi\n"
                "exit 0\n"
            ),
            "getent": "#!/bin/sh\nexit 1\n",
            "df": (
                "#!/bin/sh\n"
                "/usr/bin/touch \"$TEST_DF_MARKER\"\n"
                "echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
                "echo \"test 2000000 1 $TEST_AVAILABLE_KB 1% /opt\"\n"
            ),
            "python3": (
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = -m ] && [ \"${2:-}\" = venv ]; then\n"
                "    mkdir -p \"$3/bin\"\n"
                "    printf '#!/bin/sh\\nexit 0\\n' > \"$3/bin/python\"\n"
                "    chmod 0755 \"$3/bin/python\"\n"
                "    exit 0\n"
                "fi\n"
                "exec \"$TEST_REAL_PYTHON\" \"$@\"\n"
            ),
            "chown": "#!/bin/sh\nexit 0\n",
            "systemctl": (
                "#!/bin/sh\n"
                "[ -z \"${TEST_SYSTEMCTL_LOG:-}\" ] || printf '%s\\n' \"$*\" >> \"$TEST_SYSTEMCTL_LOG\"\n"
                "if [ \"${1:-}\" = is-active ]; then\n"
                "    [ \"${TEST_KIOSK_ACTIVE:-0}\" = 1 ]\n"
                "    exit $?\n"
                "fi\n"
                "exit 0\n"
            ),
            "curl": "#!/bin/sh\nexit 0\n",
            "cage": "#!/bin/sh\nexit 0\n",
            "brave-browser": "#!/bin/sh\nexit 0\n",
            "mv": (
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = -Tf ]; then\n"
                "    /bin/rm -f \"$3\"\n"
                "    exec /bin/mv \"$2\" \"$3\"\n"
                "fi\n"
                "exec /bin/mv \"$@\"\n"
            ),
        }
        for name, source in commands.items():
            command = fake_bin / name
            command.write_text(source, encoding="ascii")
            command.chmod(0o755)
        marker = root / "df-reached"
        environment = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "TEST_AVAILABLE_KB": "1",
            "TEST_DF_MARKER": str(marker),
            "TEST_REAL_PYTHON": sys.executable,
        }
        return install_path, environment, marker

    def test_product_and_component_version_declarations_are_synchronized(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
        self.assertEqual(version, "1.0.4")
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
        self.assertIn('COPYFILE_DISABLE=1', builder)
        self.assertIn("-name '._*'", builder)

    def test_kiosk_command_uses_native_brave_defaults_and_cage_021_arguments(self) -> None:
        environment = {
            **os.environ,
            "CAGE_BIN": "/usr/bin/cage",
        }
        result = subprocess.run(
            [HERMES_SCRIPTS / "start-kiosk.sh", "--print-command"],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(shlex.split(result.stdout), [
            "/usr/bin/cage",
            "-d",
            "-s",
            "--",
            "/usr/bin/brave-browser",
            "--ozone-platform=wayland",
            "--kiosk",
            "--no-first-run",
            "--noerrdialogs",
            "--disable-session-crashed-bubble",
            "--disable-translate",
            "--overscroll-history-navigation=0",
            "--user-data-dir=/home/olympus-display/.config/olympus-brave",
            "http://127.0.0.1:8000/",
        ])
        self.assertNotIn("-x", shlex.split(result.stdout))
        self.assertNotIn("--no-sandbox", result.stdout)
        self.assertNotIn("/snap/", result.stdout)

    def test_kiosk_browser_and_profile_remain_explicitly_overridable(self) -> None:
        result = subprocess.run(
            [HERMES_SCRIPTS / "start-kiosk.sh", "--print-command"],
            env={
                **os.environ,
                "CAGE_BIN": "/usr/bin/cage",
                "BROWSER_BIN": "/opt/browser/custom-browser",
                "OLYMPUS_KIOSK_PROFILE": "/srv/olympus/custom-profile",
            },
            capture_output=True,
            text=True,
            check=True,
        )
        arguments = shlex.split(result.stdout)
        self.assertEqual(arguments[4], "/opt/browser/custom-browser")
        self.assertIn("--user-data-dir=/srv/olympus/custom-profile", arguments)

    def test_kiosk_exec_path_is_accepted_by_cage_021_argument_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "drm" / "card0-HDMI-A-1"
            drm.mkdir(parents=True)
            (drm / "status").write_text("connected\n", encoding="ascii")
            cage = root / "cage-0.2.1"
            arguments = root / "cage-arguments"
            cage.write_text(
                """#!/bin/sh
for argument in "$@"; do
    [ "$argument" != "-x" ] || exit 64
done
printf '%s\n' "$@" > "$CAGE_ARGUMENTS"
""",
                encoding="ascii",
            )
            cage.chmod(0o755)

            result = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh"],
                env={
                    **os.environ,
                    "CAGE_BIN": str(cage),
                    "BROWSER_BIN": "/usr/bin/brave-browser",
                    "CURL_BIN": "/usr/bin/true",
                    "OLYMPUS_DRM_ROOT": str(root / "drm"),
                    "OLYMPUS_KIOSK_PROFILE": str(root / "profile"),
                    "XDG_RUNTIME_DIR": str(root / "runtime"),
                    "CAGE_ARGUMENTS": str(arguments),
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(arguments.read_text(encoding="utf-8").splitlines(), [
                "-d",
                "-s",
                "--",
                "/usr/bin/brave-browser",
                "--ozone-platform=wayland",
                "--kiosk",
                "--no-first-run",
                "--noerrdialogs",
                "--disable-session-crashed-bubble",
                "--disable-translate",
                "--overscroll-history-navigation=0",
                f"--user-data-dir={root / 'profile'}",
                "http://127.0.0.1:8000/",
            ])

    def kiosk_cleanup_fixture(self, root: Path, profile: Path) -> tuple[dict[str, str], Path]:
        drm = root / "drm" / "card0-HDMI-A-1"
        drm.mkdir(parents=True)
        (drm / "status").write_text("connected\n", encoding="ascii")
        cage = root / "cage"
        started = root / "kiosk-started"
        cage.write_text("#!/bin/sh\ntouch \"$KIOSK_STARTED\"\n", encoding="ascii")
        cage.chmod(0o755)
        proc = root / "proc"
        proc.mkdir()
        environment = {
            **os.environ,
            "CAGE_BIN": str(cage),
            "BROWSER_BIN": "/usr/bin/brave-browser",
            "CURL_BIN": "/usr/bin/true",
            "KIOSK_STARTED": str(started),
            "OLYMPUS_DRM_ROOT": str(root / "drm"),
            "OLYMPUS_KIOSK_PROFILE": str(profile),
            "OLYMPUS_PROC_ROOT": str(proc),
            "XDG_RUNTIME_DIR": str(root / "runtime"),
        }
        return environment, started

    def test_kiosk_removes_only_stale_singleton_markers_from_inactive_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile"
            profile.mkdir()
            (profile / "SingletonLock").write_text("stale-lock", encoding="ascii")
            (profile / "SingletonCookie").write_text("stale-cookie", encoding="ascii")
            (profile / "SingletonSocket").symlink_to(root / "missing-socket")
            preserved = {
                "History": "history-data",
                "Preferences": "preferences-data",
                "SingletonBackup": "not-a-known-marker",
            }
            for name, content in preserved.items():
                (profile / name).write_text(content, encoding="utf-8")
            environment, started = self.kiosk_cleanup_fixture(root, profile)

            result = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh"],
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(started.exists())
            for marker in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                self.assertFalse((profile / marker).exists())
                self.assertFalse((profile / marker).is_symlink())
            for name, content in preserved.items():
                self.assertEqual((profile / name).read_text(encoding="utf-8"), content)

    def test_kiosk_absent_markers_and_unrelated_browser_profile_are_harmless(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile"
            profile.mkdir()
            environment, started = self.kiosk_cleanup_fixture(root, profile)
            process = root / "proc" / "202"
            process.mkdir()
            (process / "cmdline").write_bytes(
                b"/usr/bin/brave-browser\0--user-data-dir=/home/other/profile\0"
            )

            result = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh"],
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(started.exists())

    def test_kiosk_live_process_using_exact_profile_prevents_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile"
            profile.mkdir()
            markers = ("SingletonLock", "SingletonCookie", "SingletonSocket")
            for marker in markers:
                (profile / marker).write_text("keep", encoding="ascii")
            environment, started = self.kiosk_cleanup_fixture(root, profile)
            process = root / "proc" / "303"
            process.mkdir()
            (process / "cmdline").write_bytes(
                b"/usr/bin/brave-browser\0--user-data-dir=" + str(profile).encode() + b"\0"
            )

            result = subprocess.run(
                [HERMES_SCRIPTS / "start-kiosk.sh"],
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("profile is already used by live process 303", result.stderr)
            self.assertFalse(started.exists())
            for marker in markers:
                self.assertEqual((profile / marker).read_text(encoding="ascii"), "keep")

    def test_kiosk_detects_monitor_and_bounds_core_wait_in_test_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            drm = Path(directory) / "card0-HDMI-A-1"
            drm.mkdir()
            status = drm / "status"
            status.write_text("disconnected\n", encoding="ascii")
            environment = {
                **os.environ,
                "CAGE_BIN": "/usr/bin/cage",
                "BROWSER_BIN": "/usr/bin/brave-browser",
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

    def test_kiosk_waits_for_monitor_and_core_then_starts_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connector = root / "drm" / "card0-HDMI-A-1"
            connector.mkdir(parents=True)
            status = connector / "status"
            status.write_text("disconnected\n", encoding="ascii")
            curl = root / "curl"
            attempts = root / "curl-attempts"
            curl.write_text(
                "#!/bin/sh\n"
                "count=0\n"
                "[ ! -f \"$CURL_ATTEMPTS\" ] || count=$(cat \"$CURL_ATTEMPTS\")\n"
                "count=$((count + 1))\n"
                "printf '%s\\n' \"$count\" > \"$CURL_ATTEMPTS\"\n"
                "[ \"$count\" -ge 2 ]\n",
                encoding="ascii",
            )
            curl.chmod(0o755)
            cage = root / "cage"
            started = root / "started"
            cage.write_text("#!/bin/sh\ntouch \"$KIOSK_STARTED\"\n", encoding="ascii")
            cage.chmod(0o755)
            process = subprocess.Popen(
                [HERMES_SCRIPTS / "start-kiosk.sh"],
                env={
                    **os.environ,
                    "CAGE_BIN": str(cage),
                    "BROWSER_BIN": "/usr/bin/brave-browser",
                    "CURL_BIN": str(curl),
                    "CURL_ATTEMPTS": str(attempts),
                    "KIOSK_STARTED": str(started),
                    "OLYMPUS_DRM_ROOT": str(root / "drm"),
                    "OLYMPUS_KIOSK_PROFILE": str(root / "profile"),
                    "OLYMPUS_KIOSK_MONITOR_WAIT_SECONDS": "0.01",
                    "OLYMPUS_KIOSK_WAIT_SECONDS": "0.01",
                    "OLYMPUS_KIOSK_MAX_WAIT_ATTEMPTS": "3",
                    "XDG_RUNTIME_DIR": str(root / "runtime"),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            status.write_text("connected\n", encoding="ascii")
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertEqual(attempts.read_text(encoding="ascii").strip(), "2")
            self.assertTrue(started.exists())

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
            self.assertIn("Kiosk restart requested: 0", result.stdout)
            self.assertEqual(before, sorted(release.iterdir()))

    def test_kiosk_package_plan_uses_idempotent_official_brave_arm64_repository(self) -> None:
        installer = (HERMES_SCRIPTS / "install.sh").read_text(encoding="utf-8")
        production_kiosk_files = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                HERMES_SCRIPTS / "install.sh",
                HERMES_SCRIPTS / "start-kiosk.sh",
                ROOT / "deploy" / "hermes" / "kiosk.env.example",
            )
        )
        self.assertIn("dpkg --print-architecture", installer)
        self.assertIn("arm64|amd64", installer)
        self.assertIn("brave-browser-archive-keyring.gpg", installer)
        self.assertIn("brave-browser-release.sources", installer)
        self.assertIn("https://brave-browser-apt-release.s3.brave.com/brave-browser.sources", installer)
        self.assertIn('cmp -s "$BRAVE_KEY_TEMP" "$BRAVE_KEYRING"', installer)
        self.assertIn('cmp -s "$BRAVE_SOURCE_TEMP" "$BRAVE_SOURCE"', installer)
        self.assertIn("cage brave-browser fonts-noto-core", installer)
        self.assertIn("[ -x /usr/bin/brave-browser ]", installer)
        self.assertNotIn("curl | sh", installer)
        self.assertNotIn("chromium-browser", production_kiosk_files)
        self.assertNotIn("/snap/bin/chromium", production_kiosk_files)

    def test_installer_separates_enable_start_and_explicit_kiosk_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = self.production_core_fixture(root)
            config, database, _backups = self.production_config(root)
            installer, environment, _marker = self.installer_fixture(
                root, core, database, config
            )
            target = root / "opt" / "olympus" / "releases" / "1.0.0"
            target.mkdir(parents=True)
            (target / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (target / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": REVISION,
                "source_tree": "clean",
                "version": "1.0.0",
            }), encoding="ascii")
            current = root / "opt" / "olympus" / "current"
            current.symlink_to("releases/1.0.0")
            log = root / "systemctl.log"
            environment["TEST_SYSTEMCTL_LOG"] = str(log)

            def invoke(*arguments: str, active: bool) -> list[str]:
                log.unlink(missing_ok=True)
                result = subprocess.run(
                    [installer, *arguments],
                    cwd=root,
                    env={
                        **environment,
                        "TEST_KIOSK_ACTIVE": "1" if active else "0",
                    },
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return log.read_text(encoding="utf-8").splitlines()

            normal_update = invoke(active=True)
            self.assertNotIn("start olympus-kiosk.service", normal_update)
            self.assertNotIn("restart olympus-kiosk.service", normal_update)

            enable_healthy = invoke("--enable-kiosk", active=True)
            self.assertIn("enable olympus-kiosk.service", enable_healthy)
            self.assertIn("is-active --quiet olympus-kiosk.service", enable_healthy)
            self.assertNotIn("start olympus-kiosk.service", enable_healthy)
            self.assertNotIn("restart olympus-kiosk.service", enable_healthy)

            enable_absent = invoke("--enable-kiosk", active=False)
            self.assertIn("start olympus-kiosk.service", enable_absent)
            self.assertNotIn("restart olympus-kiosk.service", enable_absent)

            explicit_restart = invoke("--restart-kiosk", active=True)
            self.assertIn("restart olympus-kiosk.service", explicit_restart)

    def test_installer_rejects_conflicting_restart_and_no_start_actions(self) -> None:
        result = subprocess.run(
            [HERMES_SCRIPTS / "install.sh", "--restart-kiosk", "--no-start"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be used together", result.stderr)

    def test_installer_reuses_same_version_with_identical_provenance_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = self.production_core_fixture(root)
            config, database, _backups = self.production_config(root)
            installer, environment, marker = self.installer_fixture(
                root, core, database, config
            )
            target = root / "opt" / "olympus" / "releases" / "1.0.0"
            target.mkdir(parents=True)
            (target / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (target / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": REVISION,
                "source_tree": "clean",
                "version": "1.0.0",
            }), encoding="ascii")
            (target / "installed-content").write_text("immutable\n", encoding="utf-8")
            current = root / "opt" / "olympus" / "current"
            current.symlink_to("releases/1.0.0")
            before = {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }

            result = subprocess.run(
                [installer, "--no-start"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("identical provenance; reusing it unchanged", result.stdout)
            self.assertFalse(marker.exists())
            self.assertEqual(current.readlink(), Path("releases/1.0.0"))
            self.assertEqual(before, {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            })

    def test_installer_rejects_same_version_with_different_provenance_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = self.production_core_fixture(root)
            config, database, _backups = self.production_config(root)
            installer, environment, marker = self.installer_fixture(
                root, core, database, config
            )
            target = root / "opt" / "olympus" / "releases" / "1.0.0"
            target.mkdir(parents=True)
            (target / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (target / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": "b" * 40,
                "source_tree": "clean",
                "version": "1.0.0",
            }), encoding="ascii")
            (target / "installed-content").write_text("original\n", encoding="utf-8")
            current = root / "opt" / "olympus" / "current"
            current.symlink_to("releases/1.0.0")
            before = {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }

            result = subprocess.run(
                [installer, "--no-start"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("different provenance", result.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(current.readlink(), Path("releases/1.0.0"))
            self.assertEqual(before, {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            })

    def test_installer_installs_new_version_without_mutating_previous_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = self.production_core_fixture(root)
            config, database, _backups = self.production_config(root)
            installer, environment, marker = self.installer_fixture(
                root,
                core,
                database,
                config,
                version="1.0.1",
                revision="c" * 40,
            )
            environment["TEST_AVAILABLE_KB"] = "1999999"
            previous = root / "opt" / "olympus" / "releases" / "1.0.0"
            previous.mkdir(parents=True)
            (previous / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (previous / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": REVISION,
                "source_tree": "clean",
                "version": "1.0.0",
            }), encoding="ascii")
            (previous / "installed-content").write_text("preserved\n", encoding="utf-8")
            current = root / "opt" / "olympus" / "current"
            current.symlink_to("releases/1.0.0")

            result = subprocess.run(
                [installer, "--no-start"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(marker.exists())
            self.assertEqual(current.readlink(), Path("releases/1.0.1"))
            self.assertEqual(
                (previous / "installed-content").read_text(encoding="utf-8"),
                "preserved\n",
            )
            installed = root / "opt" / "olympus" / "releases" / "1.0.1"
            self.assertEqual(json.loads(
                (installed / "RELEASE-METADATA.json").read_text(encoding="ascii")
            )["revision"], "c" * 40)

    def test_installer_runs_pre_update_backup_outside_core_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = self.production_core_fixture(root)
            config, database, backups = self.production_config(root)
            database.parent.mkdir(parents=True)
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE proof (value TEXT NOT NULL)")
                connection.execute("INSERT INTO proof VALUES ('installer')")
            installer, environment, marker = self.installer_fixture(
                root, core, database, config
            )
            caller = root / "unrelated-caller-directory"
            caller.mkdir()

            result = subprocess.run(
                [installer],
                cwd=caller,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Creating pre-update SQLite backup", result.stdout)
            self.assertIn("Created safe SQLite backup", result.stdout)
            self.assertIn("Insufficient free space", result.stderr)
            self.assertTrue(marker.exists())
            created = list(backups.glob("core-*.db"))
            self.assertEqual(len(created), 1)
            with sqlite3.connect(created[0]) as connection:
                self.assertEqual(
                    connection.execute("SELECT value FROM proof").fetchone()[0],
                    "installer",
                )

    def test_admin_wrapper_runs_enrollment_and_devices_outside_core_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = self.production_core_fixture(root)
            config, database, _backups = self.production_config(root)
            caller = root / "unrelated-caller-directory"
            caller.mkdir()
            environment = {
                **os.environ,
                "OLYMPUS_CONFIG": str(config),
            }

            enrollment = subprocess.run(
                [
                    HERMES_SCRIPTS / "admin.sh", "--core-dir", core,
                    "enrollment", "create", "--label", "test",
                ],
                cwd=caller,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            devices = subprocess.run(
                [HERMES_SCRIPTS / "admin.sh", "--core-dir", core, "devices", "list"],
                cwd=caller,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertTrue(database.exists())
            self.assertIn("Olympus enrollment token", enrollment.stdout)
            self.assertIn("No trusted devices", devices.stdout)

    def test_installer_aborts_when_pre_update_admin_backup_fails(self) -> None:
        installer = (HERMES_SCRIPTS / "install.sh").read_text(encoding="utf-8")
        self.assertTrue(installer.startswith("#!/bin/sh\nset -eu\n"))
        self.assertIn('"$RELEASE_DIR/scripts/hermes/admin.sh"', installer)
        self.assertIn("--core-dir /opt/olympus/current/core backup", installer)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / "active" / "core"
            (core / "olympus_core").mkdir(parents=True)
            python = core / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\nexit 23\n", encoding="ascii")
            python.chmod(0o755)
            config, database, _backups = self.production_config(root)
            database.parent.mkdir(parents=True)
            database.write_bytes(b"database-present")
            install_path, environment, marker = self.installer_fixture(
                root, core, database, config
            )
            caller = root / "unrelated-caller-directory"
            caller.mkdir()
            result = subprocess.run(
                [install_path],
                cwd=caller,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 23)
            self.assertIn("Creating pre-update SQLite backup", result.stdout)
            self.assertFalse(marker.exists())

    def test_doctor_rooted_mode_is_observational(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            required = (
                "etc/olympus/config.toml",
                "etc/olympus/secrets.env",
                "var/lib/olympus/core.db",
                "opt/olympus/current/display/index.html",
                "opt/olympus/current/VERSION",
                "opt/olympus/current/RELEASE-METADATA.json",
                "etc/systemd/system/olympus-core.service",
                "etc/systemd/system/olympus-kiosk.service",
                "etc/systemd/system/olympus-backup.timer",
                "etc/systemd/system/olympus-healthcheck.timer",
            )
            for relative in required:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.name == "RELEASE-METADATA.json":
                    content = json.dumps({
                        "revision": REVISION,
                        "source_tree": "clean",
                        "version": "1.0.0",
                    }, indent=2, sort_keys=True)
                elif path.name == "VERSION":
                    content = "1.0.0\n"
                elif path.name == "config.toml":
                    content = "[security]\nrequire_agent_auth = true\n"
                elif path.name == "secrets.env":
                    content = "OLYMPUS_SPOTIFY_ENABLED=false\n"
                elif path.name == "core.db":
                    sqlite3.connect(path).close()
                    continue
                else:
                    content = "test"
                path.write_text(content, encoding="utf-8")
            live_probe_marker = root / "live-probe-called"
            fake_systemctl = root / "fake-systemctl"
            fake_systemctl.write_text(
                "#!/bin/sh\n"
                "touch \"$LIVE_PROBE_MARKER\"\n"
                "exit 99\n",
                encoding="ascii",
            )
            fake_systemctl.chmod(0o755)
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            result = subprocess.run(
                [HERMES_SCRIPTS / "doctor.sh"],
                env={
                    **os.environ,
                    "OLYMPUS_ROOT": str(root),
                    "OLYMPUS_SYSTEMCTL": str(fake_systemctl),
                    "LIVE_PROBE_MARKER": str(live_probe_marker),
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("rooted filesystem inspection", result.stdout)
            self.assertIn("probes skipped", result.stdout)
            self.assertFalse(live_probe_marker.exists())
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

    def test_scheduled_backup_uses_cwd_independent_admin_wrapper(self) -> None:
        unit = (UNITS / "olympus-backup.service").read_text(encoding="utf-8")
        self.assertIn(
            "ExecStart=/opt/olympus/current/scripts/hermes/admin.sh backup",
            unit,
        )

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
        self.assertIn("RestartSec=10s", unit)
        self.assertIn("StartLimitIntervalSec=5min", unit)
        self.assertIn("StartLimitBurst=6", unit)
        self.assertIn("StandardOutput=journal", unit)
        self.assertIn("StandardError=journal", unit)
        self.assertIn("RuntimeDirectory=olympus-kiosk", unit)
        self.assertIn("RuntimeDirectoryMode=0700", unit)
        self.assertIn("Environment=XDG_RUNTIME_DIR=/run/olympus-kiosk", unit)
        self.assertNotIn("Chromium", unit)
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
