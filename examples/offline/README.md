# 不收费的接线演示

[打开演示视频](final.mp4)：两段几何画面、合成测试音、标题与整句字幕，中间有8帧局部淡化。总185帧，6.166667秒，1080×1920/30fps。

用它判断文件能否读取、字幕能否合成、原曲区间能否连续铺放、帧数是否正确。这里没有调用 H3，没有真人、歌声或作者歌曲，因此不能判断 H3 人脸、口型或审美。

从仓库根目录复跑：

```powershell
python tools/studio.py demo --out "work/demo-v1"
```

完整中间项目与证据落入你自己的 work 目录；仓库只放最终演示和[简短核验](verification.json)。`review.html` 在你运行后的 final 文件夹内，双击即可打开，不依赖网页服务器。

程序新造的几何图、合成测试音与此演示视频采用 [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)。真实模型的历史样片位于另一个目录，按 [assets 的独立许可](../../assets/LICENSE.md)使用。
