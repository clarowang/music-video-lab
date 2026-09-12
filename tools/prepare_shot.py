"""Prepare and inspect reusable H3 shot graphs. No network or paid submission.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import re
import wave
from pathlib import Path

from build_h3_api import ROOT
from prepare_singing import build_production
from singing_timing import timing_plan, wav_info


def recipe():
    return json.loads((ROOT / 'recipes/h3-shot.json').read_text(encoding='utf8'))


def require_silence(path):
    """Only the declared silent mode needs a digital-silence check."""
    with wave.open(str(path), 'rb') as audio:
        silent_byte = 128 if audio.getsampwidth() == 1 else 0
        while chunk := audio.readframes(65536):
            if any(value != silent_byte for value in chunk):
                raise ValueError('first-frame-silent requires a digital-silence PCM WAV.')


def build_shot(image, audio, samples, rate, prompt, mode='reference-audio',
               quality='delivery', deviation='', seed=42, crf=19):
    cfg = recipe()
    if mode not in cfg['modes'] or quality not in cfg['qualities']:
        raise ValueError('Unknown registered mode or quality.')
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('A shot-specific prompt is required; do not inherit the studio prompt silently.')
    if (quality != 'delivery' or seed != 42 or crf != 19) and not deviation.strip():
        raise ValueError('Changing quality, seed or native CRF requires a deviation reason.')
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('seed must be an unsigned 64-bit integer.')
    if type(crf) is not int or not 0 <= crf <= 51:
        raise ValueError('crf must be an integer from 0 to 51.')
    graph = build_production(image, audio, samples, rate, prompt.strip())
    condition = graph['11']['inputs']
    setting = cfg['modes'][mode]
    condition.update(cfg['qualities'][quality])
    condition.update(task_type=setting['task_type'],
                     prompt_primary_audio_ordinal=setting['primary_audio_ordinal'])
    if setting['first_frame']:
        condition['first_frame'] = ['9', 0]
    graph['12']['inputs']['noise_seed'] = seed
    graph['17']['inputs'].update(crf=crf, filename_prefix='music-video-lab/' + mode)
    inspect_graph(graph, quality)
    return graph


def inspect_graph(graph, quality='delivery'):
    """Read actual inputs, not output filenames. Accept renumbered observed graphs.

    Only known literal helper nodes are folded. Arbitrary expressions are never
    evaluated; an unfamiliar length expression must be resolved by its caller.
    This verifies the registered skeleton, not current service/model availability.
    """
    if not isinstance(graph, dict) or not graph:
        raise ValueError('Expected a ComfyUI API graph object.')
    for node in graph.values():
        if not isinstance(node, dict) or not isinstance(node.get('inputs'), dict):
            raise ValueError('Expected class_type/inputs nodes, not a mouse canvas.')
        for value in node['inputs'].values():
            if isinstance(value, list) and len(value) == 2 and type(value[1]) is int:
                if str(value[0]) not in graph:
                    raise ValueError('Broken graph connection.')

    def one(kind):
        found = [(key, value['inputs']) for key, value in graph.items()
                 if value.get('class_type') == kind]
        if len(found) != 1:
            raise ValueError('Expected exactly one ' + kind)
        return found[0]

    def literal(value):
        if not isinstance(value, list):
            return value
        node = graph[str(value[0])]
        kind, data = node['class_type'], node['inputs']
        if kind == 'CR Prompt Text':
            return data['prompt']
        if kind == 'ComfyMathExpression' and re.fullmatch(r'\d+', data['expression']):
            return int(data['expression'])
        raise ValueError('Unresolved helper input; freeze the value explicitly.')

    cid, cond = one('MiniMaxH3AudioConditioningT8')
    iid, _ = one('LoadImage')
    aid, _ = one('LoadAudio')
    _, sampler = one('MiniMaxH3DualClockSamplerT8')
    fid, ffn = one('MiniMaxH3ChunkFeedForward')
    lid, lora = one('LoraLoaderBypassModelOnly')
    _, output = one('VHS_VideoCombine')
    _, noise = one('RandomNoise')
    expected = recipe()['qualities'][quality]
    if any(cond[key] != value for key, value in expected.items()):
        raise ValueError('Actual native dimensions do not match selected quality ' + quality)
    frames = literal(cond['length'])
    if type(frames) is not int or frames < 56 or frames > 362 or frames % 17 != 5:
        raise ValueError('Expected a legal 17n+5 length covering a 2-15 second window.')
    if sampler['steps'] != 8 or output['frame_rate'] != 24:
        raise ValueError('The registered engine uses 8 steps and 24 fps.')
    if sampler['model'] != [fid, 0] or ffn['model'] != [lid, 0]:
        raise ValueError('FFN must be after LoRA and before DualClock.')
    if any(ffn.get(k) != v for k, v in {'enabled': True, 'chunks': 4, 'min_tokens': 8192}.items()):
        raise ValueError('Unexpected FFN parameters.')
    if (cond['audio_mode'] != 'remix_source' or cond['audio_denoise_strength'] != 0
            or cond['drive_audio'] != [aid, 0] or output['audio'] != [cid, 2]):
        raise ValueError('Registered route requires source audio conditioning and source audio output.')
    if cond.get('ref_images.ref_image_0') != [iid, 0]:
        raise ValueError('Missing image reference.')
    matching = [name for name, setting in recipe()['modes'].items()
                if cond['task_type'] == setting['task_type']
                and cond['prompt_primary_audio_ordinal'] == setting['primary_audio_ordinal']
                and cond.get('first_frame') == ([iid, 0] if setting['first_frame'] else None)]
    if len(matching) != 1:
        raise ValueError('Conditioning does not match a registered input mode.')
    baseline = build_production('image.png', 'audio.wav', 96000, 48000, 'placeholder')
    if core_signature(graph) != core_signature(baseline):
        raise ValueError('Model, decoder, attention or core connections differ from the registered engine.')
    return {'mode': matching[0], 'quality': quality, **expected,
            'fps': output['frame_rate'], 'frames': frames, 'steps': sampler['steps'],
            'seed': noise['noise_seed'], 'crf': output['crf'],
            'ffn': {k: ffn[k] for k in ('enabled', 'chunks', 'min_tokens')},
            'model': one('UNETLoader')[1]['unet_name'], 'lora': lora['lora_name'],
            'prompt': literal(cond['prompt']),
            'class_types': sorted({node['class_type'] for node in graph.values()}),
            'service_availability': 'not checked', 'visual_acceptance': 'not checked'}


def core_signature(graph):
    """Canonical connected computation, excluding the documented shot variables."""
    roots = [key for key, node in graph.items() if node['class_type'] == 'VHS_VideoCombine']
    if len(roots) != 1:
        raise ValueError('Expected one video output.')
    variables = {
        'LoadImage': {'image'}, 'LoadAudio': {'audio', 'audioUI'},
        'RandomNoise': {'noise_seed'},
        'VHS_VideoCombine': {'filename_prefix', 'crf'},
        'MiniMaxH3AudioConditioningT8': {'width', 'height', 'length', 'prompt',
            'task_type', 'first_frame', 'prompt_primary_audio_ordinal'},
    }

    def visit(key, seen):
        if key in seen:
            raise ValueError('Cyclic graph connection.')
        node = graph[key]
        kind, inputs = node['class_type'], node['inputs']
        result = {}
        for field, value in sorted(inputs.items()):
            if field in variables.get(kind, set()):
                continue
            if isinstance(value, list) and len(value) == 2 and type(value[1]) is int:
                value = [visit(str(value[0]), seen | {key}), value[1]]
            if kind == 'LoraLoaderBypassModelOnly' and field == 'strength_model':
                value = round(float(value), 12)
            result[field] = value
        return {'class_type': kind, 'inputs': result}

    return visit(roots[0], set())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', type=Path, help='Inspect an existing actual API graph; no build')
    parser.add_argument('--audio-wav', type=Path)
    parser.add_argument('--audio-role', choices=['vocal', 'mixed', 'silence'])
    parser.add_argument('--image', help='Execution service image reference')
    parser.add_argument('--audio', help='Execution service audio reference')
    parser.add_argument('--prompt', type=Path)
    parser.add_argument('--mode', choices=list(recipe()['modes']), default='reference-audio')
    parser.add_argument('--quality', choices=list(recipe()['qualities']), default='delivery')
    parser.add_argument('--deviation', default='')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--crf', type=int, default=19)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.inspect:
            print(json.dumps(inspect_graph(json.loads(args.inspect.read_text(encoding='utf-8-sig')),
                                           args.quality), ensure_ascii=False, indent=2))
            return
        if not all((args.audio_wav, args.audio_role, args.image, args.audio, args.prompt, args.output)):
            raise ValueError('Build requires audio-wav, audio-role, image, audio, prompt and output.')
        if (args.mode == 'first-frame-silent') != (args.audio_role == 'silence'):
            raise ValueError('Silence role and silent input mode must be selected together.')
        info = wav_info(args.audio_wav)
        if args.audio_role == 'silence':
            require_silence(args.audio_wav)
        graph = build_shot(args.image, args.audio, info['samples'], info['sample_rate'],
                           args.prompt.read_text(encoding='utf-8-sig'), args.mode,
                           args.quality, args.deviation, args.seed, args.crf)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf8', newline='\n') as stream:
            json.dump(graph, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print(json.dumps({'graph': str(args.output), 'version': recipe()['version'],
                          'actual': inspect_graph(graph, args.quality), 'audio': info,
                          'audio_role': args.audio_role, 'deviation': args.deviation,
                          'timing': timing_plan(info['samples'], info['sample_rate']),
                          'task_submitted': False}, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, wave.Error) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
