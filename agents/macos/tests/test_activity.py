import unittest
from types import SimpleNamespace

from olympus_agent.activity import detect_development_activity


def process(name: str) -> SimpleNamespace:
    return SimpleNamespace(info={"name": name})


class ActivityDetectionTests(unittest.TestCase):
    def test_supported_ide_reports_development(self) -> None:
        activity = detect_development_activity([process("rider")])

        self.assertEqual(activity.mode, "development")
        self.assertEqual(activity.application, "Rider")
        self.assertEqual(activity.process_name, "rider")

    def test_process_matching_is_case_insensitive(self) -> None:
        activity = detect_development_activity([process("Cursor")])

        self.assertEqual(activity.mode, "development")
        self.assertEqual(activity.application, "Cursor")

    def test_unrelated_processes_report_idle(self) -> None:
        activity = detect_development_activity([process("Finder")])

        self.assertEqual(activity.mode, "idle")
        self.assertIsNone(activity.application)

    def test_explicit_empty_process_list_reports_idle(self) -> None:
        self.assertEqual(detect_development_activity([]).mode, "idle")


if __name__ == "__main__":
    unittest.main()
