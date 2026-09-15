# 来源、贡献与版本

基础模型、节点与配方来自上游。我们感谢这些作者；同一批样片的成本与观察由本项目记录，任何结论都不代表上游作者背书。

| 来源 | 本项目使用到的部分 |
|---|---|
| [MiniMax H3模型](https://huggingface.co/MiniMaxAI/MiniMax-H3) | 模型、输入模式与提示规范；模型权重遵循其模型许可 |
| [T8star-Aix / T8mars](https://github.com/T8mars/comfyui-minimax-h3-audio-T8) | H3音频条件、双时钟采样、解码及大量公开方法；节点代码为GPL-3.0-or-later |
| [T8 Dasiwa音频驱动V1](https://www.runninghub.cn/post/2092541511882854402) | 本轮轻量配方来源；模型、加速LoRA、注意力组合 |
| [T8文武均衡双采V2](https://www.runninghub.cn/post/2095853288209084417) | E02两遍生成的来源 |
| [T8 Remix文戏](https://www.runninghub.cn/post/2093205066412027905) | 另一套双采对照 |
| [Saganaki22 / ComfyUI-sol-attn](https://github.com/Saganaki22/ComfyUI-sol-attn/blob/930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf/minimax.py) | 新生产版的 `MiniMaxH3ChunkFeedForward`，内部FFN分批；未复制该节点实现。固定源码用于读懂接口，不等于已取得RH部署commit |
| [InfiniteTalk](https://github.com/MeiGen-AI/InfiniteTalk)、[Wan2.1](https://github.com/Wan-Video/Wan2.1) | 已有唱歌生产基线 |
| [FlashVSR](https://github.com/OpenImagingLab/FlashVSR) | 生成后的视频超分；本例使用现有FlashVSR v1.1节点链 |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI)、[VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)、FFmpeg | 节点运行、视频保存、检查与整理 |

本轮源码阅读固定在T8 H3提交 `e4ff8607a982ecea22d68347efc4bcc356b996ea`。这用于固定公开说明；**不等于已核到RH服务器部署的是该提交**。RH节点版本和GPU型号未从回执完整取得。公开模板可能继续更新，使用前查看作者当前说明。

我们的增量：使用真实歌曲做同图同音频对照；固定种子与尺寸；接回不变速、不移位的原曲；保留中间片与负例；拆开生成、超分、普通缩放和人工接受；提供便携的离线检查工具。追加的生产版把分批配方、按采样数规划长度、普通放大与原曲交付整理成通用脚本，并公开13次尝试的选择性账目字段。

`workflows/`是按已测节点接口与配置重建的API图，折叠了纯文本／数值辅助节点、重新编号。它没有复制RH账号绑定、原作者完整画布、平台回执或第三方节点实现。重建图与历史图核心输入及连线做离线等价核验；本次公开整理没有在另一个账号或本地GPU上重新付费运行。

T8仓库已有分镜、歌曲分段和MV编排说明。本项目不以“别人没有分镜”或“原创了所有节点”为卖点。未实测的高级修脸与VocalLock不写成现有能力。

## 2026-09-15：整首制作与字幕模块

便携的 `studio.py`、`rh.py`、模板和教程，来自本项目先行交接版，正式并入公共仓库后直接调用这里的核心，取消包内 `engine/` 副本。原有 H3 工具/配方保持 ab6e8f2 时的字节；每个新批次记录实际工具和依赖配方哈希。整首组装依据实际制作中的连续原曲、共享采样切点与局部接缝方法重新实现；不是把私有生产队列换个文件名。

原词字幕部分使用 [Qwen3-ASR 官方项目](https://github.com/QwenLM/Qwen3-ASR) 的 ForcedAligner 模型和 [shumoLR 的 ComfyUI 节点](https://github.com/shumoLR/Comfyui_SynVow_Qwen3ASR/blob/main/aligner.py)，实测入口为 [user_lmrwtdvh 的公开图](https://www.runninghub.ai/post/2026261585597042689)。另外两个显示/存储组件为 [ComfyUI-Custom-Scripts](https://github.com/pythongosssss/ComfyUI-Custom-Scripts) 的 ShowText 和 [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use) 的 saveText。我们提供所见 8 节点配置、原词/时间转换、异常标记和单样本实测，不分发这些节点实现或模型权重。RH 实例字段与上游版本可能不同，使用方需要核对实际接口。

RH 单任务接入器依据官方[高级创建](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749013)、[上传](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749007)、[V2 查询](https://www.runninghub.cn/runninghub-api-doc-cn/api-425767306)说明整理，接口字段于2026-09-15核对；新接入器仅通过模拟测试。完整验证边界见[这一版的检查记录](starter/VALIDATION.md)。

新的离线演示只有程序生成的几何画面与测试音。它证明文件链能跑，不作为 H3 表演、字幕模型效果或人物形象展示。
