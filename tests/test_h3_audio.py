"""Regression probes for sample-preserving conversion and native amplitude faults."""
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from h3_audio import ensure_pcm16, require_pcm16, check_native_audio


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class AudioBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='h3-audio-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def source(self, width, name='source.wav', rate=44100):
        path = self.root/name
        count = rate*2+7
        values = [round(.3*math.sin(i*.083)*(2**(width*8-1)-1)) for i in range(count)]
        with wave.open(str(path), 'wb') as stream:
            stream.setparams((2, width, rate, 0, 'NONE', 'not compressed'))
            stream.writeframes(b''.join(v.to_bytes(width,'little',signed=True)*2 for v in values))
        return path, count

    def test_24_and_32_bit_keep_all_samples_and_original_bytes(self):
        for width in (3,4):
            source, count = self.source(width, f'pcm{width}.wav')
            original = source.read_bytes()
            result = ensure_pcm16(source)
            self.assertTrue(result['converted'])
            self.assertEqual((result['samples'],result['sample_rate'],result['channels']), (count,44100,2))
            self.assertLessEqual(result['max_sample_change'],1/32768+1e-7)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(ensure_pcm16(source), result)

    def test_pcm16_is_reused_and_wrong_depth_is_rejected_before_upload(self):
        source, _ = self.source(2)
        self.assertFalse(ensure_pcm16(source)['converted'])
        wrong, _ = self.source(3,'wrong.wav')
        with self.assertRaisesRegex(ValueError,'PCM16'):
            require_pcm16(wrong)

    def test_unknown_output_source_and_hardlink_cannot_be_overwritten(self):
        source, _ = self.source(3)
        with self.assertRaises(ValueError):ensure_pcm16(source,source)
        out=self.root/'existing.wav';out.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):ensure_pcm16(source,out)
        self.assertEqual(out.read_bytes(),b'keep')
        alias=self.root/'linked.wav'
        __import__('os').link(source,alias)
        with self.assertRaises(ValueError):ensure_pcm16(source,alias)

    def test_truncated_payload_is_rejected(self):
        source, _ = self.source(3)
        source.write_bytes(source.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError,'payload'):
            ensure_pcm16(source)

    def test_float_wav_is_derived_without_time_shift(self):
        source, count = self.source(2)
        floating=self.root/'float.wav'
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-c:a','pcm_f32le',str(floating)],check=True,capture_output=True)
        result=ensure_pcm16(floating)
        self.assertEqual(result['samples'],count)
        self.assertLessEqual(result['max_sample_change'],1/32768+1e-7)

    def test_native_huge_float_amplitude_is_blocked_before_remix(self):
        source,_=self.source(2,rate=48000)
        bad=self.root/'bad.wav'
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-af','volume=65536','-c:a','pcm_f32le',str(bad)],check=True,capture_output=True)
        with self.assertRaisesRegex(ValueError,'amplitude'):
            check_native_audio(bad,source)
        with self.assertRaisesRegex(ValueError,'clipping'):
            ensure_pcm16(bad)

    def test_source_audio_correspondence_and_missing_audio(self):
        source,_=self.source(2,rate=48000)
        native=self.root/'native.m4a'
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-c:a','aac','-b:a','192k',str(native)],check=True,capture_output=True)
        result=check_native_audio(native,source)
        self.assertGreater(result['zero_offset_correlation'],.97)
        shifted=self.root/'shifted.wav'
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-af','adelay=150|150','-c:a','pcm_s16le',str(shifted)],check=True,capture_output=True)
        with self.assertRaisesRegex(ValueError,'differs'):
            check_native_audio(shifted,source)
        with self.assertRaises(ValueError):check_native_audio(self.root/'missing.mp4')


if __name__=='__main__':unittest.main()
