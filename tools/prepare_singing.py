"""Prepare the observed FFN4 singing API graph; never upload or submit a task.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import wave
from pathlib import Path

from build_h3_api import ROOT, build
from singing_timing import timing_plan, wav_info


def build_production(image, audio, samples, rate, prompt=None):
    cfg = json.loads((ROOT / 'recipes/h3-singing-production.json').read_text(encoding='utf8'))
    plan = timing_plan(samples, rate)
    if prompt is None:
        prompt = (ROOT / cfg['prompt_file']).read_text(encoding='utf8').strip()
    graph = build(image, audio, plan['audio_seconds'], cfg['width'], cfg['height'],
                  cfg['seed'], mode='singing', prompt=prompt)
    # The original D05 model/attention/LoRA/clock chain is retained.
    # Fold sample-exact length into a literal, then add the observed FFN patch.
    graph['11']['inputs']['length'] = plan['generation_frames']
    graph['18'] = {'class_type': 'MiniMaxH3ChunkFeedForward',
                   'inputs': {'model': ['5', 0], **cfg['ffn']}}
    graph['13']['inputs']['model'] = ['18', 0]
    graph['17']['inputs']['filename_prefix'] = 'music-video-lab/singing-production'
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vocal-wav', type=Path, required=True,
                        help='Local PCM vocal WAV, used to count exact samples')
    parser.add_argument('--image', required=True, help='Image filename/reference in the execution service')
    parser.add_argument('--audio', required=True, help='Vocal filename/reference in the execution service')
    parser.add_argument('--prompt', type=Path, help='Optional UTF-8 prompt; changes the observed recipe')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        info = wav_info(args.vocal_wav)
        prompt = args.prompt.read_text(encoding='utf8').strip() if args.prompt else None
        graph = build_production(args.image, args.audio, info['samples'], info['sample_rate'], prompt)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf8', newline='\n') as output:
            json.dump(graph, output, ensure_ascii=False, indent=2)
            output.write('\n')
        print(json.dumps({'written': args.output.name, 'nodes': len(graph),
                          'vocal_sha256': info['sha256'],
                          'plan': timing_plan(info['samples'], info['sample_rate']),
                          'task_submitted': False}, ensure_ascii=False, indent=2))
    except (OSError, ValueError, wave.Error) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
