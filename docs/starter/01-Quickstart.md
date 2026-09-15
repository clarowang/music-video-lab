# 第一次使用

先让 Codex 读文件和检查环境，再花钱。推荐让它代你运行命令；下列命令从解压后的包根目录执行，项目路径带空格时保留引号。

## 需要你准备的东西

| 材料 | 用途 | 没有时怎么办 |
|---|---|---|
| 已确定的完整歌曲 | 最终声音与统一时间轴 | 先选定一版，生成后换歌会牵动口型和切点 |
| 与歌曲同起点的人声WAV | 让 H3 跟随发音 | 可自行用熟悉的剪辑工具提取；不用为了全自动重搭分离服务 |
| 歌词TXT和SRT | 准确文字、初步切点与字幕 | 可用[原词对齐工具](../lyrics-alignment.md)准备；原词管文字，模型给时间，异常另审 |
| 自己有权使用的人物参考 | 身份稳定 | 先做并确认一个人物母版；不要用本包作者的角色作默认模板 |
| 风格及额度 | 控制选择与消耗 | 先聊是近景唱、MV或混合，随后确认首个小样及整批额度 |

你不用先把每个参数填完。能从素材核到的信息由 Codex 读取；真正影响效果或费用的选择才问你。

## 工具环境

Python 3.10+，FFmpeg/FFprobe（含 libx264、ass/libass、xfade、tpad），Pillow 和 requests。没有本地GPU也能做准备与剪辑；H3 算力由你选择的服务提供。

先运行：

```powershell
python --version
ffmpeg -version
ffprobe -version
```

缺软件先让 Codex 给你明确安装清单，按你的设备和许可安装。FFmpeg 的官方入口是 [ffmpeg.org/download.html](https://ffmpeg.org/download.html)，本包不附第三方安装器。

推荐独立Python环境，以下以Windows为例，创建与安装需要你同意后执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools/studio.py doctor
```

后续命令里的 `python` 可换成 `.venv\Scripts\python.exe`；macOS/Linux 为 `.venv/bin/python`。当前完整便携演练在 Windows 完成，其他系统未在本轮执行。`doctor` 不查账号、不提交RH、不读取密钥内容。

## 先跑不收费的演示

```powershell
python tools/studio.py demo --out "work/my-first-demo"
```

几何测试图 → 生成驱动音频和工作流 JSON → 本机制造模拟原生片 → 1080整理 → 两镜合成、连续音乐和字幕。到 `work/my-first-demo/final/review.html` 看结果。这一步不调用图像模型或RH；几何图和测试音仅供验证接线。

如果目录已存在，请检查结果，或用 `work/my-first-demo-v2`。不要为了重跑删除已有付费原片。离线测试：

```powershell
python -m unittest discover -s tests -v
```

## 第一个正式项目

让 Codex 复制 `templates/project` 为 `work/你的项目/project`，放入自己的输入、图片和提示；由它根据实际材料改 `project.json`。先选一个3–6秒代表镜头完成跨账号试跑，确认画质与费用后再扩整首。

```powershell
python tools/studio.py validate --project "work/你的项目/project"
python tools/studio.py prepare --project "work/你的项目/project" --out "work/你的项目/batch-v1"
```

prepare 只在本机冻结图音、精确切片和生成JSON，不收费。每镜的 `jobs/01/job.json` 写明实际尺寸、帧数、模式与哈希。随后按 [RH接入](04-RunningHub.md) 跑你的账号。

下载真实原生片后：

```powershell
python tools/studio.py deliver --batch "work/你的项目/batch-v1" --id 01 --raw "work/你的项目/batch-v1/jobs/01/native.mp4"
```

所有镜头收齐，按 [剪辑说明](06-Editing.md) 合成。`clips/01.mp4` 等是给剪辑的片段；`final.mp4` 是整条候选成片，这两种交付不要混淆。
