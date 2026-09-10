"""Exact sample/frame planning shared by the public singing tools.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import math
import wave
from fractions import Fraction
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def wav_info(path):
    with wave.open(str(path), 'rb') as audio:
        if audio.getcomptype() != 'NONE':
            raise ValueError('Use an uncompressed PCM WAV.')
        samples, rate = audio.getnframes(), audio.getframerate()
        channels, sample_width = audio.getnchannels(), audio.getsampwidth()
        # Check actual payload too: a valid-looking header can describe a truncated file.
        remaining = samples
        while remaining:
            count = min(remaining, 65536)
            if len(audio.readframes(count)) != count * channels * sample_width:
                raise ValueError('The PCM WAV payload is shorter than its header.')
            remaining -= count
    timing_plan(samples, rate)
    return {'samples': samples, 'sample_rate': rate, 'channels': channels,
            'sample_width': sample_width, 'sha256': sha256(path)}


def timing_plan(samples, rate):
    if (type(samples) is not int or type(rate) is not int or samples <= 0 or rate <= 0):
        raise ValueError('Samples and sample rate must be positive integers.')
    seconds = Fraction(samples, rate)
    if not 2 <= seconds <= 15:
        raise ValueError('This recipe accepts 2–15 seconds; this is not a VRAM guarantee.')
    needed = math.ceil(seconds * 24)
    generated = needed + (5 - needed) % 17
    delivered = math.ceil(seconds * 30)
    return {'audio_samples': samples, 'audio_sample_rate': rate,
            'audio_seconds': float(seconds), 'audio_duration_fraction': str(seconds),
            'generation_fps': 24, 'generation_frames': generated,
            'generation_tail_fraction': str(Fraction(generated, 24) - seconds),
            'delivery_fps': 30, 'delivery_frames': delivered,
            'delivery_duration_fraction': str(Fraction(delivered, 30)),
            'delivery_tail_fraction': str(Fraction(delivered, 30) - seconds),
            'exact_audio_video_length': Fraction(delivered, 30) == seconds}
