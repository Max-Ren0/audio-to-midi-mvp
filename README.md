# Noto · Audio to MIDI

把一首混合歌曲拆成**按乐器分轨、可逐音编辑的多轨 MIDI**，为扒谱、练习和重新编曲提供起点。

**[在线作品集 →](https://max-ren0.github.io/audio-to-midi-mvp/)** ｜ 状态：本地研究原型（无前端，不是成品）

## 项目概览

**要解决的痛点**：歌曲音频方便听，却没法像 MIDI 那样逐个音符地看、改；扒谱和拆轨主要靠人工，费时间。

**怎么做**：

```text
MP3 → 声音分离 → 每类乐器用专门的模型转写 → 音符整理 → 多轨 MIDI + 处理报告
```

- 目标六类乐器：钢琴、木吉他、清音电吉他、贝斯、鼓、弦乐（忽略人声）。
- 不从零训练模型，而是**按乐器组合现有模型**，每次替换都和参考 MIDI 逐轨对比：
  - 钢琴：BS-RoFormer SW 分离 → Transkun
  - 贝斯 / 鼓：MuScriptor Medium 替换实验
  - 吉他 / 弦乐：仍在对照研究
- 全部本地运行，不上传音频。

**阶段性结果**（单曲实验，严格逐音 F1：音高、类别一致，起音误差 ≤ 50ms）：

| 音轨 | 改动 | F1 |
|---|---|---|
| 贝斯 | 换用 MuScriptor（《唯一》） | 25.45% → **71.92%** |
| 鼓 | 混合路线（开发片段 / 同曲另一片段） | 56.00% → **77.25%** / 37.04% → 44.07% |

这些只是单首歌上的研究结果，**不代表其他歌曲的效果**，也没有经过系统试听。吉他和弦乐仍有明显错误；多曲标注评测、统一的一键流程、模型商用许可还没完成。

**仓库导航**：`src/` 核心代码 · `scripts/` 各路线入口 · `tests/` 测试 · `docs/` 固定路线说明 · `outputs/` 规格、PRD、实验报告（研究过程记录） · `CHANGELOG.md` 版本记录

---

## 技术说明（基线命令行）

本地 MP3 → 按乐器类别分轨的 Type 1 MIDI。无前端，使用现有音乐软件编辑结果。

**当前是实验版，不是通过音乐质量验收的 v0.0.0。** 已跑通用户指定歌曲的60秒片段；真实标注集 F1、人工修改工作量和音乐软件验收尚未完成。

## 工作流程

文件校验与16000Hz单声道解码 → 独立模型进程 → 保留原始乐器与人声标签 → 音符整理 → 多轨MIDI与处理报告。

七类目标：钢琴、木吉他、电吉他、贝斯、鼓、弦乐、人声旋律。只输出有音符的轨道。出现某类标签不代表识别准确。

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

120BPM和4/4拍为明确标注的默认值，未实现拍速估计；所有轨道按实际秒数换算到同一时间线，不吸附节拍。模型输出为二值起音，MIDI力度用80；鼓的50ms长度只是播放约定。MIDI不包含歌词、原唱音色、插件或原始音频。

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

## 尚未通过的验收

- 七类在真实标注集上的识别质量、木吉他与电吉他的可靠区分。
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
