# 通用H3镜头准备

版本`h3-shot-native864-ffn4-v1`。复用[已公开的FFN4唱歌底座](h3-production.md)，默认864×1536/24fps、8步、seed42。针对实际镜头写提示，不默认继承麦克风、录音棚或人物情绪。

| 模式 | 输入和用途 | 边界 |
|---|---|---|
| `reference-audio` | 参考图+给定音频，Ref2VA | 参考身份/场景，不声明图就是第一帧 |
| `first-frame-audio` | 同一图作参考和首帧，Hybrid，配给定音频 | 保住开场构图的候选；不保证多人只让指定人开口 |
| `first-frame-silent` | 图作参考和首帧，Hybrid，配数字静音 | 用于倾听、小反应、短动作；静音不是闭嘴保证 |

三种都由本地PCM WAV采样数确定2–15秒单窗时长，沿用最小覆盖17n+5帧。输入音频角色必须声明为vocal、mixed或silence。WAV格式不证明内容已分离人声；工具只检查静音模式确实是数字静音。

```bash
python tools/prepare_shot.py --audio-wav inputs/voice.wav --audio-role vocal --image uploaded-image.png --audio uploaded-voice.wav --prompt inputs/shot.txt --mode first-frame-audio --output out/shot.api.json
python tools/prepare_shot.py --inspect out/shot.api.json
```

`image/audio`是生成服务能读取的素材引用，用户需自己上传或用已有执行器绑定。此工具只输出API图和参数/时长报告，没有HTTP请求，不会花生成费。首次生成仍要核实服务端实际模型文件、节点版本及可用性。

想做小尺寸机位探针时显式使用`--quality draft --deviation "Motion test only; not a quality comparison"`。改seed或native CRF也要说明原因。原生576输出再放大1080，仍不能当864原生比较。原图面积低于目标时，节点的参考面积限制可能让实际生成变小，应先准备合适大小的输入，并查原片尺寸。

生成后可继续用[本地交付工具](h3-production.md)：高原生片加对应原曲切片，普通放大到1080/30。检查输出不足帧时报错，不用定格伪造完整生成。通用剧情若需保留中间动作，应显式记生成区间和剪辑取段；这种取段不同于整段音频零余量交付。

## 这次核验了什么

新构建器与旧唱歌构建器共用代码；离线测试覆盖默认高尺寸、静音角色、非法尺寸替代、输入接法和核心连线变更。另将历史唱歌、首帧演唱、多人反应和递杯的实际提交图归一比较：规范节点编号和输入引用、折叠文字/帧数辅助节点后核核心一致。种子、提示、CRF及输入模式作为明确参数分别记录。

没有为这次整理重新生成；也没让另一个RH账号实跑。多人/动作已有候选与取段使用证据，不代表严格角色控制通过。尾帧、参考视频、长镜头接力、横屏、6+2等不在这三种注册用法内，仍可以作为单独实验提出。

这里是执行图，仍没有鼠标画布布局。模型、节点和注意力/FFN方法来自上游，详见[来源](credits.md)；本仓库新增的是用途封装、离线检查与复跑说明。
