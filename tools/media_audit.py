"""Inspect real video frames and extract an unenhanced still with FFmpeg.

Copyright (C) 2026 music-video-lab contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import math
import subprocess
from pathlib import Path


def command(args):
    proc = subprocess.run(args, capture_output=True, text=True, encoding='utf8', errors='replace')
    if proc.returncode:
        raise ValueError(proc.stderr.strip() or 'Media command failed')
    return proc.stdout


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def frame_timing(frames):
    """Use actual PTS, not container duration (which may follow a longer audio track)."""
    pts = [number(f.get('best_effort_timestamp_time', f.get('pts_time'))) for f in frames]
    if not pts or any(t is None for t in pts):
        return {'frame_count': len(frames), 'video_seconds': None, 'monotonic_pts': None}
    gaps = [b-a for a, b in zip(pts, pts[1:])]
    duration = number(frames[-1].get('duration_time', frames[-1].get('pkt_duration_time')))
    duration_source = 'last frame duration'
    if not duration or duration <= 0:
        if gaps and min(gaps) > 0 and max(gaps)-min(gaps) < 0.00002:
            duration = sum(gaps) / len(gaps)
            duration_source = 'inferred from uniform PTS spacing'
        else:
            duration = None
    return {
        'frame_count': len(frames), 'first_video_pts_seconds': pts[0],
        'last_video_pts_seconds': pts[-1],
        'video_seconds': pts[-1]-pts[0]+duration if duration else None,
        'duration_basis': duration_source if duration else 'unknown final-frame duration',
        'monotonic_pts': all(d > 0 for d in gaps),
        'min_pts_gap_seconds': min(gaps) if gaps else None,
        'max_pts_gap_seconds': max(gaps) if gaps else None,
    }


def inspect(path, audio_seconds=None):
    if audio_seconds is not None and (not math.isfinite(audio_seconds) or audio_seconds <= 0):
        raise ValueError('audio-seconds must be finite and positive')
    meta = json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    video = next((s for s in meta['streams'] if s['codec_type'] == 'video'), None)
    if video is None:
        raise ValueError('No video stream')
    frames = json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
        '-show_entries','frame=best_effort_timestamp_time,pts_time,duration_time,pkt_duration_time',
        '-of','json',str(path)])).get('frames', [])
    result = frame_timing(frames)
    result.update(file=Path(path).name, width=video['width'], height=video['height'],
        fps=video.get('avg_frame_rate'), sample_aspect_ratio=video.get('sample_aspect_ratio'),
        display_aspect_ratio=video.get('display_aspect_ratio'),
        container_seconds=number(meta.get('format', {}).get('duration')),
        audio_stream_seconds=[number(s.get('duration')) for s in meta['streams'] if s['codec_type']=='audio'],
        covers_requested_audio=None, requested_audio_seconds=audio_seconds,
        note='Coverage assumes audio and video start at the same point. This is not a lip-sync or visual-quality score.')
    if audio_seconds is not None and result['video_seconds'] is not None:
        result['covers_requested_audio'] = result['video_seconds'] + 0.000001 >= audio_seconds
    return result


def extract(path, at, output):
    if not math.isfinite(at) or at < 0:
        raise ValueError('at must be finite and nonnegative')
    output = Path(output)
    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    command(['ffmpeg','-v','error','-n','-i',str(path),'-ss',str(at),'-frames:v','1',str(output)])
    if not output.is_file() or output.stat().st_size == 0:
        raise ValueError('No frame at that time; check the video duration')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    check = sub.add_parser('inspect'); check.add_argument('video', type=Path)
    check.add_argument('--audio-seconds', type=float)
    still = sub.add_parser('frame'); still.add_argument('video', type=Path)
    still.add_argument('--at', type=float, required=True); still.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        if a.cmd == 'inspect':
            print(json.dumps(inspect(a.video, a.audio_seconds), ensure_ascii=False, indent=2))
        else:
            extract(a.video, a.at, a.output)
            print(a.output)
    except (ValueError, OSError) as e:
        p.exit(2, str(e) + '\n')


if __name__ == '__main__':
    main()
