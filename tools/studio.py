"""Portable music-video preparation and assembly. No network or paid calls.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import array
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import wave
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_shot import build_shot, inspect_graph
from singing_timing import timing_plan, sha256
from finalize_singing import finalize, check_final, probe



def engine_snapshot():
    # Hash the shared public implementation, including local modifications.
    # An in-flight batch keeps its own frozen snapshot; upgrading the checkout is explicit.
    files = ['tools/studio.py', 'tools/build_h3_api.py', 'tools/prepare_shot.py', 'tools/prepare_singing.py',
             'tools/singing_timing.py', 'tools/finalize_singing.py',
             'recipes/h3-light.json', 'recipes/h3-shot.json', 'recipes/h3-singing-production.json',
             'workflows/h3-singing-production.api.json']
    return {'repository': 'https://github.com/clarowang/music-video-lab',
            'recipe': 'starter-2026-09-15',
            'files': {p: sha256(ROOT / p) for p in files}}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def command(args, cwd=None):
    p = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', errors='replace')[-3500:])
    return p.stdout


def ff(args, cwd=None):
    return command(['ffmpeg', '-v', 'error', '-xerror', '-n', '-threads', '2',
                    '-filter_complex_threads', '2', *args], cwd)


def local(root, name):
    p = (Path(root) / name).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValueError('Project paths must stay inside the project: ' + str(name))
    return p


def wavinfo(path):
    with wave.open(str(path), 'rb') as w:
        info = dict(samples=w.getnframes(), rate=w.getframerate(),
                    channels=w.getnchannels(), width=w.getsampwidth())
        if info['rate'] != 48000 or info['width'] != 2 or info['channels'] not in (1, 2):
            raise ValueError('Use 48 kHz, 16-bit PCM WAV, mono or stereo: ' + str(path))
        if len(w.readframes(info['samples'])) != info['samples'] * info['channels'] * 2:
            raise ValueError('Truncated WAV: ' + str(path))
        return info


def wavcut(source, output, start, end, silent=False):
    with wave.open(str(source), 'rb') as r:
        r.setpos(start)
        data = r.readframes(end - start)
        if len(data) != (end - start) * r.getnchannels() * r.getsampwidth():
            raise ValueError('Audio does not cover the requested sample interval.')
        with wave.open(str(output), 'wb') as w:
            w.setparams(r.getparams())
            w.writeframes(bytes(len(data)) if silent else data)


def validate(root):
    from PIL import Image
    root = Path(root).resolve()
    p = read(root / 'project.json')
    if p.get('schema') != 'music-video-starter-v1':
        raise ValueError('Unknown project schema.')
    if p.get('subtitles_clock', 'song') not in ('song', 'clip'):
        raise ValueError('subtitles_clock must be song or clip.')
    if p.get('vocal_alignment_reviewed') is not True:
        raise ValueError('Listen/check vocal-to-song alignment, then record vocal_alignment_reviewed=true.')
    mix, vocal = local(root, p['mix']), local(root, p['vocal'])
    mi, vi = wavinfo(mix), wavinfo(vocal)
    if mi['samples'] != vi['samples']:
        raise ValueError('Full vocal and song must use the same start and sample count; do not stretch silently.')
    shots, ids = p['shots'], set()
    if not shots:
        raise ValueError('No shots. First design the story and listen to the cut points.')
    previous = None
    for s in shots:
        sid, a, b = s['id'], s['start_sample'], s['end_sample']
        if not isinstance(sid, str) or not re.fullmatch(r'[0-9]{2,3}', sid) or sid in ids:
            raise ValueError('Use unique two/three-digit shot IDs.')
        ids.add(sid)
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= mi['samples']:
            raise ValueError('Invalid sample bounds: ' + sid)
        if a % 1600 or b % 1600:
            raise ValueError('Starter strict mode requires 30 fps cut points (1600 samples at 48k). See timing guide.')
        if previous is not None and a != previous:
            raise ValueError('Shots must cover one continuous song interval, with no gaps/overlap.')
        previous = b
        timing_plan(b - a, 48000)  # Public production scope: 2 to 15 seconds.
        mode = s.get('mode', 'reference-audio')
        drive = s.get('drive', 'vocal')
        if mode not in ('reference-audio', 'first-frame-audio', 'first-frame-silent'):
            raise ValueError('Unknown H3 input mode.')
        if drive not in ('vocal', 'mix', 'silence') or ((mode == 'first-frame-silent') != (drive == 'silence')):
            raise ValueError('Silent shots require both silent input mode and silent drive.')
        image = local(root, s['image'])
        with Image.open(image) as im:
            if im.width < 864 or im.height < 1536 or im.width * 16 != im.height * 9:
                raise ValueError('Prepare a real portrait 9:16 reference >=864x1536; do not stretch faces: ' + sid)
        if not local(root, s['prompt']).read_text('utf-8-sig').strip():
            raise ValueError('Empty shot prompt: ' + sid)
    if p.get('subtitles'):
        local(root, p['subtitles']).read_text('utf-8-sig')
    return p


def prepare(project, batch):
    project, batch = Path(project).resolve(), Path(batch).resolve()
    p = validate(project)
    batch.mkdir(parents=True, exist_ok=False)
    (batch / 'jobs').mkdir()
    (batch / 'clips').mkdir()
    source_files = {p['mix'], p['vocal'], 'project.json'}
    if p.get('subtitles'):
        source_files.add(p['subtitles'])
        shutil.copyfile(local(project, p['subtitles']), batch / 'lyrics.srt')
    first, last = p['shots'][0]['start_sample'], p['shots'][-1]['end_sample']
    wavcut(local(project, p['mix']), batch / 'continuous-mix.wav', first, last)
    rows = []
    for s in p['shots']:
        sid, a, b = s['id'], s['start_sample'], s['end_sample']
        j = batch / 'jobs' / sid
        j.mkdir()
        source_files.update((s['image'], s['prompt']))
        image_name = 'reference' + local(project, s['image']).suffix.lower()
        shutil.copyfile(local(project, s['image']), j / image_name)
        prompt = local(project, s['prompt']).read_text('utf-8-sig').strip()
        (j / 'prompt.txt').write_text(prompt + '\n', encoding='utf-8', newline='\n')
        drive = s.get('drive', 'vocal')
        source = p['mix'] if drive == 'mix' else p['vocal']
        wavcut(local(project, source), j / 'drive.wav', a, b, drive == 'silence')
        wavcut(local(project, p['mix']), j / 'mix.wav', a, b)
        mode = s.get('mode', 'reference-audio')
        graph = build_shot('__UPLOAD_IMAGE__', '__UPLOAD_AUDIO__', b - a, 48000,
                           prompt, mode, 'delivery', '', 42, 19)
        write(j / 'workflow.api.json', graph)
        files = [image_name, 'drive.wav', 'mix.wav', 'prompt.txt', 'workflow.api.json']
        job = dict(id=sid, image=image_name, drive='drive.wav', mix='mix.wav',
                   graph='workflow.api.json', audio_role=drive, timing=timing_plan(b-a, 48000),
                   actual=inspect_graph(graph, 'delivery'),
                   hashes={name: sha256(j / name) for name in files},
                   task_submitted=False, human_review='pending')
        write(j / 'job.json', job)
        rows.append(dict(id=sid, start_sample=a, end_sample=b,
                         start_frame=(a-first)//1600, end_frame=(b-first)//1600,
                         frames=(b-a)//1600))
    manifest = dict(schema='music-video-starter-batch-v1', title=p.get('title', ''),
                    source_start_sample=first, source_end_sample=last,
                    frames=(last-first)//1600, sample_rate=48000, fps=30,
                    subtitles_clock=p.get('subtitles_clock', 'song'),
                    mix_sha256=sha256(batch/'continuous-mix.wav'),
                    subtitle_sha256=sha256(batch/'lyrics.srt') if (batch/'lyrics.srt').exists() else None,
                    shots=rows, input_hashes={f:sha256(local(project, f)) for f in sorted(source_files)},
                    engine=engine_snapshot(),
                    generation_authorized=False)
    write(batch/'manifest.json', manifest)
    write(batch/'project.snapshot.json', p)
    return dict(batch=str(batch), shots=len(rows), frames=manifest['frames'],
                rh_calls=0, next='Read docs/starter/04-RunningHub.md before any paid submission.')


def deliver(batch, sid, raw):
    batch, raw = Path(batch).resolve(), Path(raw).resolve()
    m = read(batch/'manifest.json')
    if sid not in {s['id'] for s in m['shots']}:
        raise ValueError('Shot is not in this batch.')
    j = batch/'jobs'/sid
    job = read(j/'job.json')
    for name, expected in job['hashes'].items():
        if sha256(j/name) != expected:
            raise ValueError('Frozen job input changed: ' + name)
    out = batch/'clips'/f'{sid}.mp4'
    result = finalize(raw, j/'mix.wav', out, check_only=out.exists())
    return dict(id=sid, output=str(out), result=result)


def srt_cues(text):
    cues = []
    text = text.lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n')
    def seconds(stamp):
        match = re.fullmatch(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})', stamp.strip())
        if not match:
            raise ValueError('Malformed SRT timestamp: ' + stamp)
        h,m,s,ms = map(int,match.groups())
        return Fraction(h*3600+m*60+s) + Fraction(ms,1000)
    for block in re.split(r'\n\s*\n',text.strip()):
        lines = block.splitlines()
        if not lines:
            continue
        i = 1 if lines[0].strip().isdigit() else 0
        if len(lines) <= i+1 or '-->' not in lines[i]:
            raise ValueError('Malformed SRT cue.')
        a,b = [seconds(x) for x in lines[i].split('-->')]
        if a >= b:
            raise ValueError('Zero/negative SRT duration; ask Codex to review, preserve the original.')
        cues.append((a,b,'\n'.join(lines[i+1:])))
    return cues


def ass_time(value):
    n = max(0, round(value*100))
    h,n = divmod(n,360000); m,n = divmod(n,6000); s,n = divmod(n,100)
    return f'{h}:{m:02}:{s:02}.{n:02}'


def clean_ass(text):
    return text.replace('\\','＼').replace('{','｛').replace('}','｝').replace('\n',r'\N')


def make_ass(batch, out, font):
    if any(ch in font for ch in ',\n\r'):
        raise ValueError('Invalid font name.')
    m = read(batch/'manifest.json')
    header = ('[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n'
              'WrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n'
              'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
              f'Style: Lyric,{font},58,&H00F0F6FF,&H00F0F6FF,&H60303030,&H80000000,0,0,0,0,100,100,0,0,1,1.5,1.5,2,80,80,250,1\n'
              f'Style: Title,{font},76,&H00FFFFFF,&H00FFFFFF,&H60303030,&H80000000,0,0,0,0,100,100,0,0,1,1,1.5,8,80,80,140,1\n\n'
              '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
    duration = Fraction(m['frames'],30)
    origin = Fraction(m['source_start_sample'],48000) if m['subtitles_clock']=='song' else Fraction(0)
    if m['subtitles_clock'] not in ('song','clip'):
        raise ValueError('subtitles_clock must be song or clip.')
    lines=[]; mapped=[]
    if (batch/'lyrics.srt').exists():
        for a,b,text in srt_cues((batch/'lyrics.srt').read_text('utf-8-sig')):
            a,b=max(Fraction(1,30),a-origin),min(duration,b-origin)
            if a>=b:
                continue
            lines.append(f'Dialogue: 1,{ass_time(a)},{ass_time(b)},Lyric,,0,0,0,,{{\\fad(80,80)}}{clean_ass(text)}\n')
            mapped.append(dict(start=float(a),end=float(b),text=text))
    if m['title']:
        lines.append(f'Dialogue: 2,0:00:00.00,{ass_time(min(duration,Fraction(3)))},Title,,0,0,0,,{{\\fad(120,180)}}{clean_ass(m["title"])}\n')
    (out/'captions.ass').write_text(header+''.join(lines),encoding='utf-8',newline='\n')
    write(out/'captions.json',mapped)


def vencode():
    return ['-c:v','libx264','-threads','4','-preset','fast','-crf','18',
            '-pix_fmt','yuv420p','-r','30','-fps_mode','cfr','-video_track_timescale','48000']


def assemble(batch, output, transition_frames=0, font='Arial', font_file=None):
    batch, out = Path(batch).resolve(), Path(output).resolve()
    m = read(batch/'manifest.json')
    if sha256(batch/'continuous-mix.wav') != m['mix_sha256']:
        raise ValueError('Frozen continuous music changed.')
    if m['subtitle_sha256'] and sha256(batch/'lyrics.srt') != m['subtitle_sha256']:
        raise ValueError('Frozen subtitles changed. Prepare a new version for editing changes.')
    if transition_frames < 0 or transition_frames > 30 or transition_frames % 2:
        raise ValueError('Transition length must be 0 or an even frame count <=30.')
    half=transition_frames//2
    clips=[]
    for s in m['shots']:
        clip=batch/'clips'/f'{s["id"]}.mp4'
        plan=timing_plan(s['end_sample']-s['start_sample'],48000)
        check_final(clip,batch/'jobs'/s['id']/'mix.wav',plan)
        if s['frames'] <= 2*half:
            raise ValueError('Shot too short for this transition.')
        clips.append(clip)
    protected={str(x):sha256(x) for x in clips+[batch/'continuous-mix.wav',batch/'manifest.json']}
    out.mkdir(parents=True,exist_ok=False)
    (out/'parts').mkdir()
    (out/'fonts').mkdir()
    if font_file:
        font_file=Path(font_file).resolve()
        shutil.copyfile(font_file,out/'fonts'/font_file.name)
    make_ass(batch,out,font)
    started=time.perf_counter(); parts=[]
    for i,(s,clip) in enumerate(zip(m['shots'],clips)):
        left=half if i else 0
        right=s['frames']-(half if i<len(clips)-1 else 0)
        name=f'part-{len(parts):03}.mp4'
        ff(['-i',clip,'-an','-vf',f'trim=start_frame={left}:end_frame={right},setpts=PTS-STARTPTS,setsar=1',
            *vencode(),out/'parts'/name])
        parts.append((name,right-left))
        if half and i<len(clips)-1:
            graph=(f'[0:v]trim=start_frame={s["frames"]-half}:end_frame={s["frames"]},setpts=PTS-STARTPTS,fps=30,'
                   f'tpad=stop_mode=clone:stop={half},trim=end_frame={2*half},setsar=1,settb=AVTB[a];'
                   f'[1:v]trim=end_frame={half},setpts=PTS-STARTPTS,fps=30,tpad=start_mode=clone:start={half},'
                   f'trim=end_frame={2*half},setsar=1,settb=AVTB[b];'
                   f'[a][b]xfade=transition=fade:duration={transition_frames/30:.9f}:offset=0,'
                   f'trim=end_frame={transition_frames},settb=1/30,format=yuv420p[v]')
            name=f'part-{len(parts):03}.mp4'
            ff(['-i',clip,'-i',clips[i+1],'-filter_complex',graph,'-map','[v]','-an',*vencode(),out/'parts'/name])
            parts.append((name,transition_frames))
    if sum(n for _,n in parts)!=m['frames']:
        raise ValueError('Internal assembly length mismatch.')
    (out/'parts.ffconcat').write_text('ffconcat version 1.0\n'+''.join(f"file 'parts/{name}'\n" for name,_ in parts),encoding='utf-8')
    ff(['-f','concat','-safe','0','-i','parts.ffconcat','-an','-c:v','copy',
        '-video_track_timescale','48000','picture.mp4'],out)
    # Always lay down one continuous original song. Clip audio never participates in a transition.
    ff(['-i','picture.mp4','-i',batch/'continuous-mix.wav','-vf','ass=captions.ass:fontsdir=fonts',
        '-map','0:v:0','-map','1:a:0',*vencode(),'-c:a','aac','-b:a','320k','-ar','48000','-ac','2',
        '-movie_timescale','48000','-use_editlist','1','-map_metadata','-1','-movflags','+faststart','final.mp4'],out)
    samples=m['source_end_sample']-m['source_start_sample']
    # Same public verification accepts long assembled songs; only the planner's generation input is 2-15 s.
    plan={'audio_samples':samples,'audio_sample_rate':48000,'audio_duration_fraction':str(Fraction(samples,48000)),
          'delivery_frames':m['frames'],'delivery_duration_fraction':str(Fraction(m['frames'],30))}
    result=check_final(out/'final.mp4',batch/'continuous-mix.wav',plan)
    if any(sha256(p)!=h for p,h in protected.items()):
        raise ValueError('An input changed during assembly.')
    report=dict(schema='starter-assembly-v1',engine_verification=result,
                elapsed_seconds=round(time.perf_counter()-started,3),transition_frames=transition_frames,
                transition_note='Optional blend uses cloned edge frames only inside the seam; lip-sync may look worse there.',
                protected_inputs=protected,human_review='pending')
    write(out/'verification.json',report)
    links=''.join(f'<li>{html.escape(s["id"])}: {s["start_frame"]/30:.3f}–{s["end_frame"]/30:.3f}s</li>' for s in m['shots'])
    page=('<!doctype html><meta charset="utf-8"><title>Video review</title>'
          '<style>body{background:#121722;color:#eef2fa;font:18px system-ui;max-width:920px;margin:32px auto}video{max-height:72vh;max-width:100%}a{color:#8de6cf}</style>'
          '<h1>成片复看 / Human review</h1><p>这是技术交付候选。请听咬字、看表情、接缝、字幕和人物一致性。</p>'
          '<video controls src="final.mp4"></video><p><a href="final.mp4">打开视频</a> · <a href="captions.ass">可编辑字幕</a></p>'
          '<ol>'+links+'</ol><p>本页面无服务依赖，双击即可打开。</p>')
    (out/'review.html').write_text(page,encoding='utf-8')
    return dict(output=str(out/'final.mp4'),frames=m['frames'],rh_calls=0,check='PASS',human_review='pending')


def doctor():
    report={'python':sys.version.split()[0], 'account_checked':False, 'network_called':False}
    for tool in ('ffmpeg','ffprobe'):
        path=shutil.which(tool)
        report[tool]=path
        if not path:
            raise ValueError(tool+' is missing from PATH. See docs/starter/01-Quickstart.md.')
    filters=command(['ffmpeg','-hide_banner','-filters']).decode('utf-8',errors='replace')
    encoders=command(['ffmpeg','-hide_banner','-encoders']).decode('utf-8',errors='replace')
    for token in (' ass ',' xfade ',' tpad '):
        if token not in filters:
            raise ValueError('FFmpeg lacks filter: '+token.strip())
    if 'libx264' not in encoders:
        raise ValueError('FFmpeg lacks libx264.')
    import PIL
    import requests
    report.update(pillow=PIL.__version__,requests=requests.__version__,checks='PASS')
    return report


def demo(output):
    from PIL import Image, ImageDraw
    root=Path(output).resolve(); root.mkdir(parents=True,exist_ok=False)
    project=root/'project'; project.mkdir()
    for sub in ('inputs','images','prompts'):
        (project/sub).mkdir()
    # Synthetic tones and geometry test time, transport and editing; they are not an H3/voice sample.
    pcm=array.array('h')
    for i in range(480000):
        x=round(3000*math.sin(2*math.pi*(330 if i<240000 else 440)*i/48000))
        pcm.extend((x,x))
    if sys.byteorder!='little': pcm.byteswap()
    with wave.open(str(project/'inputs/mix.wav'),'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(pcm.tobytes())
    shutil.copyfile(project/'inputs/mix.wav',project/'inputs/vocal.wav')
    shots=[]
    for sid,a,b,color in [('01',48000,193600,'#284F63'),('02',193600,344000,'#774336')]:
        im=Image.new('RGB',(864,1536),color); d=ImageDraw.Draw(im)
        d.rounded_rectangle((150,300,714,1180),80,outline='#DAE3CC',width=18)
        d.ellipse((320,530,544,754),fill='#DAE3CC')
        d.text((280,1240),'OFFLINE DEMO / '+sid,fill='white',font_size=28)
        im.save(project/'images'/f'{sid}.png')
        (project/'prompts'/f'{sid}.txt').write_text('An adult singer in a close portrait. Restrained expression, clear articulation, subtle breathing. No microphone, no subtitles.',encoding='utf-8')
        shots.append(dict(id=sid,start_sample=a,end_sample=b,image=f'images/{sid}.png',
                          prompt=f'prompts/{sid}.txt',mode='reference-audio',drive='vocal'))
    (project/'inputs/lyrics.srt').write_text('1\n00:00:01,150 --> 00:00:03,800\nOFFLINE DEMO - FIRST SHOT\n\n2\n00:00:04,100 --> 00:00:07,000\nONE CONTINUOUS SOUNDTRACK\n',encoding='utf-8')
    write(project/'project.json',dict(schema='music-video-starter-v1',title='LOCAL PIPELINE DEMO',
          mix='inputs/mix.wav',vocal='inputs/vocal.wav',subtitles='inputs/lyrics.srt',subtitles_clock='song',
          vocal_alignment_reviewed=True,shots=shots))
    batch=root/'batch'; prepare(project,batch)
    for s in shots:
        j=batch/'jobs'/s['id']; job=read(j/'job.json'); frames=job['timing']['generation_frames']
        ff(['-loop','1','-framerate','24','-i',j/job['image'],'-an','-frames:v',str(frames),
            '-vf',"drawbox=x=40+20*sin(t):y=180:w=90:h=90:color=white@0.6:t=fill,setsar=1",
            '-c:v','libx264','-threads','4','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-r','24',j/'native.mp4'])
        deliver(batch,s['id'],j/'native.mp4')
    return assemble(batch,root/'final',8)


def main():
    ap=argparse.ArgumentParser(description=__doc__); sp=ap.add_subparsers(dest='action',required=True)
    sp.add_parser('doctor')
    d=sp.add_parser('demo'); d.add_argument('--out',type=Path,required=True)
    v=sp.add_parser('validate'); v.add_argument('--project',type=Path,required=True)
    p=sp.add_parser('prepare'); p.add_argument('--project',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    p=sp.add_parser('deliver'); p.add_argument('--batch',type=Path,required=True); p.add_argument('--id',required=True); p.add_argument('--raw',type=Path,required=True)
    p=sp.add_parser('assemble'); p.add_argument('--batch',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--transition-frames',type=int,default=0); p.add_argument('--font',default='Arial'); p.add_argument('--font-file',type=Path)
    a=ap.parse_args()
    try:
        if a.action=='doctor': result=doctor()
        elif a.action=='demo': result=demo(a.out)
        elif a.action=='validate': result={'valid':True,'shots':len(validate(a.project)['shots']),'rh_calls':0}
        elif a.action=='prepare': result=prepare(a.project,a.out)
        elif a.action=='deliver': result=deliver(a.batch,a.id,a.raw)
        else: result=assemble(a.batch,a.out,a.transition_frames,a.font,a.font_file)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,OSError,RuntimeError,StopIteration,wave.Error) as e:
        ap.exit(2,str(e)+'\n')


if __name__=='__main__': main()
