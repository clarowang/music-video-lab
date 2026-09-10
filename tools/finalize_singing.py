"""Deliver one downloaded H3 clip as ordinary 1080/30fps with original-song audio.

Requires FFmpeg and FFprobe on PATH; Python standard library only. No network calls.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import array
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import wave
from fractions import Fraction
from pathlib import Path

from singing_timing import sha256, timing_plan, wav_info


def run(command):
    return subprocess.run(command, capture_output=True, check=True)


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                           '-show_format', '-of', 'json', str(path)]).stdout)


def video_pts(path, stream):
    data = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_entries', 'frame=best_effort_timestamp',
        '-of', 'json', str(path)]).stdout)
    base = Fraction(stream['time_base'])
    return [int(frame['best_effort_timestamp']) * base for frame in data['frames']]


def track_duration(stream):
    return int(stream['duration_ts']) * Fraction(stream['time_base'])


def check_raw(path, plan):
    data = probe(path)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    if ((video['width'], video['height']) != (864, 1536)
            or Fraction(video['avg_frame_rate']) != 24
            or Fraction(video['r_frame_rate']) != 24
            or video.get('sample_aspect_ratio', '1:1') not in {'1:1', 'N/A'}):
        raise ValueError('Expected an undistorted 864x1536 / 24fps H3 original.')
    frames = int(video['nb_read_frames'])
    if (Fraction(frames, 24) < Fraction(plan['audio_duration_fraction'])
            or track_duration(video) != Fraction(frames, 24)):
        raise ValueError('Original picture duration is too short or inconsistent; no freeze-tail repair.')
    if video_pts(path, video) != [Fraction(i, 24) for i in range(frames)]:
        raise ValueError('Original video has a nonzero start or irregular frame timestamps.')
    return {'frames': frames, 'fps': 24, 'width': 864, 'height': 1536, 'sha256': sha256(path)}


def pcm(path, plan):
    samples = array.array('f')
    samples.frombytes(run(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(path),
        '-map', '0:a:0', '-af', f'atrim=end_sample={plan["audio_samples"]}',
        '-f', 'f32le', '-ac', '2', '-ar', str(plan['audio_sample_rate']), '-']).stdout)
    if sys.byteorder != 'little':
        samples.byteswap()
    if len(samples) != plan['audio_samples'] * 2:
        raise ValueError('Decoded audio does not cover all original-song samples.')
    return samples


def audio_correlation(mix, output, plan):
    reference, actual = pcm(mix, plan), pcm(output, plan)
    count = len(reference)
    mean_r, mean_a = math.fsum(reference) / count, math.fsum(actual) / count
    var_r = math.fsum((x - mean_r) ** 2 for x in reference)
    var_a = math.fsum((x - mean_a) ** 2 for x in actual)
    if var_r / count < 1e-16:
        if max(abs(x - y) for x, y in zip(reference, actual)) > 1e-4:
            raise ValueError('Silent/constant input does not match delivered audio.')
        return None
    covariance = math.fsum((x - mean_r) * (y - mean_a) for x, y in zip(reference, actual))
    correlation = covariance / math.sqrt(var_r * var_a) if var_a > 0 else 0
    if not math.isfinite(correlation) or correlation < .98:
        raise ValueError('Delivered audio does not match the original-song slice at zero offset.')
    return correlation


def check_final(output, mix, plan):
    data = probe(output)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in data['streams'] if s['codec_type'] == 'audio')
    frames = plan['delivery_frames']
    duration = Fraction(plan['delivery_duration_fraction'])
    if ((video['width'], video['height']) != (1080, 1920)
            or Fraction(video['avg_frame_rate']) != 30
            or Fraction(video['r_frame_rate']) != 30
            or int(video['nb_read_frames']) != frames
            or track_duration(video) != duration
            or Fraction(video['start_time']) != 0
            or video.get('sample_aspect_ratio') != '1:1'):
        raise ValueError('Unexpected delivery dimensions, frames, rate, duration or start.')
    if (track_duration(audio) != Fraction(plan['audio_duration_fraction'])
            or Fraction(audio['start_time']) != 0):
        raise ValueError('Delivered audio duration/start does not match the exact WAV slice.')
    if abs(Fraction(data['format']['duration']) - duration) > Fraction(1, 1000000):
        raise ValueError('Container duration differs from the planned picture duration.')
    if video_pts(output, video) != [Fraction(i, 30) for i in range(frames)]:
        raise ValueError('Delivery frame timestamps are not continuous.')
    run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '2', '-i', str(output),
         '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
    correlation = audio_correlation(mix, output, plan)
    return {'sha256': sha256(output), 'full_decode': 'PASS', 'frame_timestamps': 'PASS',
            'original_mix_zero_offset_correlation': correlation, 'timing': plan,
            'human_lip_sync_and_aesthetic_review': 'NOT_PERFORMED_BY_THIS_TOOL'}


def finalize(video, mix, output, check_only=False):
    video, mix, output = Path(video), Path(mix), Path(output)
    if output.suffix.lower() != '.mp4':
        raise ValueError('Output must have an .mp4 extension.')
    if output.resolve() in {video.resolve(), mix.resolve()}:
        raise ValueError('Output must differ from the original video and audio.')
    info = wav_info(mix)
    plan = timing_plan(info['samples'], info['sample_rate'])
    raw = check_raw(video, plan)
    if check_only:
        return check_final(output, mix, plan)
    receipt = output.with_suffix('.delivery.json')
    if output.exists() or receipt.exists():
        raise FileExistsError('Output or receipt already exists; use --check or a new output name.')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=output.stem + '.pending-', suffix='.mp4', dir=output.parent)
    os.close(fd)
    pending = Path(name)
    started = time.perf_counter()
    try:
        # Keep the last real source frame at the 24->30 rounding boundary.
        # check_raw has already rejected a source shorter than the original-song audio.
        filters = (f'[0:v]fps=30:start_time=0:round=near:eof_action=pass,'
                   f'trim=end_frame={plan["delivery_frames"]},setpts=PTS-STARTPTS,'
                   'scale=1080:1920:flags=lanczos,setsar=1[v];'
                   f'[1:a]atrim=end_sample={info["samples"]},asetpts=PTS-STARTPTS[a]')
        timescale = str(math.lcm(info['sample_rate'], 30))
        command = ['ffmpeg', '-v', 'error', '-xerror', '-y', '-threads', '2',
            '-filter_complex_threads', '2', '-i', str(video), '-i', str(mix),
            '-filter_complex', filters, '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-threads', '4', '-preset', 'fast', '-crf', '16',
            '-pix_fmt', 'yuv420p', '-fps_mode', 'cfr', '-r', '30',
            '-c:a', 'aac', '-b:a', '320k', '-ar', str(info['sample_rate']), '-ac', '2',
            '-video_track_timescale', timescale, '-movie_timescale', timescale,
            '-use_editlist', '1', '-map_metadata', '-1', '-movflags', '+faststart', str(pending)]
        run(command)
        final = check_final(pending, mix, plan)
        if raw['sha256'] != sha256(video) or info['sha256'] != sha256(mix):
            raise ValueError('An input changed during processing; output not published.')
        report = {'version': 'native864-ffn4-neutral-minimal-tail-v1',
                  'raw': raw, 'mix_sha256': info['sha256'], 'final': final,
                  'elapsed_seconds': round(time.perf_counter() - started, 3),
                  'note': 'Ordinary resize/frame duplication; AAC audio encoding. No AI enhancement or lip-sync scoring.'}
        # Exclusive hard-link creation cannot replace another process's final file.
        # The temporary file is on the same filesystem as output (NTFS/ext4/APFS).
        os.link(pending, output)
        with receipt.open('x', encoding='utf8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        return report
    finally:
        pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True, help='Downloaded 864x1536 / 24fps H3 original')
    parser.add_argument('--mix', type=Path, required=True, help='Exact matching original-song PCM WAV slice')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Validate an existing output without encoding')
    args = parser.parse_args()
    try:
        report = finalize(args.video, args.mix, args.output, args.check)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except subprocess.CalledProcessError as error:
        parser.exit(2, error.stderr.decode('utf8', errors='replace')[-2500:] + '\n')
    except (OSError, ValueError, KeyError, StopIteration, wave.Error) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
