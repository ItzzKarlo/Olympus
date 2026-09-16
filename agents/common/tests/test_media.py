import unittest
from unittest.mock import patch
from olympus_agent_common.media import LocalMediaCollector, normalize_mpris

class MediaTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_and_missing_api_are_safe(self):
        with patch.dict('os.environ', {}, clear=True):
            collector = LocalMediaCollector()
            self.assertEqual(await collector.sample(), [])
            self.assertEqual(collector.health, 'disabled')
        collector.enabled = True
        with patch('sys.platform', 'unsupported'):
            self.assertEqual(await collector.sample(), [])
            self.assertEqual(collector.health, 'unsupported_missing_sdk')

    def test_mpris_units_metadata_and_pause(self):
        state = normalize_mpris('org.mpris.MediaPlayer2.spotify', {
            'PlaybackStatus': 'Paused', 'Position': 3500000,
            'Metadata': {'xesam:title': 'Song', 'xesam:artist': ['Artist'], 'mpris:length': 90000000}})
        self.assertEqual(state['progress_ms'], 3500)
        self.assertEqual(state['track']['duration_ms'], 90000)
        self.assertFalse(state['is_playing'])
        self.assertIsNone(state['track']['id'])
