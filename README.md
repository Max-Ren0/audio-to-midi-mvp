# Noto · Audio to MIDI

把一首混合歌曲转为**按乐器分轨、可逐音编辑的多轨 MIDI**，给想跟流行歌练贝斯、鼓或钢琴的学习者一份可核对的草稿。

**[在线作品集 →](https://max-ren0.github.io/audio-to-midi-mvp/)** ｜ 状态：本地研究原型（无前端，不是成品）

## 项目概览

**需求假设**（2026-11-25）：自动谱错在哪看不出来，用户不敢信。音符与小节对不上，用户改不动。MVP 聚焦 A「可信的三轨草稿」和 B「拿来就能编辑」，两项需求仍待用户验证。北极星指标与上线门槛均为独立真值评测集上的逐轨 F1。

**怎么做**：

```text
本地 MP3 → YourMT3 基线 → 钢琴专用路线与贝斯／鼓重新转写 → 多轨 MIDI + 处理回执
```

- **MVP 先承诺三轨：钢琴、贝斯、鼓**，这三轨目前效果相对最好。木吉他、清音电吉他、弦乐仍在研究，照常输出但不计入 MVP 验收，结果可能缺失或错误较多；人声不输出。
- 不从零训练模型，而是**按乐器组合现有模型**，每次替换都和参考 MIDI 逐轨对比：
  - 钢琴：BS-RoFormer SW 分离 → Transkun
  - 贝斯 / 鼓：MuScriptor Medium 替换实验
  - 吉他 / 弦乐：仍在对照研究
- 全部本地运行，不上传音频。

**近期评测**

- **端到端（2026-11-25）**。只输入音频，8/8 段生成可回读 MIDI。钢琴、贝斯、鼓的逐音 micro F1 分别为 94.74%、54.79%、49.80%。贝斯和鼓相较同批条件评测的降幅均来自空类别误报。 [样本、口径与结果](outputs/e2e-eval/README.md)
- **RWC-P 路线选拔（2026-11-26）**。22 首用于调参，另 50 首封存测试。现有 S3 组合的钢琴、贝斯、鼓 micro F1 为 82.29%、76.19%、79.83%，相对全 YourMT3 高 26.47、49.63、4.38 个百分点。分数表示与 RWC-P 参考的一致度，不是准确率。钢琴参考可靠性低，鼓仅计底鼓与军鼓，所选歌曲均有三轨。 [评测与局限](outputs/rwcp-eval/README.md)

已提供[一键三轨入口](#一键三轨)，独立真值验收、目标音乐软件导入和模型商用许可仍待确认。早期路线对照见[单曲报告](outputs/muscriptor-route/实验报告.md)和[多曲条件评测报告](outputs/multi-song-eval/README.md)。

**仓库导航**：`src/` 核心代码 · `scripts/` 各路线入口 · `tests/` 测试 · `docs/` 固定路线说明 · `outputs/` 规格、PRD、实验报告（研究过程记录） · `CHANGELOG.md` 版本记录

---

## 技术说明（基线命令行）

本地 MP3 → 按乐器类别分轨的 Type 1 MIDI。无前端，使用现有音乐软件编辑结果。

**当前是实验版，不是通过音乐质量验收的 v0.0.0。** 已跑通用户指定歌曲的60秒片段；真实标注集 F1、人工修改工作量和音乐软件验收尚未完成。

## 工作流程

文件校验与16000Hz单声道解码 → 独立模型进程 → 保留原始乐器与人声标签 → 音符整理 → 多轨MIDI与处理报告。

以下为 v0.0 基线命令行的历史行为：七类目标为钢琴、木吉他、电吉他、贝斯、鼓、弦乐、人声旋律（后续已改为忽略人声，MVP 先承诺钢琴、贝斯、鼓三轨）。只输出有音符的轨道。出现某类标签不代表识别准确。

## 安装与运行

需要 Python3.11、uv、FFmpeg/FFprobe。依赖只安装在项目 `.venv`，权重只下载到项目 `work/`。

```sh
uv sync --frozen --extra model --extra dev
.venv/bin/audio-midi doctor
.venv/bin/audio-midi prepare
.venv/bin/audio-midi transcribe "/完整路径/输入.mp3" --output "outputs/runs/result.mid"
```

默认使用CPU和2个计算线程。`--device mps` 是实验选项，尚未完成本机验收。模型约536MiB；首次准备需要下载，转录时不向第三方上传音频。网络只用于安装依赖与准备模型。

普通转录的默认内存上限为本机成功实验峰值加30%后向上取整，见实验报告；可以通过 `--memory-limit-gib` 显式设置，其他机器应重新校准。最多重试1次，重试共享原截止时间。超时或失败退出码为2，不把半成品交付为成功。

输入必须为真正MP3，实际解码长度≤180秒。超长拒绝，不自动截断；已有结果或同名报告默认拒绝覆盖，只有显式加 `--overwrite` 才允许替换。

## 输出

- `result.mid`：Type1、480PPQ、按类别分轨；鼓用通道10，其余轨避开该通道。
- `result.report.json`：音符事件、缺失类别、解码警告、模型/权重版本、机器、耗时、内存和质量评测状态。
- `work/logs/`：本地模型运行日志，忽略上传。

这里的 `audio-midi transcribe` 使用固定 120 BPM、4/4。所有轨道按实际秒数换算到同一时间线，不吸附节拍。一键三轨入口的可选节拍对齐见下文。模型输出为二值起音，MIDI力度用80；鼓的50ms长度只是播放约定。MIDI不包含歌词、原唱音色、插件或原始音频。

## 音符评测

人工标注文件为JSON，音符时间单位为秒：

```json
{"notes":[{"category":"piano","pitch":60,"onset":1.0,"offset":1.5}]}
```

```sh
.venv/bin/audio-midi evaluate reference.json outputs/runs/result.report.json
.venv/bin/audio-midi evaluate-dataset manifest.json
```

清单例子（每首歌有唯一ID，路径相对清单文件）：

```json
{"samples":[{"id":"song-01","kind":"real","contains":["piano","vocal"],"reference":"reference.json","prediction":"result.report.json"}]}
```

上例仅演示格式，不是实际评测数据。主指标要求类别与音高相同、起音误差≤50ms，采用一对一最大匹配。逐类汇总TP/FP/FN；每类至少5首含该类的真实歌曲才能判定，合成样本不计入歌曲数。原曲不存在类别的多余预测单独统计。0.70/0.40为规格提议阈值，报告会标记尚待最终确认。

## 测试与复现

```sh
.venv/bin/python -m pytest -q
uv lock --check
```

模型：YourMT3 `yptf_moe_nops`，通过固定提交的 mt3-infer 调用；Transformers固定4.43.4，避免新版本移除旧T5接口。完整依赖锁定在 `uv.lock`。

使用模型自带32767采样点窗口（16000Hz下约2.048秒）与跨窗延音标签，避免再次套30秒外层窗口破坏延音。项目自己的音符解码保留闭合长音，并按规格补齐片尾未闭合音符。原始模型错误计数保留在报告中，不能据此承诺无漏音或截断。

## 一键三轨

使用已有本地环境和模型，从一首 MP3 生成可编辑的 `noto.mid` 与 `receipt.json`。

```sh
.venv/bin/python scripts/run_noto.py input.mp3 --output-dir /完整路径/新目录
.venv/bin/python scripts/run_noto.py input.mp3 --output-dir /完整路径/并行结果 --parallel
.venv/bin/python scripts/run_noto.py input.mp3 --output-dir /完整路径/小节对齐 --beat-align
.venv/bin/python scripts/run_noto.py input.mp3 --output-dir /完整路径/缺轨过滤 --presence-gate
```

单首输入最长 180 秒，使用 CPU，YourMT3 基线固定为 2 个计算线程（`--device cpu --threads 2`）。输出目录必须尚未创建。默认从仓库根目录读取本地资源。在独立检出目录运行时，传入 `--resources /完整路径/有模型资源的主检出目录`，并用已准备依赖的 Python 环境执行。MuScriptor 权重沿用本机默认位置 `~/Library/NeuralNote/models/muscriptor-medium-f16.gguf`。

YourMT3 先生成整曲基线；只有基线识别到钢琴时才用钢琴 B 替换。MuScriptor 根据音频补充或替换贝斯和鼓，保留未被替换的基线轨。吉他、弦乐等研究轨沿用基线，不计入 MVP 验收，人声不输出。处理过程只使用输入音频及本次推理生成的中间文件，不读取参考 MIDI 或参考乐器列表。

默认串行（`--no-parallel`）。启用 `--parallel` 后，如果基线识别到钢琴轨，钢琴 B 和 MuScriptor 会同时运行，结束后再合并 MIDI。两路默认各用 2 个计算线程，可分别用 `--piano-threads` 和 `--muscriptor-threads` 设为 1 或 2。钢琴 B 的阶段报告以 `cpu_threads` 记录实际值，`lock.cpu_threads` 保留锁文件默认值。两路各用 1 线程时，串并行一致性已通过桩测试。真实模型的 MIDI 一致性实测使用各 2 线程，1 线程的模型输出仍待验证。

2026-11-25 在 Apple M3 Pro 上对两个 60 秒片段各做一次串并行对照，耗时分别减少 19.9% 和 21.8%，同一片段的 MIDI 哈希一致，峰值内存上升。 [实测记录](CHANGELOG.md)

默认使用 `--no-beat-align`，保留固定 120 BPM、4/4。开启 `--beat-align` 后，沿用环境中的 librosa 检测节拍，通过频谱和和声重音估计 4/4 或 3/4。检测到的小节起点写成 MIDI 变速事件。拍号不确定时使用 4/4。音频太短、环境缺少 librosa、检测或速度图拟合出错时，仍发布固定网格 MIDI，并在回执记录原因。支持导入节奏图的音乐软件需同时导入 MIDI 的速度与拍号。

默认保持音符的原起止秒数、音高和力度。对齐后以 30,720 PPQ 写出，时间误差不超过对应速度下的半个 MIDI tick。慢速回归样本的最大实测误差为 35.81 μs。显式传入 `--quantize 1/4`、`1/8` 或 `1/16` 才会把起音吸附到当前 MIDI 网格。量化会改变起音和时值，可能跳过会打乱同音高事件顺序的起音，转写 F1 评测应保持量化关闭。

开启 `--beat-align` 时，使用 public.15 的组合规则替换 public.12 的速度选择。组合规则比较原节拍网格与两个半速候选，依据频谱起音、四拍重音和速度弱先验决定是否减半。回执的 `beat_alignment.tempo_selection` 记录候选 BPM、强度、选中的网格及理由。`beat_alignment` 也记录拍号、检测规律度、回退原因及量化结果。

规则用 RWC-P 22 首调参曲冻结后，对另 50 首测试曲单次评估。固定 120 BPM、public.12 与组合规则的小节线宏 F1 分别为 7.74%、47.00%、49.54%，节拍宏 F1 分别为 29.85%、82.15%、85.16%（±70 ms 一对一匹配）。相对 public.12，小节线 F1 的提升不显著，配对 bootstrap 95% 区间为 [−3.29, +8.36] 个百分点，跨过 0。倍速从 6 首降到 0 首，半速从 1 首增到 2 首。新增的 P046 本身是快歌，奇偶拍起音强弱交替明显，现有特征未能将它与应减半的倍速曲区分开。开关保持默认关闭。真实 3/4 和 DAW 导入仍待验证。[版本记录](CHANGELOG.md)

`--presence-gate` 为默认关闭的实验选项，可用 `--no-presence-gate` 显式关闭。开启后，钢琴、贝斯、鼓每分钟预测音符数分别低于 150、80、100 时移除该轨，回执记录每轨特征、阈值和判断。23 段测试的空类别误报从 1065 降到 215 个音符，误删 3／36 条真实轨。原 RWC-P 50 首测试误删 11／148 条，包含转写良好的稀疏声部。阈值来自约 60 秒的片段，一键入口按整首时长计算，长前奏或间奏会进一步降低平均密度。

启动后先写入 `running` 回执。串行逐阶段更新，并行两路结束后记录各自结果。回执记录实际命令、参数、Git 状态、是否实际并行（`parallel_used`）、各阶段 UTC 起止时间、墙钟耗时和进程树 RSS 采样峰值（`peak_memory_bytes`）。RSS 按进程求和，共享页可能被重复计入。成功时发布 `noto.mid`，记录各轨来源和缺轨，退出 `0`。任一路失败，或并行期间父进程收到 `SIGINT`、`SIGTERM`，会等两路结束，保留各阶段结果和日志，写入失败回执后退出 `1`。信号中断时回执还会记录 `interrupted_by`。资源预检失败会在模型启动前写失败回执并退出 `2`。参数错误或输出目录已存在时也退出 `2`。

## 尚未通过的验收

- 在独立真值评测集上，MVP 三轨（钢琴、贝斯、鼓）的端到端逐轨 F1 分别达到最低线。
- （v0.0 口径）七类在真实标注集上的识别质量、木吉他与电吉他的可靠区分。
- 纯讲话的可靠检测：当前只保证静音拒绝；语音可能被模型误识别为音符。
- 5–10首真实歌曲、每类别≥5首的人工标注与逐类F1。
- 用户选定音乐软件中的多轨打开和实际编辑。
- 其他机器、完整180秒输入、MPS运行的性能。

详见 [规格](outputs/v0.0-spec.md)、[实验报告](outputs/spike-report.md)、[版本记录](CHANGELOG.md) 与 [第三方来源](THIRD_PARTY.md)。

## 版本维护

每个可用阶段检查后提交并推送，重要里程碑加标签。实验版以 `v0.0.0-spike.N` 标记；正式 `v0.0.0` 须按规格通过验收。原始媒体、模型权重、凭证及本地运行产物不上传。

## 质量优先第二路线与音色试听

按用户新要求增加本地Demucs6s分离后转谱：pYIN处理人声/贝斯、BasicPitch ONNX处理钢琴、YourMT3处理吉他/鼓及other中的弦乐。该实验允许更久，默认生产transcribe仍保留原三倍时长限制。

MIDI写入每轨Bank Select、Program Change、instrument_name与音量控制。采样音色试听另存WAV；标准MIDI不包含真实乐器采样。可用scripts/reprocess_split.py执行实验，scripts/setup_quality.sh准备独立依赖。详情见outputs/v0.0-二次转录说明.md。

## v0.1 免费实验路线

v0.1使用六类器乐，忽略人声；两套方案见outputs/v0.1/两套逐轨方案.md。当前是RC实验，不能因整体分数提高就视为六类通过。原audio-midi命令是历史基线路线；本轮六类免费路线使用下述脚本。

在仓库根目录准备项目隔离环境（已有模型资产按THIRD_PARTY.md准备）：

```sh
sh scripts/setup_v01.sh
.venv/bin/python scripts/run_v01.py input.mp3 --config config/v0.1-free.json --output-dir outputs/runs/my-v01 --solo
```

输入MP3≤180秒；默认质量实验限时1800秒，CPU2线程，模型分阶段内存限制。输出目录必须不存在。该命令不读取标准MIDI、不调用音乐API。生成MID不内嵌采样，试听由本地音色库合成。首次所需模型/环境下载需要联网；推理本身本地完成。

仅评测时另行提供标准，所有候选共用已确认的映射（下例.9995/.14仅针对本项目既有AudioTrimmer片段，其他歌曲不能照搬）：

```sh
.venv/bin/python scripts/evaluate_v01.py reference.mid outputs/runs/my-v01/多乐器.mid --duration 60.0304375 --scale .9995 --shift .14 --output outputs/runs/my-v01/评测.json
```

`--candidates`仅用于以输入及候选哈希绑定的历史候选清单复原，耗时不包括历史推理；不冒充全流程耗时。`--stems`复用必须通过输入与六个stem的来源哈希校验。所有实际产物和权重留本地，代码/配置/摘要推送公开 GitHub 仓库。

## 当前固定钢琴路线（2026-10-16）

钢琴已固定为 **BS-Roformer SW → Transkun预训练2.0**。使用 `scripts/run_piano_b.py`；模型哈希、缓存校验、命令和限制见 [固定钢琴B实现](docs/钢琴B固定路径.md)。历史v0.1入口保留复现，不自动替换。

## 鼓轨首轮研究升级（2026-10-16）

钢琴B保持固定，鼓实验组合采用YourMT3细鼓键＋SW/ADTOF军鼓/闭镲。开发片段鼓F1 56.00%→77.25%，冻结规则的同曲额外片段37.04%→44.07%，尚未通过多曲质量验收。含非商业研究模型，不能直接当作商用默认。[报告与边界](outputs/drums/鼓轨升级报告.md)，[固定研究规则](config/drums-hybrid-research.json)。

`config/piano-b-drums-research.json`配`outputs/drums/六轨组装来源.json`供`run_v01.py --candidates`重建此次六轨；这是显式缓存组装，不是对任意新音频直接执行全部研究步骤。其他四类预测没有改变。每个鼓候选的MID/试听保存在本机outputs/runs/drums，不推送用户媒体。
