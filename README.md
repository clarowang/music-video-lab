# 音乐影像实验室 · Music Video Lab

**从真实音乐视频制作出发，公开工作流、对照样片、失败记录和实际成本。**

我们持续制作音乐影像，研究怎样把已经完成的歌曲、人物图片和镜头意图，变成可以交给剪辑的片段。叁和三界KTV是实际案例；研究范围还会延伸到表情、多人互动、分镜与新模型。

目前是第一份公开研究快照，2026-09-10。模型、节点与基础配方来自MiniMax、T8star-Aix及其他开源作者；我们的工作是场景适配、同素材比较、实际交付检查和经验记录。这里没有重新训练一个基础模型。

## 先看结果

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

## 从哪里开始

1. [H3首轮公开报告](docs/h3-study.md)：看样本、费用、失败和适用范围。
2. [复跑说明](docs/reproduce.md)：走原作者正常RH入口，或使用API节点图；两种入口分开说明。
3. [检查自己的视频](docs/tools.md)：查帧数、时长，导出固定时刻截图；工具在本地运行，不调用付费生成。
4. [来源与贡献](docs/credits.md)、[许可范围](LICENSES.md)：上游贡献、代码与演示素材分开。

## 首版包含什么

```text
docs/          方法、复跑步骤、限制与上游来源
recipes/       已测设置、镜头提示与超分参数
workflows/     根据已测接口重建的ComfyUI API图（不是鼠标画布JSON）
tools/         生成API图、帧数检查、抽帧和离线看片页
tests/         时长边界及输入检查
data/          19次任务的公开字段、精选样本与哈希
assets/        少量短视频和固定时刻截图
```

当前公开工具只在本地准备和检查，**不会拿到你的密钥，也不会替你发起付费生成**。RH跨账号部署、模型版本、节点兼容性仍需各自核对。我们还没有发布自己的RH一键应用。

## 交流

欢迎在 [Issues](https://github.com/clarowang/music-video-lab/issues) 留下可复现的问题：输入类型、使用的版本、参数、实际结果与预期。分享自己的示例前请确认素材可公开，别贴API密钥或私有下载地址。

后续优先沿真实制作问题继续研究：脸与配饰的不同增强收益、原曲口型、多人关系和分镜交付。结果成熟就补充，不承诺固定更新频率。

**English:** Production-grounded experiments for AI music videos: singing lip sync, expressions, multi-character shots, upscaling, failure cases and measured costs. Start with the [reproduction guide](docs/reproduce.md). This is a research snapshot, not a universal quality or speed benchmark.

代码与API图采用GPL-3.0-or-later；原创说明采用CC BY 4.0；展示媒体另行许可。请读 [LICENSES.md](LICENSES.md)。
