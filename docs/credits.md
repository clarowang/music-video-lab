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
