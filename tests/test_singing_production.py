"""Sample/frame boundaries and actual offline delivery behavior.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from finalize_singing import check_raw, finalize
from prepare_singing import build_production
from singing_timing import timing_plan, wav_info


class TimingTests(unittest.TestCase):
    def test_one_sample_after_generation_boundary_needs_next_legal_group(self):
        self.assertEqual(timing_plan(452000, 48000)['generation_frames'], 226)
        self.assertEqual(timing_plan(452001, 48000)['generation_frames'], 243)

    def test_one_sample_after_delivery_boundary_must_not_cut_audio(self):
        exact, beyond = timing_plan(480000, 48000), timing_plan(480001, 48000)
        self.assertTrue(exact['exact_audio_video_length'])
        self.assertEqual(exact['delivery_tail_fraction'], '0')
        self.assertEqual(beyond['delivery_frames'], 301)
        self.assertLess(Fraction(beyond['delivery_tail_fraction']), Fraction(1, 30))

    def test_frame_grids_cover_audio_and_use_the_smallest_legal_count(self):
        for rate in (44100, 48000):
            for whole in range(2, 15):
                for offset in (0, 1, 1599, 1600, 1999, 2000, rate - 1):
                    samples = whole * rate + offset
                    plan = timing_plan(samples, rate)
                    duration = Fraction(samples, rate)
                    generated, delivered = plan['generation_frames'], plan['delivery_frames']
                    self.assertEqual(generated % 17, 5)
                    self.assertGreaterEqual(Fraction(generated, 24), duration)
                    self.assertLess(Fraction(generated - 17, 24), duration)
                    self.assertGreaterEqual(Fraction(delivered, 30), duration)
                    self.assertLess(Fraction(delivered - 1, 30), duration)

    def test_invalid_sample_counts_and_unmeasured_long_inputs(self):
        for samples, rate in [(0, 48000), (1, 0), (-1, 48000),
                              (480000.0, 48000), (16 * 48000, 48000), (48000, 48000)]:
            with self.assertRaises(ValueError):
                timing_plan(samples, rate)

    def test_pcm_header_cannot_hide_truncated_payload(self):
        with tempfile.TemporaryDirectory(prefix='mvl-wav-') as folder:
            path = Path(folder) / 'audio.wav'
            with wave.open(str(path), 'wb') as stream:
                stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\0\0' * 96000)
            self.assertEqual(wav_info(path)['samples'], 96000)
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaises(ValueError):
                wav_info(path)


class GraphTests(unittest.TestCase):
    def test_public_example_is_rebuildable_and_has_no_broken_connections(self):
        graph = build_production('portrait.png', 'vocal.wav', 441600, 48000)
        expected = json.loads((ROOT / 'workflows/h3-singing-production.api.json').read_text(encoding='utf8'))
        self.assertEqual(graph, expected)
        for node in graph.values():
            for value in node['inputs'].values():
                if isinstance(value, list):
                    self.assertIn(value[0], graph)

    def test_audio_length_is_read_from_samples_not_the_example(self):
        graph = build_production('other.png', 'different.wav', 452001, 48000)
        self.assertEqual(graph['11']['inputs']['length'], 243)
        self.assertEqual(graph['13']['inputs']['model'], ['18', 0])
        self.assertEqual(graph['18']['inputs']['model'], ['5', 0])
        self.assertEqual(graph['17']['inputs']['audio'], ['11', 2])

    def test_prompt_matches_the_published_observed_fingerprint(self):
        recipe = json.loads((ROOT / 'recipes/h3-singing-production.json').read_text(encoding='utf8'))
        prompt = (ROOT / recipe['prompt_file']).read_text(encoding='utf8').strip()
        self.assertEqual(hashlib.sha256(prompt.encode()).hexdigest(), recipe['prompt_sha256_utf8_stripped'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/FFprobe required')
class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='mvl-delivery-')
        cls.folder = Path(cls.temp.name)
        cls.raw, cls.mix = cls.folder / 'raw.mp4', cls.folder / 'mix.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=864x1536:rate=24', '-frames:v', '49', '-c:v', 'libx264',
            '-threads', '2', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(cls.raw)],
            check=True, capture_output=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            'sine=frequency=733:sample_rate=48000', '-af', 'atrim=end_sample=98000',
            '-c:a', 'pcm_s16le', str(cls.mix)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_last_real_frame_survives_24_to_30_rounding_and_recheck(self):
        output = self.folder / 'valid.mp4'
        report = finalize(self.raw, self.mix, output)
        self.assertEqual(report['final']['timing']['delivery_frames'], 62)
        self.assertEqual(report['final']['timing']['delivery_tail_fraction'], '1/40')
        self.assertGreater(report['final']['original_mix_zero_offset_correlation'], .98)
        self.assertEqual(finalize(self.raw, self.mix, output, True)['sha256'], report['final']['sha256'])
        with self.assertRaises(FileExistsError):
            finalize(self.raw, self.mix, output)

    def test_short_source_rejected_before_encoding(self):
        with self.assertRaisesRegex(ValueError, 'too short'):
            check_raw(self.raw, timing_plan(100800, 48000))

    def test_output_cannot_replace_original(self):
        with self.assertRaisesRegex(ValueError, 'differ'):
            finalize(self.raw, self.mix, self.raw)


if __name__ == '__main__':
    unittest.main()
