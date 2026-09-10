"""Build a ComfyUI API graph locally; this module never submits a generation.

Copyright (C) 2026 music-video-lab contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frames_for_seconds(seconds, fps=24):
    if not math.isfinite(seconds) or not 2 <= seconds <= 15:
        raise ValueError('This recipe accepts 2–15 seconds; longer clips need separate validation.')
    if fps != 24:
        raise ValueError('This recipe was tested at 24 fps only.')
    needed = math.ceil(seconds * fps)
    return needed + (5 - needed) % 17


def build(image, audio, seconds=9.2, width=576, height=1024, seed=42,
          mode='singing', prompt=None):
    if mode not in {'singing', 'drama'}:
        raise ValueError('mode must be singing or drama')
    if not image or (mode == 'singing' and not audio):
        raise ValueError('An image is required; singing also needs a source audio filename.')
    if any(not isinstance(n, int) or n < 128 or n > 2048 or n % 32 for n in [width, height]):
        raise ValueError('Dimensions must be multiples of 32 within 128–2048; this is not a VRAM guarantee.')
    if not isinstance(seed, int) or not 0 <= seed < 2 ** 64:
        raise ValueError('seed must be an unsigned 64-bit integer')
    length = frames_for_seconds(seconds)
    cfg = json.loads((ROOT / 'recipes/h3-light.json').read_text(encoding='utf8'))
    if prompt is None:
        prompt = (ROOT / ('recipes/prompts/singing.txt' if mode == 'singing' else 'recipes/prompts/smile.txt')).read_text(encoding='utf8').strip()
    graph = {}

    def node(nid, kind, **inputs):
        graph[str(nid)] = {'class_type': kind, 'inputs': inputs}

    node(1, 'UNETLoader', unet_name=cfg['model'], weight_dtype='default')
    node(2, 'MiniMaxH3MemoryEfficientSageAttentionPatch', model=['1', 0])
    node(3, 'ModelAttentionBackend', model=['2', 0], attention='pytorch attention')
    node(4, 'SolAttnMiniMax', model=['3', 0], **cfg['sol_attention'])
    node(5, 'LoraLoaderBypassModelOnly', model=['4', 0], lora_name=cfg['lora'], strength_model=cfg['lora_strength'])
    node(6, 'CLIPLoader', clip_name=cfg['clip'], type='minimax', device='default')
    node(7, 'VAELoader', vae_name=cfg['video_vae'])
    node(8, 'VAELoader', vae_name=cfg['audio_vae'])
    node(9, 'LoadImage', image=image)
    condition = {
        'allow_above_reference_area': False, 'ref_images.ref_image_0': ['9', 0],
        'length': length, 'audio_denoise_strength': 0, 'ref_image_size': 'max',
        'audio_vae': ['8', 0], 'strict_prompt_tags': True, 'video_vae': ['7', 0],
        'reference_video_policy': 'official_2_to_15s', 'prompt_primary_audio_ordinal': 1 if mode == 'singing' else 0,
        'width': width, 'height': height, 'audio_mode': 'remix_source' if mode == 'singing' else 'native',
        'task_type': 'Ref2VA', 'prompt': prompt, 'add_source_as_reference': False, 'clip': ['6', 0],
    }
    if mode == 'singing':
        node(10, 'LoadAudio', audio=audio, audioUI='')
        condition['drive_audio'] = ['10', 0]
    node(11, 'MiniMaxH3AudioConditioningT8', **condition)
    node(12, 'RandomNoise', noise_seed=seed)
    node(13, 'MiniMaxH3DualClockSamplerT8', scheduler=cfg['scheduler'], shift_audio=cfg['shift_audio'],
         shift_video=cfg['shift_video'], sampler_name=cfg['sampler'], av_latent=['11', 1],
         model=['5', 0], steps=cfg['steps'])
    node(14, 'BasicGuider', conditioning=['11', 0], model=['13', 0])
    node(15, 'SamplerCustomAdvanced', guider=['14', 0], latent_image=['11', 1], noise=['12', 0],
         sigmas=['13', 2], sampler=['13', 1])
    node(16, 'MiniMaxH3AVDecodeT8', av_latent=['15', 0], audio_vae=['8', 0], video_vae=['7', 0])
    node(17, 'VHS_VideoCombine', images=['16', 0], audio=['11', 2] if mode == 'singing' else ['16', 1],
         filename_prefix='music-video-lab/' + mode, **cfg['save_video'])
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Filename visible to the target ComfyUI input directory')
    parser.add_argument('--audio', help='Source vocal audio filename, required for singing')
    parser.add_argument('--seconds', type=float, default=9.2)
    parser.add_argument('--width', type=int, default=576)
    parser.add_argument('--height', type=int, default=1024)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--mode', choices=['singing', 'drama'], default='singing')
    parser.add_argument('--prompt', type=Path, help='UTF-8 prompt file')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        graph = build(args.image, args.audio, args.seconds, args.width, args.height, args.seed,
                      args.mode, args.prompt.read_text(encoding='utf8').strip() if args.prompt else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf8', newline='\n') as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except (ValueError, OSError) as e:
        parser.exit(2, str(e) + '\n')
    print(f'Wrote {args.output}: {len(graph)} nodes, {frames_for_seconds(args.seconds)} frames. No task submitted.')


if __name__ == '__main__':
    main()
