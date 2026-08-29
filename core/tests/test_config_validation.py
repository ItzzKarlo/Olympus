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


if __name__ == "__main__":
    unittest.main()
