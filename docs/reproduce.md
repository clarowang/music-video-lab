# 怎样复跑

先分清两件事：复跑同样的方法，与逐像素复现同一条片子。平台版本、算子、输入和随机过程都会影响结果。本仓库提供参数和接口图；没有承诺在任意机器或RH账号上一键成功。

## 普通使用者：从作者公开入口开始

1. 打开 [T8 Dasiwa音频驱动V1](https://www.runninghub.cn/post/2092541511882854402)，通过平台正常功能建立自己的副本。
2. 使用自己有权处理的一张人物图和一段纯人声WAV。我们的唱歌测试为9.2秒；如果已有纯人声，不再重复分离。
3. 对照 [轻量配方](../recipes/h3-light.json)：576×1024、24fps、8步、视频/音频时钟12/3、seed42，音频模式`remix_source`、denoise=0。模型和LoRA名称见同文件。不要只凭“H3”标题认为模型相同。
4. 先核平台列出的节点与模型都可用，再按自己的额度生成一条。另一种子用20260910；高原生对照仅改864×1536，仍应重新审表情和嘴形。
5. 下载视频，使用本仓库工具检查帧数。用同一份原曲听看口型；不要用同步评分自动移动音轨后再宣称原始口型准确。

作者公开入口与图可能更新。若节点名称或字段变化，先比对原作者说明；我们的配方记录日期为2026-09-10。保存、发布、API资格和权限仍由RH决定。本仓库不提供别人的工作流载体ID，也不承诺一个API入口能执行所有工作流。

## 熟悉ComfyUI/API的人：生成独立节点图

需要Python 3.10+。`tools/build_h3_api.py`只写本地JSON，不联网、不上传文件、不生成视频。

```sh
python tools/build_h3_api.py --image portrait.png --audio vocal.wav --seconds 9.2 --output local-output/h3.api.json
python tools/build_h3_api.py --image portrait.png --audio vocal.wav --seconds 9.2 --width 864 --height 1536 --output local-output/h3-high.api.json
python tools/build_h3_api.py --image scene.png --mode drama --seconds 6.5 --prompt recipes/prompts/smile.txt --output local-output/smile.api.json
```

图里的图片/音频文件名应是**目标ComfyUI输入目录内可读取的文件名**；RH上传文件需要使用自己的平台引用，不能拿别人的上传缓存照填。

`workflows/*.api.json`是预先生成的相同格式示例。它们是`class_type/inputs`接口图，不带可拖拽的前端画布布局。普通ComfyUI“打开工作流”要求的前端JSON是另一种格式。需使用支持ComfyUI prompt API的执行端，或在作者画布中按配方设置。

运行端需已安装图中全部节点，并具备相应H3模型、LoRA、Qwen编码器、音视频VAE和注意力依赖。名称列表见 [环境记录](../data/environment.json)。本仓库不下载权重、不代装节点、不自动改生产环境。RH使用24G默认档完成了历史测试；这里没有可移植显存保证。

图中帧数先按`ceil(秒数×24)`保证请求覆盖音频，再对齐到`17n+5`。这在已测9.2秒与6.5秒上分别为226与158帧，与历史请求一致；其他边界时长的向上规则仅做过离线测试，不能替代实际输出核验。

## 超分和声音

本例后接的 [FlashVSR参数](../recipes/flashvsr-observed.json)只是冻结参数记录，未包装成公开的一键RH超分应用。先生成，再用自己的已验证超分链，保留两阶段文件与分别扣费。

576×1024经2倍超分得到1152×2048，再用普通等比缩放到1080×1920。普通缩放不生成细节。不要把这个步骤称为MiniMax未开放的官方2K重生成。

若最终使用完整歌曲，声音处理应保留原曲的速度和位置；先确认视频帧数覆盖音频，再做容器封装。示例片的原曲已在内部对齐到该片段起点；这里不公开完整歌曲或单独人声素材。想用同样的方法，请换自己的图片和音频。精选片用于看结果和复核工具，并不是原始训练/生成输入包。
