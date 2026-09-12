"""Contract checks for new shot preparation; no paid calls.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import copy
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_shot import build_shot, inspect_graph, require_silence
from prepare_singing import build_production


class ShotTests(unittest.TestCase):
    def test_default_is_high_native_and_existing_singing_core(self):
        graph = build_shot('a.png', 'b.wav', 452001, 48000, 'A restrained performance.')
        report = inspect_graph(graph)
        self.assertEqual((report['width'], report['height'], report['frames']), (864, 1536, 243))
        baseline = build_production('a.png', 'b.wav', 452001, 48000, 'A restrained performance.')
        graph['17']['inputs']['filename_prefix'] = baseline['17']['inputs']['filename_prefix']
        self.assertEqual(graph, baseline)

    def test_silent_first_frame_remains_source_conditioned(self):
        graph = build_shot('a.png', 'b.wav', 144000, 48000, 'Both listen quietly.', 'first-frame-silent')
        self.assertEqual(graph['11']['inputs']['first_frame'], ['9', 0])
        self.assertEqual(inspect_graph(graph)['mode'], 'first-frame-silent')
        self.assertEqual(graph['11']['inputs']['audio_denoise_strength'], 0)
        self.assertEqual(graph['17']['inputs']['audio'], ['11', 2])

    def test_low_quality_needs_reason_and_cannot_masquerade_as_delivery(self):
        with self.assertRaisesRegex(ValueError, 'deviation'):
            build_shot('a.png', 'b.wav', 144000, 48000, 'Listen.', quality='draft')
        graph = build_shot('a.png', 'b.wav', 144000, 48000, 'Listen.', quality='draft', deviation='Motion only')
        with self.assertRaisesRegex(ValueError, 'native dimensions'):
            inspect_graph(graph)
        self.assertEqual(inspect_graph(graph, 'draft')['width'], 576)

    def test_changed_model_or_decode_route_is_not_silently_accepted(self):
        graph = build_shot('a.png', 'b.wav', 144000, 48000, 'Listen.')
        for node, field, value in [('1', 'unet_name', 'unverified.safetensors'),
                                    ('17', 'images', ['9', 0]),
                                    ('13', 'steps', 6), ('18', 'chunks', 2)]:
            modified = copy.deepcopy(graph)
            modified[node]['inputs'][field] = value
            with self.assertRaises(ValueError):
                inspect_graph(modified)

    def test_silence_is_actual_pcm_not_a_filename_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'silence.wav'
            for data, silent in [(b'\0\0' * 64000, True), (b'\1\0' + b'\0\0' * 63999, False)]:
                with wave.open(str(path), 'wb') as output:
                    output.setparams((1, 2, 32000, 0, 'NONE', 'not compressed'))
                    output.writeframes(data)
                if silent:
                    require_silence(path)
                else:
                    with self.assertRaises(ValueError):
                        require_silence(path)

    def test_prompt_and_uncatalogued_modes_do_not_fall_back(self):
        for prompt, mode in [('', 'reference-audio'), ('Listen.', 'unknown')]:
            with self.assertRaises(ValueError):
                build_shot('a.png', 'b.wav', 144000, 48000, prompt, mode)


if __name__ == '__main__':
    unittest.main()
