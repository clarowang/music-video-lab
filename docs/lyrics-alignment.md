# 原曲＋原词：先得到可审的歌词字幕

你已经有确定的歌词，希望知道它们在歌曲的什么位置。给 Qwen3-ForcedAligner-0.6B 同一首音频和原词，让它返回时间；本地工具按原词行生成逐句 SRT，同时保留字/词级 SRT 和异常报告。这个环节和 H3 生视频独立，可以先用在普通剪辑中。

**文字以原词为准，时间仍可能错。** 这是给定文本的强制对齐；字符覆盖完整不等于从声音识别正确，也不等于每个唱点已经人工校准。

## 这一版交了什么

- [8 节点 API 图](../workflows/lyrics-alignment.api.json)：读取音频、加载对齐模型、给定中文原词、返回并保存字级 TSV。保留实跑所见接口，没有节点画布布局或账号绑定。
- [离线准备和收尾工具](../tools/lyrics_srt.py)：冻结输入、填原词、导入返回的 TSV、校核和导出字幕。
- 模型实际执行由你自己的 ComfyUI/RH 环境完成。**本工具不联网，现有 `rh.py` 仅适配 H3 视频任务，不要拿它提交这个字幕图。** 本版没有移植内部的字幕云端队列。

模型来自 [Qwen 官方项目](https://github.com/QwenLM/Qwen3-ASR)，节点参考 [shumoLR 的实现](https://github.com/shumoLR/Comfyui_SynVow_Qwen3ASR/blob/main/aligner.py)，实测入口来自 [user_lmrwtdvh 的公开对齐工作流](https://www.runninghub.ai/post/2026261585597042689)。模型和节点实现没有打包到仓库。

## 1. 准备你自己的输入

```powershell
python tools/lyrics_srt.py prepare --audio "你的歌曲.wav" --lyrics "你的原词.txt" --out "work/song/alignment-v1"
```

这个命令只在本机运行，需要 FFprobe。接受一首不超过 180 秒的音频，这是工具范围，不是模型上限；当前配方固定中文。TXT 支持 UTF-8、带 BOM 的 UTF-16 和 GB18030，保留原词分行及标点，忽略独立的 `[Verse]`、`[Chorus]` 等常见结构标签。模糊文件选择、原词缺失都不自动猜。

生成 `alignment-job.json`、冻结原曲/原词副本、`workflow.api.json`。输出目录必须新建；原文件保持原样。对齐可以先用带伴奏的原曲，我们有一首实际成功记录，不能推成所有混音都一样好。

## 2. 在自己可用的环境运行对齐图

让你的 Codex 核对节点与模型。实际计算链是 `LoadAudio → Qwen3ForcedAlign`，另一路 `Qwen3ForcedAlignerLoader → Qwen3ForcedAlign`，输出 0 是每行“文本、起点、终点”的 TSV，末端 `easy saveText` 保存它；4 个 ShowText 只供查看输出。

先复制冻结图为本地 `submitted.api.json`，将节点 12 的 `audio` 改成上传后返回的 `fileName`；本地 ComfyUI 则用其有效输入文件引用。节点 15 保持你的完整原词、`language=Chinese`、`segment_by_sentence=false`。不要编辑冻结图来蒙混哈希检查。

我们保留 RH 实测所见的 `unload_after` 等字段；上游节点与 RH 部署可能不同，不能假定接口版本完全一样。需要鼠标画布时按你安装的节点重建并检验。提交前给出账号、实际图、费用与具体授权；已有 taskId 先收旧结果，超时不重复提交。把本次实际图、taskId、费用和下载来源记在你自己的工作目录。

## 3. 导出字幕

下载这次任务的原始时间文本，确认对应同一音频与原词。格式如下，三列之间是制表符，时间以秒计：

```text
甲	0.100	0.900
乙	0.900	1.300
```

```powershell
python tools/lyrics_srt.py finalize --job "work/song/alignment-v1" --tsv "work/song/raw-timestamps.txt" --out "work/song/subtitles-v1"
```

输出 `lines.srt`（按原词逐句）、`words-raw.srt`（原始字/词时间）、`audit.json`、`timings.json`、原始 TSV 和哈希回执。英文等内容可能以词为单位，不能把一个词按字符均分后自称每字识别准确。缺字、越行、倒序、非法时间会停止；零时长、重叠和超过 2 秒单元会记录而不伪造修补。相同长度的文字偏差按位置恢复原词并逐项记账，它不会修正歌手唱错的声音。

剪辑先用 `lines.srt`，在项目配置中指明它属于整首歌曲时间轴。字级零时长在播放器中可能不显示；整句也为零时长时，当前组装器会拒绝，需要听审另存修订。原 TSV 只提供格式和冻结输入检查，工具不能自行证明你下载的是正确任务。

## 实测边界

2026-09-15 一首中文歌曲：74.6135 秒带伴奏原曲、20 行 140 字，一次任务实扣 4 RH 币；平台 `taskCostTime` 为 19 秒，上传开始到下载完成为 43.577 秒。字序覆盖 140/140，但有 5 个零时长字和 1 个 7.44 秒长单元，负时长/重叠/越界均为 0。使用方认为已够用；没有逐字人工校准全部边界。

[筛选后的数据](../data/lyrics-alignment-sample-001.json)保留这一条的费用与瑕疵，不公开原曲、完整歌词或账户信息。单样本不是通用价格、成功率或精确度保证。本次公共包装只做离线验证，没有新账号付费复跑。
