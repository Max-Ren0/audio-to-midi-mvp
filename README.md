# Audio to MIDI MVP

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
