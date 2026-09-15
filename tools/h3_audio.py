"""H3 audio boundary: derived PCM16 inputs and native source-audio validation.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

from singing_timing import sha256

VERSION = 'h3-pcm16-native-audio-v1'


def pcm_info(path):
    """Read integer PCM without imposing a song or shot duration limit."""
    with wave.open(str(path), 'rb') as stream:
        n, rate, channels, width = (stream.getnframes(), stream.getframerate(),
                                     stream.getnchannels(), stream.getsampwidth())
        if stream.getcomptype() != 'NONE' or n <= 0 or rate <= 0 or channels not in (1, 2):
            raise ValueError('Use nonempty mono/stereo audio.')
        left = n
        while left:
            count = min(left, 65536)
            if len(stream.readframes(count)) != count * channels * width:
                raise ValueError('PCM payload is shorter than its header.')
            left -= count
    return dict(samples=n, sample_rate=rate, channels=channels, sample_width=width)


def require_pcm16(path):
    try:
        info = pcm_info(path)
    except (wave.Error, EOFError) as error:
        raise ValueError('H3 drive must be PCM16 WAV; prepare a derived copy with h3_audio.py normalize.') from error
    if info['sample_width'] != 2:
        raise ValueError('H3 drive must be PCM16 WAV; use h3_audio.py normalize without replacing the source.')
    return info


def decoded(path, rate=16000, channels=1):
    command = ['ffmpeg', '-v', 'error', '-xerror', '-threads', '2', '-i', str(path),
               '-map', '0:a:0', '-vn', '-ar', str(rate), '-ac', str(channels), '-f', 'f32le', '-']
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        raise ValueError('Audio stream missing or undecodable: ' + result.stderr.decode('utf-8', errors='replace')[-700:])
    values = array.array('f')
    values.frombytes(result.stdout)
    if sys.byteorder != 'little':
        values.byteswap()
    if not values or len(values) % channels:
        raise ValueError('Empty or incomplete decoded audio.')
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Audio contains NaN or infinite amplitude.')
    return values


def stats(values):
    return {'samples': len(values), 'rms': math.sqrt(math.fsum(v*v for v in values)/len(values)),
            'peak': max(abs(v) for v in values),
            'over_abs1_fraction': sum(abs(v) > 1 for v in values)/len(values)}


def ensure_pcm16(source, output=None):
    """Preserve source rate/channels/timeline; only integer representation changes.

    Original files and unknown existing outputs are never replaced. An existing
    PCM16 source is reused; a prior matching conversion receipt is recoverable.
    Float/compressed inputs are decoded by FFmpeg with their existing time zero.
    """
    source = Path(source).resolve()
    source_hash = sha256(source)
    try:
        original = pcm_info(source)
    except (wave.Error, EOFError):
        original = None
    if original and original['sample_width'] == 2:
        return {'version': VERSION, 'converted': False, 'source': str(source),
                'source_sha256': source_hash, 'path': str(source), 'sha256': source_hash, **original}
    output = Path(output).resolve() if output else source.with_name(source.stem+'-h3-pcm16-'+source_hash[:12]+'.wav')
    receipt = output.with_suffix('.audio.json')
    if output == source or (output.exists() and os.path.samefile(output, source)):
        raise ValueError('PCM16 output must differ from the original and its hard links.')
    if output.exists() or receipt.exists():
        if output.exists() and receipt.exists():
            old = json.loads(receipt.read_text(encoding='utf-8-sig'))
            if (old.get('version') == VERSION and old.get('source_sha256') == source_hash
                    and old.get('sha256') == sha256(output) and old.get('path') == str(output)):
                require_pcm16(output)
                return old
        raise FileExistsError('Unknown/changed audio output or receipt; choose another output path.')
    if original:
        rate, channels = original['sample_rate'], original['channels']
    else:
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
            '-show_entries', 'stream=sample_rate,channels', '-of', 'json', str(source)], capture_output=True, check=True)
        streams = json.loads(result.stdout)['streams']
        if not streams:
            raise ValueError('No source audio stream.')
        rate, channels = int(streams[0]['sample_rate']), int(streams[0]['channels'])
        if rate <= 0 or channels not in (1, 2):
            raise ValueError('Only mono/stereo source audio is supported.')
    before = decoded(source, rate, channels)
    if stats(before)['peak'] > 1.000001:
        raise ValueError('Source exceeds full scale; refusing silent clipping or loudness changes.')
    count = len(before)//channels
    if original and count != original['samples']:
        raise ValueError('Decoded source length differs from PCM header.')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output.stem+'.pending-', suffix='.wav', dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-y', '-i', str(source),
            '-map', '0:a:0', '-vn', '-ar', str(rate), '-ac', str(channels), '-c:a', 'pcm_s16le',
            '-map_metadata', '-1', str(temp)], capture_output=True, check=True)
        info = require_pcm16(temp)
        if (info['samples'], info['sample_rate'], info['channels']) != (count, rate, channels):
            raise ValueError('PCM conversion changed rate, channels or sample count.')
        after = decoded(temp, rate, channels)
        error = max(abs(x-y) for x,y in zip(before, after))
        if len(after) != len(before) or error > 1/32768+1e-7:
            raise ValueError('PCM conversion changed more than one 16-bit quantization step.')
        if sha256(source) != source_hash:
            raise ValueError('Source changed during conversion.')
        result = {'version': VERSION, 'converted': True, 'source': str(source), 'source_sha256': source_hash,
                  'path': str(output), 'sha256': sha256(temp), **info,
                  'max_sample_change': error, 'gain_applied': 1, 'receipt': str(receipt)}
        os.link(temp, output)
        with receipt.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
        return result
    finally:
        temp.unlink(missing_ok=True)


def check_native_audio(native, drive=None):
    """Reject invalid amplitudes before replacing the returned audio with music.

    For source-audio H3 routes, optional drive additionally checks exact-start
    waveform similarity. These measurements are never a lip-sync score.
    """
    observed = decoded(native)
    result = {'version': VERSION, 'native_sha256': sha256(native),
              'analysis_rate': 16000, **stats(observed), 'status': 'PASS',
              'lip_sync_checked': False}
    # AAC may overshoot full scale slightly. Gross normalization faults must not.
    if result['peak'] > 1.25 or result['rms'] > 1.05:
        raise ValueError('Native audio amplitude is abnormal; keep the raw file and stop before original-music replacement.')
    if drive is not None:
        require_pcm16(drive)
        reference = decoded(drive)
        if len(observed) < len(reference):
            raise ValueError('Native audio does not cover the complete drive.')
        observed = observed[:len(reference)]
        r, o = stats(reference), stats(observed)
        result.update(drive_sha256=sha256(drive), reference=r, compared_samples=len(reference))
        if r['rms'] < 1e-8:
            if o['rms'] > 1e-5:
                raise ValueError('Digital-silence drive returned nonsilent source audio.')
            result['zero_offset_correlation'] = None
        else:
            ratio = o['rms']/r['rms']
            mx, my = math.fsum(reference)/len(reference), math.fsum(observed)/len(observed)
            vx = math.fsum((x-mx)**2 for x in reference)
            vy = math.fsum((y-my)**2 for y in observed)
            correlation = math.fsum((x-mx)*(y-my) for x,y in zip(reference, observed))/math.sqrt(vx*vy) if vx*vy else 0
            result.update(rms_ratio=ratio, zero_offset_correlation=correlation)
            if not .8 <= ratio <= 1.25 or correlation < .97:
                raise ValueError('Native source audio differs in level or zero-offset waveform from the submitted drive.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('normalize'); p.add_argument('source', type=Path); p.add_argument('--output', type=Path)
    p = sub.add_parser('check'); p.add_argument('native', type=Path); p.add_argument('--drive', type=Path)
    args = parser.parse_args()
    try:
        result = ensure_pcm16(args.source, args.output) if args.action == 'normalize' else check_native_audio(args.native, args.drive)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, wave.Error, subprocess.CalledProcessError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
