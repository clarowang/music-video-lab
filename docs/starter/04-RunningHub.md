# 用你自己的 RunningHub 账号接通 H3

**先离线准备，再在你自己的账号上试一镜。** 本包不携带原作者的API Key、工作流ID、登录态或三并发资格。原作者跑过这条模型路线，不代表你账号已满足模型/节点/API条件。

## 首次接通要核对什么

1. 你可以登录RH，并有自己可用的ComfyUI/API入口。按当前平台页面完成它要求的保存、运行或API准备；不要把本包当作绕过账号资格的方法。
2. 读 `data/h3-required-models.json` 和实际API图，确认当前服务有对应模型、LoRA、文本编码器、VAE和自定义节点。可以参考 [T8公开路线](https://www.runninghub.cn/post/2092541511882854402) 及 [T8代码](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)。加载自己的/获授权的工作流检查，不寻找他人私有应用的隐藏图。
3. `workflowId` 使用你自己拥有或获授权使用的ID。API图中的图片和音频最初是占位符，必须上传并改为服务器返回的 `fileName`。
4. 核当前实例价格、币余额与可并发数，先选一个3–6秒代表镜头。长段24G失败不等于模型不能做，但48G升档和重做都可能增加成本。

RH官方高级接口文档列出了完整 `workflow` JSON字符串字段。它和仅用 `nodeInfoList` 覆盖旧节点参数是不同入口；本包按完整图提交。该字段也不负责替你安装不存在的模型。见 [官方高级任务接口](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749013)。

## 本包的API工具能干到哪

`tools/rh.py` 提供四个独立动作：提交一个镜头、查询一次、成功后下载、给不确定提交绑定已核实的taskId。默认没有持续队列、定时轮询或失败重做。这样你的 Codex 能看清每一步，也能以后按你的需要接自己的编排器。

**本轮只做了模拟接口测试，没有拿新账号付费验收这个新便携接入器。** 工作流来自已实跑路线，网络字段核了当前官方说明；账号差异、服务版本和实时计费仍须你首镜验证。明确的报错交给你的 Codex，优先看缺节点、缺模型、输入引用、API权限或提交状态。

## 密钥放哪里

在你自己的终端设置 `RUNNINGHUB_API_KEY` 环境变量；不把密钥发进聊天，不写在 project.json 或工作流里。Windows可以让程序在本地隐藏输入：

```powershell
$rhSecret = Read-Host 'RunningHub API Key' -AsSecureString
$rhPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($rhSecret)
try { $env:RUNNINGHUB_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($rhPtr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($rhPtr) }
```

这是当前PowerShell进程的环境变量：从这个终端启动脚本才会继承。另一个已打开的Codex进程不一定能读到，不能因此让你反复贴Key。也可以用你自己已有的本地密钥管理方式给执行进程注入。国际站可设 `RUNNINGHUB_BASE=https://www.runninghub.ai`；跨站账号不要想当然混用。

## 付费提交一镜

先让 Codex 读 `jobs/01/job.json`，给你看镜头、模式、864尺寸、时长、实例与估计费用。你批准后，将 `templates/approval.example.json` 复制到本批本地工作目录，填本镜 `job.json` 的SHA256、你的授权文字、金额、实例和 `execution_allowed=true`。

模板初始额度0、执行关闭。**批准金额是本地审计记录，不是RH服务器的扣费硬上限。** 单任务可能超过估计；如你要求严格金额封顶，先查平台是否提供硬限额，否则不要承诺“设了数字就不会超”。整批要另有总账，记录已花、已提交未结及预留；这个单任务脚本不会自动管理全账户三并发或总预算。

```powershell
python tools/rh.py submit --job "work/你的项目/batch-v1/jobs/01" --approval "work/你的项目/approval-01.json" --workflow-id 你的可用工作流ID
```

这一条会上传本镜参考图和驱动音频、发送一次生成请求。执行意图先写 `rh-state.json`，图绑定后保留 `submitted.api.json`，收到taskId马上存盘；不保存Key或临时下载链接。已有人声不会在这里重复分离。

[官方上传说明](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749007) 区分节点用的 `fileName` 和下载地址；临时URL不是长期素材库。下载后保留本地付费原片。

## 查询和收片

```powershell
python tools/rh.py query --job "work/你的项目/batch-v1/jobs/01"
python tools/rh.py download --job "work/你的项目/batch-v1/jobs/01"
python tools/studio.py deliver --batch "work/你的项目/batch-v1" --id 01 --raw "work/你的项目/batch-v1/jobs/01/native.mp4"
```

前两项按 [官方V2查询](https://www.runninghub.cn/runninghub-api-doc-cn/api-425767306) 读取同一taskId。查询是一次快照，不会等到自动结束；让 Codex 适当间隔查询，或你稍后再叫它收片。下载只下载已成功产物，不会重付生成费。费用字段缺失留null，随后在RH记录里核实际消耗。

工具没有修改/取消他人任务的动作。需要停止已提交的付费任务时，在你自己的RH任务页面取消并查终态/费用；不要以关闭本地聊天等同取消云端任务。

## 异常恢复

- **提交超时**：先读 `rh-state.json`。`SUBMIT_UNCERTAIN`不表示未提交，查本账号任务列表与提交时刻；确认对应taskId后执行 `recover --job ... --task-id ...`，再query。不要直接重发。
- **上传失败、尚未create**：状态的 `create_attempted=false`可作为证据。保留这次失败记录，让Codex准备新尝试目录/编号；不删账伪装首跑。
- **421/并发满**：账户可能已有其他任务。等空位，核拒绝是否确实没创建，别同时再开一批抢槽。
- **显存不足**：保留失败任务、实际图和费用。是否缩短镜头、改更省显存接法或用plus，先说具体影响；不偷换小分辨率冒充成功。
- **下载中断**：`.download-part`是未完成文件，核完再移开它重下；不重新生成。`native.mp4`存在但没有匹配哈希时先检查，不覆盖。
- **少帧或尺寸异常**：`deliver`会拒绝；看原片的视频帧数/尺寸，别拿音轨长度或文件名1080替代证据。

只拿到一种“AI应用”界面时，本包并不保证能获取它的工作流。可转用本包已公开的API图和你有权使用的执行入口；需要鼠标画布时，让Codex按当前插件UI重建/导出并检验，不能声称本包API图已验证可直接拖入所有画布。
