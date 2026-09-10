# 本地检查工具

需要Python 3.10+及PATH中的`ffmpeg`、`ffprobe`。不需要Python第三方包，不会调用RH。

```sh
python tools/media_audit.py inspect assets/videos/singing-native.mp4 --audio-seconds 9.2
python tools/media_audit.py frame assets/videos/singing-native.mp4 --at 4.5 --output local-output/frame.png
python tools/build_gallery.py
python -m unittest discover -s tests
```

`inspect`报告画面尺寸、实际解码帧数、帧率、视频时长、音轨时长、SAR/DAR及音频覆盖情况。视频时长按逐帧PTS与最后一帧时长计算；若无法确定则留空，不把容器总时长冒充视频时长。它不评价口型、卡顿感或美观。

`frame`准确寻到指定秒数后抽一帧，不添加美颜或超分。`build_gallery.py`根据`data/samples.json`重建离线HTML，媒体都是仓库内的相对路径，没有外部脚本和追踪器。并排播放用于看观感，浏览器启动差异不参与口型测量；逐字判断请单独播放并开声音。

文件默认不覆盖，检查已有结果后再选择新输出名。生成API图也只写JSON，实际付费提交由使用者自己的平台入口完成。

## 单人唱歌准备与交付

新增工具与旧图库/抽帧工具分开，完整步骤见 [生产指南](h3-production.md)。

| 工具 | 用途 | 是否联网或消费 |
|---|---|---|
| `prepare_singing.py` | 读取本地人声WAV采样数，构建864原生＋FFN4＋中性提示API图 | 否；只生成JSON |
| `finalize_singing.py` | 下载后一次普通放大、30fps适配、最小裁尾和接原曲，并检查成片 | 否；调用本机FFmpeg/FFprobe |
| `singing_timing.py` | 两个工具共享的采样数、帧数与哈希计算 | 否 |

```sh
python tools/prepare_singing.py --vocal-wav local-inputs/vocal.wav --image portrait.png --audio vocal.wav --output local-output/singing.api.json
python tools/finalize_singing.py --video local-inputs/h3-native.mp4 --mix local-inputs/mix.wav --output local-output/1.mp4
```

两个阶段使用同时间线、同起止的人声与原曲切片。生成平台的输入引用由你自己的运行端提供，工具不会读取账号凭据。最终的 `*.delivery.json` 记录精确时长、原片/原曲/成片哈希、解码和音轨匹配；它不能判断逐字嘴型或审美。

发布时19项离线检查通过，包含实际FFmpeg转换的末帧舍入和短片拒绝；另用一条已付费原生片验证，结果与此前交付逐字节一致。验证范围见 [包装核验](../data/h3-production-verification.json)。运行测试如提示跳过FFmpeg部分，则只完成了其余检查。
