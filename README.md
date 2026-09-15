# 音乐影像实验室 · Music Video Lab

**把一首现成歌曲、人物参考和镜头想法，做成可以审阅的音乐视频。** 公开工作流、使用方法、正负样片与实际成本。

我们持续制作音乐影像，研究怎样把已经完成的歌曲、人物图片和镜头意图，变成可以交给剪辑的片段。叁和三界KTV是实际案例；研究范围还会延伸到表情、多人互动、分镜与新模型。

**2026-09-15 更新：[从分镜到成片：音乐视频制作入门版](docs/starter/README.md)。** 新增整首制作工具、给 Codex 的接管说明、项目模板、原曲＋原词字幕对齐和不收费的离线演示。H3 主配方保持不变，进步在于别人更容易接起来、复跑和交付。[查看更新记录](CHANGELOG.md)。

模型、节点与基础配方来自 MiniMax、T8star-Aix 及其他开源作者。我们的贡献是实际制作中的接法、对照、时间轴、交付工具与经验记录，[来源与致谢](docs/credits.md)明确列出。

## 第一次来，从这里开始

1. [下载整个仓库 ZIP](https://github.com/clarowang/music-video-lab/archive/refs/heads/main.zip)，解压后在自己的 Codex 中打开这个文件夹。
2. 把下面的话发给它，让它按阶段读说明、检查环境，先跑离线演示。
3. 正式制作时提供自己的歌曲、人物参考和想要的感觉；先在自己的账号跑一镜，再决定整批。

```text
请先读 AGENTS.md、README.md 和 docs/starter/01-Quickstart.md。
先用人话解释从分镜到成片的流程，检查本机工具与我已有的材料，不启动收费生成。
帮我跑通离线演示，再按我的素材和授权做首个真实镜头。
项目状态和实际结果保存在 work 下，我换聊天后从文件继续。
```

你不需要先学会连 ComfyUI 节点。资料说明怎样准备和检查，模型服务、账户和最终选片仍由你决定。生图使用你的 Codex 实际可用的工具；仓库没有附送生图服务或模型额度。

## 当前推荐路线

**H3 864×1536 / 24fps / 8步 / FFN4 → 本机普通放大 1080×1920 / 30fps → 连续原曲＋字幕剪辑。** 默认不用 FlashVSR、AI 补帧或美颜；轻美颜可以在自己的剪辑软件里另做对照。

| 你要做什么 | 从哪里进入 |
|---|---|
| 从一首歌做出整条视频 | [分镜到成片入门版](docs/starter/README.md)、[快速开始](docs/starter/01-Quickstart.md) |
| 设计分镜、选参考、换装、生首图 | [分镜与生图](docs/starter/02-Storyboard-Images.md) |
| 按原曲唱歌，收回精确长度片段 | [单人唱歌生产指南](docs/h3-production.md)、[API图](workflows/h3-singing-production.api.json) |
| 首帧演唱、静音反应、其他镜头 | [通用 H3](docs/h3-shots.md)、[当前接法与边界](docs/starter/03-H3.md) |
| 把原曲和原词变成字幕 | [歌词对齐](docs/lyrics-alignment.md)：逐句/字级 SRT，附时间瑕疵报告 |
| 多段严丝合缝地合起来 | [共同时间轴](docs/starter/05-Timing.md)、[FFmpeg 剪辑](docs/starter/06-Editing.md) |
| 接自己的 RH 或恢复失败任务 | [单任务接入与恢复](docs/starter/04-RunningHub.md)、[常见问题](docs/starter/07-FAQ.md) |

准备与剪辑使用同一张采样表；48kHz 音频每1600个采样对应一帧30fps画面。模型先生成足够长的原片，本机核覆盖、裁多余尾巴，整首再铺一条连续原曲。不要靠转场或变速把歌越拼越短。具体切点范围和限制见时间轴说明。

## 不花模型费，先试文件链

装好[所需工具](docs/starter/01-Quickstart.md)后，从仓库根目录运行：

```powershell
python tools/studio.py doctor
python tools/studio.py demo --out "work/my-first-demo"
```

到 `work/my-first-demo/final/review.html` 看结果，双击即可，不依赖网页服务。也可以先看仓库里的[演示视频与说明](examples/offline/README.md)。它只用几何图和测试音，验证两镜185帧、连续音轨、字幕、短接缝的完整交接。

**这版整链通过离线验证；新的 RH 接入器只做过模拟接口测试，尚未跨账号付费验收。** 旧 H3 实跑证据、字幕的一条实测、便携软件检查与人工审美分开记录，见[验证范围](docs/starter/VALIDATION.md)。API图是执行图，没有鼠标画布布局；账号可用模型/节点需自行核对。

## 历史样片：第一轮画质与费用对照

下面保留第一轮《药》样片，方便追溯曾经尝试过的超分与低尺寸路线。它们不是当前 FFN4 配方的新一轮同素材比较。

| 同一段《药》，9.2秒 | 高清尺寸整理后 | 同日生产基线 |
|---|---|---|
| [![H3接FlashVSR](assets/posters/singing-flash.png)](assets/videos/singing-flash.mp4) | [![提高原生尺寸](assets/posters/singing-high.png)](assets/videos/singing-high.mp4) | [![Wan基线](assets/posters/singing-wan.png)](assets/videos/singing-wan.mp4) |
| H3生成29＋FlashVSR43＝**72 RH币** | H3原生864×1536，再普通放大到1080：**54 RH币** | Wan＋InfiniteTalk＋FlashVSR：**190 RH币** |

点击图片进入对应视频文件。完整下载仓库后，双击 [gallery.html](gallery.html) 可并排播放、查看原生与超分前后的静帧。GitHub的源码预览不会执行这个HTML。

**72币是这次两项任务的实扣之和，不是H3官方2K超分，也不是已经发布的一键融合应用。** 三者的输出帧率、质感和最终可用率并不相等。价格是历史样本，不能直接推成同质量生产报价。

- **唱歌**：H3已有值得听看嘴形的候选；接回同一原曲，没有平移音频去修同步。逐字口型还需要人审。
- **超分**：本例耳环和麦克风更清楚，但脸部可能更有加工感。新增细节不必然是真实细节。
- **表情与互动**：浅笑、大笑、近侧手扶肩有可挑片段；精确控制每个人的头和眼睛仍有缺口。
- **失败也公开**：双采样例生成了假字幕；更复杂的配方没有自动更好。

## 历史证据与测量

- [H3首轮公开报告](docs/h3-study.md)、[首轮复跑说明](docs/reproduce.md)：历史正负对照与入口。
- [第二批13次尝试](data/h3-production-batch-002.json)：4次显存失败，8段FFN4/24G＋1段原方案/48G；9段技术交付共708 RH币。人工时间与最终采用率没测全，不作固定报价。
- [检查自己的视频](docs/tools.md)：查真实帧数/PTS/音画时长、固定时刻抽帧。检查结果不替代连续口型和审美判断。

## 仓库里有什么

```text
AGENTS.md      新 Codex 从文件接管的说明
docs/starter/  分镜、生图、H3、RH、时间轴、剪辑、恢复
docs/          专题研究、复跑步骤、限制与上游来源
recipes/       已测设置、镜头提示与超分参数
workflows/     根据已测接口重建的ComfyUI API图（不是鼠标画布JSON）
tools/         共用核心、整首准备/收片/剪辑、可选 RH 单任务、字幕对齐收尾
templates/     空白项目、分镜、状态、尝试与授权记录
tests/         时间/输入/恢复保护与离线验证
data/          筛选的实测字段、版本和核验
examples/      CC0 几何图/合成音演示
assets/        少量历史真实样片，独立素材许可
```

`studio.py` 和 `lyrics_srt.py` 都在本机运行。可选 `rh.py submit` 会读取你本机环境变量中的密钥、上传该镜素材并请求一次付费生成；默认无许可不能提交，没有自动重试或消费硬封顶。仓库没有账户、私人角色库、整首歌或模型权重，也还不是 RH 一键应用。

## 交流

欢迎在 [Issues](https://github.com/clarowang/music-video-lab/issues) 留下可复现的问题：输入类型、使用的版本、参数、实际结果与预期。分享自己的示例前请确认素材可公开，别贴API密钥或私有下载地址。

后续优先沿真实制作问题继续研究：脸与配饰的不同增强收益、原曲口型、多人关系和分镜交付。结果成熟就补充，不承诺固定更新频率。

**English:** Production-grounded AI music-video workflows, now with a portable storyboard-to-edit starter, exact shared timing, optional RH adapter, lyric alignment, offline demo, failure records and measured costs. Start with the [quickstart](docs/starter/01-Quickstart.md). The new RH adapter has not been validated on a second account.

代码与API图采用GPL-3.0-or-later；原创说明采用CC BY 4.0；展示媒体另行许可。请读 [LICENSES.md](LICENSES.md)。
