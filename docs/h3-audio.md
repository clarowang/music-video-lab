# H3音频兼容入口

音频边界版本：`h3-pcm16-native-audio-v1`。图、模型、8步、FFN4、采样切点和交付配方保持原有选择。

## 提交前

H3的驱动文件统一使用**PCM16 WAV**。24位、32位或浮点WAV可以作为原件保存；用 `h3_audio.py` 另存兼容副本，上传返回的 `path`，再冻结其哈希和服务端文件名。不能先上传旧文件、只把本地清单改成新文件。

```powershell
python tools/h3_audio.py normalize work/song/inputs/vocal.wav --output work/song/inputs/vocal-h3.wav
```

已有PCM16原件会原样复用，并返回原路径。其他输入通过本机FFmpeg解码；保持采样率、声道、解码后的采样数与零点，不裁静音、不调整响度、不拉伸。不覆盖原件或硬链接；未知同名输出会报错。转换回执记录输入/输出哈希及量化误差，匹配旧回执可以恢复。超满幅浮点源拒绝静默削波，损坏、空或不可解码音频也停止。

转换只改变声音的数字表示，**不提取人声**。仍须按用途提供已分离人声或真正数字静音，最终回接原曲。压缩下载源的解码零点沿FFmpeg处理结果；是否同一首、同一版本、原曲与人声是否对齐，仍由输入检查确认。不能凭下载来源或WAV扩展名作结论。

`prepare_shot.py`、`prepare_singing.py`、`rh.py`会在付费提交前拒绝非PCM16驱动。直接调用图构建函数只得到图结构，不能跳过媒体预检。`studio.py`原有48kHz PCM16和30fps帧界限制保持；转换器保留采样率，不替代studio的48kHz要求。

## 收片后、接回原曲前

```powershell
python tools/h3_audio.py check work/song/native.mp4 --drive work/song/inputs/vocal-h3.wav
python tools/finalize_singing.py --video work/song/native.mp4 --drive work/song/inputs/vocal-h3.wav --mix work/song/mix.wav --output work/song/clip.mp4
```

H3驱动接法会在原片保留输入音频。`finalize_singing.py`先检查这条原片声音，再用原曲替换；`studio.py deliver`自动传入冻结驱动做比较。缺音轨、不可解码、非有限幅值和异常大幅值会停止。提供 `--drive` 时另查完整覆盖、零偏移波形和音量比例；原曲混音不能代替人声驱动参加这个比较。

当前分析为16kHz单声道，允许AAC小量变化：原片峰值不高于1.25、RMS不高于1.05；非静音驱动的RMS比在0.8—1.25、零偏移相关度至少0.97。数字静音另查接近静音。这些是拦截已知传输异常的工程阈值，**不是口型分数**，也不保证演唱、眨眼或闭嘴提示已落实。用于生成全新音频的其他接法需另定检查，不套用源音频一致性要求。

原片异常时保留taskId和文件，先诊断；本地整理失败不触发重生成。转换回执、原片音频检查与最终原曲音轨检查共同留存，不能只凭换好配乐后的成片声音判断模型输入正常。
