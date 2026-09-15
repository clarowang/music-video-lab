# 复制本文件夹，再放自己的材料

把本目录复制成包根 `work/你的项目/project`。在里面新建：

```text
inputs/mix.wav       完整原曲，48kHz PCM16
inputs/vocal.wav     同起点、同样本数的完整人声
inputs/lyrics.srt    UTF-8字幕，示例配置按完整原曲计时
images/01.png        自己确认的9:16图片，至少864×1536
images/02.png
prompts/01.txt       实际提交的逐镜提示
prompts/02.txt
project.json         本歌唯一图音绑定与采样区间
```

**JSON中的两个区间只是格式例子，不是你的歌曲分镜，也没有收费许可。** 根据实际歌曲改整张表；检查原曲/人声对齐后再记 `vocal_alignment_reviewed=true`。02展示静音驱动的只演镜头，不要求你的第2镜也只演。

图像/视频实际命令在包根README和docs中。本模板没有附人物图片、人声或整首歌，验证前必须放自己的材料。
