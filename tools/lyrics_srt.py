"""Prepare original-song/text alignment and turn returned TSV into reviewable SRT.
Offline only: this CLI never uploads, calls a model, or submits a paid task.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
from studio import ROOT, read, write, local, sha256

VERSION = 'lyrics-align-public-2026-09-15'

def lyric_lines(path):
    data = Path(path).read_bytes()
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16')
    else:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('gb18030')
    tags = r'\[(?:Verse|Chorus|Intro|Outro|Bridge|Pre-Chorus|Post-Chorus|Hook|Interlude|Instrumental)(?:\s+\d+)?\]'
    lines = [line.strip() for line in text.splitlines() if line.strip() and not re.fullmatch(tags, line.strip(), re.I)]
    if not lines or any(not any(c.isalnum() for c in line) for line in lines):
        raise ValueError('TXT must contain lyric lines, with optional standalone section tags.')
    return lines


def parse_alignment(raw, lines, duration):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid audio duration.')
    if not lines or any(not any(c.isalnum() for c in line) for line in lines):
        raise ValueError('Missing original lyric lines.')
    units = []
    for line_index, line in enumerate(lines):
        prefix = ''
        first = len(units)
        for c in line:
            if c.isalnum():
                units.append({'character': c, 'display': prefix + c, 'line': line_index})
                prefix = ''
            elif len(units) > first:
                units[-1]['display'] += c
            else:
                prefix += c
    parsed = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split('\t')
        if len(fields) != 3:
            raise ValueError(f'Invalid timestamp row {number}')
        text, start, end = fields[0], float(fields[1]), float(fields[2])
        length = sum(c.isalnum() for c in text)
        if not length or not all(map(math.isfinite, (start, end))) or start < 0 or end < start or end > duration + 0.05:
            raise ValueError(f'Invalid text/time interval at row {number}; do not invent timings.')
        if parsed and start < parsed[-1]['start']:
            raise ValueError('Timestamp starts are out of order; preserve raw data for review.')
        parsed.append({'raw_text': text, 'start': start, 'end': end, 'length': length})
    if sum(r['length'] for r in parsed) != len(units):
        raise ValueError('Returned text length differs from original lyrics; no safe positional replacement.')
    cursor = 0
    chars, replacements = [], []
    for index, row in enumerate(parsed):
        part = units[cursor:cursor + row['length']]
        cursor += row['length']
        if part[0]['line'] != part[-1]['line']:
            raise ValueError('A returned token crosses original lyric lines; preserve raw data for review.')
        expected = ''.join(p['character'] for p in part)
        actual = ''.join(c for c in row['raw_text'] if c.isalnum())
        if actual != expected:
            replacements.append({'row': index + 1, 'returned': actual, 'original': expected})
        chars.append({'text': ''.join(p['display'] for p in part), 'start': row['start'], 'end': row['end'],
                      'line': part[0]['line'] + 1, 'raw_text': row['raw_text']})
    sentences = []
    for i, line in enumerate(lines, 1):
        part = [r for r in chars if r['line'] == i]
        if not part:
            raise ValueError('A lyric line has no returned timing.')
        sentences.append({'text': line, 'start': min(r['start'] for r in part), 'end': max(r['end'] for r in part)})
    audit = {'text_authority': 'original_lyrics', 'original_characters': len(units), 'returned_units': len(chars),
             'text_replacements': replacements,
             'zero_duration': [dict(index=i + 1, **r) for i, r in enumerate(chars) if r['start'] == r['end']],
             'longer_than_2s': [r for r in chars if r['end'] - r['start'] > 2],
             'overlaps': [{'left': i + 1, 'right': i + 2} for i in range(len(chars) - 1)
                          if chars[i]['end'] > chars[i + 1]['start']],
             'srt_zero_duration': [i + 1 for i, r in enumerate(chars) if timestamp(r['start']) == timestamp(r['end'])],
             'timing_policy': 'unchanged model intervals; no invented duration for zero-length characters',
             'listening_verified': False}
    return chars, sentences, audit


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def srt_bytes(rows):
    return '\n'.join(f"{i}\n{timestamp(r['start'])} --> {timestamp(r['end'])}\n{r['text']}\n"
                     for i, r in enumerate(rows, 1)).encode('utf-8-sig')


def prepare(audio, lyrics, out):
    audio, lyrics, out = Path(audio).resolve(strict=True), Path(lyrics).resolve(strict=True), Path(out).resolve()
    if audio.suffix.lower() not in ('.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.aac'):
        raise ValueError('Unsupported audio file; use an explicit song path.')
    lines = lyric_lines(lyrics)
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                             '-of', 'json', str(audio)], capture_output=True, check=True)
    duration = float(json.loads(result.stdout)['format']['duration'])
    if not math.isfinite(duration) or not 0 < duration <= 180:
        raise ValueError('This preparation tool accepts audio up to 180 seconds; this is not a model limit.')
    # Do all input validation before creating an output. Never overwrite source media.
    graph = read(ROOT/'workflows/lyrics-alignment.api.json')
    graph['15']['inputs']['text'] = '\n'.join(lines)
    graph['22']['inputs']['file_name'] = 'alignment-' + sha256(audio)[:12] + '-' + sha256(lyrics)[:12]
    out.mkdir(parents=True, exist_ok=False)
    audio_name = 'source-audio' + audio.suffix.lower()
    shutil.copyfile(audio, out/audio_name)
    shutil.copyfile(lyrics, out/'original-lyrics.txt')
    write(out/'workflow.api.json', graph)
    files = [audio_name, 'original-lyrics.txt', 'workflow.api.json']
    manifest = dict(schema=VERSION, audio=audio_name, lyrics='original-lyrics.txt',
                    lines=lines, duration_seconds=duration, language='Chinese',
                    text_authority='original_lyrics',
                    hashes={name:sha256(out/name) for name in files},
                    tool_sha256=sha256(Path(__file__)),
                    execution_authorized=False, network_calls=0)
    write(out/'alignment-job.json', manifest)
    return dict(job=str(out), lines=len(lines), characters=sum(c.isalnum() for line in lines for c in line),
                duration_seconds=duration, network_calls=0,
                next='Bind uploaded fileName to node 12 in a separate execution copy; see docs/lyrics-alignment.md.')


def finalize(job, tsv, out):
    job, tsv, out = Path(job).resolve(strict=True), Path(tsv).resolve(strict=True), Path(out).resolve()
    manifest = read(job/'alignment-job.json')
    if manifest.get('schema') != VERSION:
        raise ValueError('Unknown alignment job version.')
    for name, expected in manifest['hashes'].items():
        if sha256(local(job, name)) != expected:
            raise ValueError('Frozen alignment input changed: ' + name)
    lines = lyric_lines(local(job, manifest['lyrics']))
    if lines != manifest['lines']:
        raise ValueError('Manifest text differs from frozen original lyrics.')
    raw = tsv.read_bytes()
    chars, sentences, audit = parse_alignment(raw.decode('utf-8-sig'), lines, manifest['duration_seconds'])
    out.mkdir(parents=True, exist_ok=False)
    (out/'alignment.tsv').write_bytes(raw)
    (out/'lines.srt').write_bytes(srt_bytes(sentences))
    (out/'words-raw.srt').write_bytes(srt_bytes(chars))
    write(out/'timings.json', {'words':chars, 'lines':sentences})
    write(out/'audit.json', audit)
    (out/'README.md').write_text(
        '# 字幕待审交付\n\n文字以冻结的原词为准，时间来自导入的模型 TSV。\n\n'
        '- lines.srt：按原词分行的整句字幕，适合先放入剪辑。\n'
        '- words-raw.srt：字/词级原始边界；零时长字可能不显示，不作均分补齐。\n'
        f"- 原始零时长 {len(audit['zero_duration'])}，SRT 毫秒格式下零时长 {len(audit['srt_zero_duration'])}，"
        f"超过 2 秒的单元 {len(audit['longer_than_2s'])}，重叠 {len(audit['overlaps'])}。\n"
        f"- 文字恢复 {len(audit['text_replacements'])} 处，见 audit.json；改字幕不会改音频唱词。\n"
        '- timings.json 和 alignment.tsv 保留边界证据。导入剪辑前听看；修订另存版本。\n'
        '- 本工具没有调用模型；导入的 TSV 应与本次冻结图音/原词来自同一实际任务。\n',
        encoding='utf-8', newline='\n')
    receipt = dict(schema=VERSION, job_sha256=sha256(job/'alignment-job.json'),
                   raw_sha256=sha256(out/'alignment.tsv'), source_hashes=manifest['hashes'],
                   outputs={name:sha256(out/name) for name in ('lines.srt','words-raw.srt','timings.json','audit.json','README.md')},
                   network_calls=0, human_timing_review='pending',
                   imported_tsv_matches_remote_task='caller must verify task provenance')
    write(out/'receipt.json', receipt)
    return dict(output=str(out), lines=len(sentences), units=len(chars),
                zero_duration=len(audit['zero_duration']), network_calls=0, human_timing_review='pending')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--audio', type=Path, required=True)
    p.add_argument('--lyrics', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('finalize')
    p.add_argument('--job', type=Path, required=True)
    p.add_argument('--tsv', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    try:
        result = prepare(a.audio, a.lyrics, a.out) if a.action=='prepare' else finalize(a.job, a.tsv, a.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as e:
        ap.exit(2, str(e)+'\n')


if __name__=='__main__': main()
