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
        self.assertTrue(state['track']['id'].startswith('metadata:'))

    async def test_macos_fixed_script_observation_and_denied_access(self):
        import json
        from unittest.mock import AsyncMock, Mock
        collector = LocalMediaCollector()
        collector.enabled = True
        process = Mock(returncode=0)
        process.communicate = AsyncMock(return_value=(json.dumps({'PlaybackStatus': 'playing', 'Position': 1000000, 'Metadata': {'xesam:title': 'Song'}}).encode(), b''))
        with patch('sys.platform', 'darwin'), patch('asyncio.create_subprocess_exec', AsyncMock(return_value=process)) as spawn:
            state = (await collector.sample())[0]
            self.assertTrue(state['is_playing'])
            self.assertEqual(spawn.call_args.args[:3], ('/usr/bin/osascript', '-l', 'JavaScript'))
            collector._next_poll = 0
            process.returncode = 1
            self.assertEqual(await collector.sample(), [])
            self.assertEqual(collector.health, 'unavailable')
