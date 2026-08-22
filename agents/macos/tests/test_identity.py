import tempfile
import unittest
from pathlib import Path

from olympus_agent.identity import load_or_create_agent_id


class IdentityTests(unittest.TestCase):
    def test_identity_is_generated_once_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".olympus" / "agent-id"

            first = load_or_create_agent_id(path)
            second = load_or_create_agent_id(path)

            self.assertRegex(first, r"^mac-[0-9a-f]{32}$")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
