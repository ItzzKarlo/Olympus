import os
from pathlib import Path
import tempfile
import unittest

from olympus_agent_common.identity import load_or_create_device_key


class DeviceKeyTests(unittest.TestCase):
    def test_key_is_generated_once_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".olympus" / "agent-key.pem"
            first = load_or_create_device_key(path)
            second = load_or_create_device_key(path)
            self.assertEqual(first.public_bytes, second.public_bytes)
            self.assertEqual(len(first.public_bytes), 32)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
