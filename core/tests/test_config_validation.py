from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from olympus_core.config import load_core_config


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "hermes" / "validate-config.py"


class ProductionConfigValidationTests(unittest.TestCase):
    def run_validator(self, config: Path, secrets: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, VALIDATOR, "--config", config, "--secrets", secrets],
            capture_output=True,
            text=True,
        )

    def test_valid_disabled_integrations_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            secrets = root / "secrets.env"
            config.write_text("[security]\nrequire_agent_auth = true\n", encoding="utf-8")
            secrets.write_text("OLYMPUS_SPOTIFY_ENABLED=false\n", encoding="utf-8")
            result = self.run_validator(config, secrets)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_secret_key_reports_key_and_lines_but_not_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            secrets = root / "secrets.env"
            config.write_text("[security]\nrequire_agent_auth = true\n", encoding="utf-8")
            secret_value = "must-never-appear"
            secrets.write_text(
                f"OLYMPUS_SPOTIFY_ENABLED=false\nOLYMPUS_SPOTIFY_ENABLED={secret_value}\n",
                encoding="utf-8",
            )
            result = self.run_validator(config, secrets)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate key OLYMPUS_SPOTIFY_ENABLED", result.stderr)
        self.assertIn("line 1", result.stderr)
        self.assertNotIn(secret_value, result.stderr)

    def test_malformed_existing_core_config_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text("[broken\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Core configuration is invalid"):
                load_core_config(config)

    def test_enabled_calendar_requires_all_credentials_and_rejects_empty_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            secrets = root / "secrets.env"
            config.write_text(
                "[security]\nrequire_agent_auth = true\n[calendar]\nenabled = true\n",
                encoding="utf-8",
            )
            secrets.write_text(
                "OLYMPUS_GOOGLE_CLIENT_ID=client\n"
                "OLYMPUS_GOOGLE_CLIENT_SECRET=\"\"\n",
                encoding="utf-8",
            )
            result = self.run_validator(config, secrets)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OLYMPUS_GOOGLE_CLIENT_SECRET", result.stderr)
        self.assertIn("OLYMPUS_GOOGLE_REFRESH_TOKEN", result.stderr)

    def test_enabled_football_requires_credential_for_selected_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            secrets = root / "secrets.env"
            config.write_text(
                "[security]\nrequire_agent_auth = true\n"
                "[football]\nenabled = true\nprovider = \"football-data\"\n",
                encoding="utf-8",
            )
            secrets.write_text("OLYMPUS_FOOTBALL_API_KEY=wrong-provider-key\n", encoding="utf-8")
            result = self.run_validator(config, secrets)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OLYMPUS_FOOTBALL_DATA_API_KEY", result.stderr)
        self.assertNotIn("wrong-provider-key", result.stderr)

    def test_systemd_secrets_reject_shell_export_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            secrets = root / "secrets.env"
            config.write_text("[security]\nrequire_agent_auth = true\n", encoding="utf-8")
            secrets.write_text("export OLYMPUS_SPOTIFY_ENABLED=false\n", encoding="utf-8")
            result = self.run_validator(config, secrets)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported export prefix", result.stderr)


if __name__ == "__main__":
    unittest.main()
