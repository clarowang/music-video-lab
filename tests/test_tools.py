"""Boundary checks: do not confuse longer audio with sufficient video frames.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_h3_api import build, frames_for_seconds
from media_audit import frame_timing


class FrameBudgetTests(unittest.TestCase):
    def test_observed_cases(self):
        self.assertEqual(frames_for_seconds(9.2),226)
        self.assertEqual(frames_for_seconds(6.5),158)

    def test_duration_just_over_an_aligned_frame_cannot_round_down(self):
        self.assertEqual(frames_for_seconds(226/24+0.00001),243)

    def test_invalid_duration_rejected(self):
        for seconds in [float('nan'),float('inf'),0,-1,16]:
            with self.assertRaises(ValueError):frames_for_seconds(seconds)

    def test_real_picture_span_excludes_longer_container_audio(self):
        frames=[{'best_effort_timestamp_time':str(10+i/24),'duration_time':str(1/24)} for i in range(221)]
        result=frame_timing(frames)
        self.assertAlmostEqual(result['video_seconds'],221/24)
        self.assertTrue(result['monotonic_pts'])

    def test_unknown_last_frame_is_not_invented(self):
        self.assertIsNone(frame_timing([{'pts_time':'0'}])['video_seconds'])

    def test_nonmonotonic_detected(self):
        result=frame_timing([{'pts_time':'0','duration_time':'.04'},{'pts_time':'0','duration_time':'.04'}])
        self.assertFalse(result['monotonic_pts'])

    def test_singing_requires_audio(self):
        with self.assertRaises(ValueError):build('image.png',None)

    def test_api_connections_exist_without_a_source_audio_in_drama(self):
        graph=build('image.png',None,6.5,mode='drama')
        self.assertNotIn('drive_audio',graph['11']['inputs'])
        for node in graph.values():
            for value in node['inputs'].values():
                if isinstance(value,list):self.assertIn(value[0],graph)


if __name__=='__main__':unittest.main()
