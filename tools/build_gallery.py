"""Build a self-contained offline review document; no hosting or external requests.

Copyright (C) 2026 music-video-lab contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    items = json.loads((ROOT/'data/samples.json').read_text(encoding='utf8'))['samples']
    esc = lambda s: html.escape(str(s), quote=True)
    sections=[]
    for name in dict.fromkeys(s['group'] for s in items):
        cards=[]
        for s in (s for s in items if s['group']==name):
            cards.append(f'''<article><h3>{esc(s['title'])}</h3><video controls playsinline muted preload="metadata"
poster="{esc(s['poster'])}" src="{esc(s['video'])}"></video><p>{esc(s['note'])}</p>
<small>{esc(s['case_id'])} · {s['width']}×{s['height']} · {esc(s['fps'])} fps · {s['decoded_frames']}帧</small>
<p><a href="{esc(s['video'])}">单独看视频</a> · <a href="{esc(s['poster'])}">原尺寸截图（{s['poster_seconds']}秒）</a></p></article>''')
        sections.append(f'<section class="group"><div class="head"><h2>{esc(name)}</h2><button type="button">从头一起播放</button></div><div class="grid">'+''.join(cards)+'</div></section>')
    stills=''.join(f'<figure><a href="{esc(s["poster"])}"><img loading="lazy" src="{esc(s["poster"])}" alt="{esc(s["title"])}"></a><figcaption>{esc(s["title"])} · 4.5秒</figcaption></figure>' for s in items if s['group']=='唱歌')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>音乐影像实验室 · H3首版实物</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#10141c;color:#e9edf5;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1450px;margin:auto;padding:38px 24px}h1{font-size:40px;line-height:1.3;margin:16px 0}h2{font-size:25px}h3{font-size:18px;min-height:54px;margin:0 0 12px}a{color:#a8decf}a:hover{color:white}p{color:#c2cad7}small{color:#acb6c6}header{max-width:900px;margin-bottom:30px}.eyebrow{color:#a8decf;letter-spacing:2px}.notice{border-left:3px solid #a8decf;padding:12px 18px;background:#1b2430}.group,.stills{padding:24px;background:#191f2a;border:1px solid #303847;border-radius:16px;margin:26px 0}.head{display:flex;align-items:center;justify-content:space-between;gap:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:18px}article{background:#0f151f;padding:16px;border-radius:12px}video{width:100%;max-height:560px;aspect-ratio:9/16;object-fit:contain;background:black;border-radius:6px}button{background:#a8decf;border:0;color:#102520;border-radius:8px;padding:12px 18px;font:inherit;cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid #fff;outline-offset:4px}.stills .grid{grid-template-columns:repeat(4,minmax(0,1fr))}figure{margin:0}figure img{width:100%;display:block}figcaption{font-size:13px;padding-top:8px}footer{padding:12px 0 36px;color:#acb6c6}details{margin:18px 0}summary{cursor:pointer;color:#a8decf}@media(max-width:700px){main{padding:20px 14px}h1{font-size:29px}.group,.stills{padding:16px}.head{display:block}.head button{margin-bottom:16px}.stills .grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style><main><header><div class="eyebrow">MUSIC VIDEO LAB · 2026-09-10</div><h1>先看实物，再说模型有多强</h1><p>同一段歌的生成、超分与原生尺寸对照；另看浅笑、大笑、三人和扶肩。九个短片来自已有研究，包含失败。</p><p><a href="README.md">项目说明</a> · <a href="docs/h3-study.md">完整研究结论</a> · <a href="docs/reproduce.md">复跑方法</a> · <a href="https://github.com/clarowang/music-video-lab">GitHub</a></p><p class="notice">72币＝29币H3生成＋43币独立FlashVSR任务。不是官方2K重生成，也未证明与190币基线同质量同可用率。唱歌沿用同一原曲，剧情静音。并排播放看观感，逐字口型请单独开声音看。</p></header>'''+''.join(sections)+'''<section class="stills"><h2>同一时刻，再看脸和耳环</h2><p>统一显示大小，点击可看原尺寸。原生与FlashVSR来自同一条生成；高原生和Wan是其他生成结果，姿态不完全相同。更清楚是否更好看，请分部位判断。</p><div class="grid">'''+stills+'''</div></section><details><summary>我们能控制到哪里？</summary><p>能保存实际参数、固定素材与种子、改节点连接、取出中间片、查回结果与费用。平台控制模型部署、显存、排队和计费；具体嘴形、手指和表情仍要看输出。本仓库的工具只负责离线准备与检查，尚无跨账号验收的一键RH应用。</p></details><footer>节点与配方来源：MiniMax、T8star-Aix及相关开源作者；本项目负责场景适配和实物比较。<a href="docs/credits.md">来源说明</a> · <a href="assets/LICENSE.md">示例媒体使用范围</a>。本页不含统计脚本。</footer></main><script>
const videos=[...document.querySelectorAll('video')];
document.querySelectorAll('.group button').forEach(button=>button.addEventListener('click',async()=>{
const group=button.closest('.group');const local=[...group.querySelectorAll('video')];
videos.forEach(v=>v.pause());local.forEach((v,i)=>{v.currentTime=0;v.muted=i!==0;});
const results=await Promise.allSettled(local.map(v=>v.play()));
button.textContent=results.some(r=>r.status==='rejected')?'请分别点击播放器':'重新从头一起播放';
}));
videos.forEach(v=>v.addEventListener('play',()=>videos.filter(x=>x.closest('.group')!==v.closest('.group')).forEach(x=>x.pause())));
</script></html>'''
    (ROOT/'gallery.html').write_text(page,encoding='utf8',newline='\n')
    print(f'gallery.html: {len(items)} videos')


if __name__=='__main__':
    build()
