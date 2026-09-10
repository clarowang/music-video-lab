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
