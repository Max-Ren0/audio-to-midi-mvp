# 固定钢琴B实现

用户确认：2026-10-16。唯一默认钢琴新入口是 `scripts/run_piano_b.py`，不再以本曲评分自动挑其他钢琴模型。历史 `run_v01.py` 和旧配置保留复现用途，不会被偷偷改成新路线。

## 路径

MP3（≤180秒）→ FFmpeg整段44100Hz双声道、不裁静音 → 固定BS-Roformer SW分离 → piano.wav → Transkun预训练2.0（安装包2.0.1）→ 正常音符整理/Type1 PPQ480 MIDI → GeneralUser GS试听。

`config/piano-b.lock.json`固定SW权重、配置、推理wrapper哈希、MSST提交和Transkun权重/配置哈希及包版本。验证失败直接停止，无Demucs/BasicPitch回退。代码版本由Git提交固定；不代表全部Python传递依赖已逐字节锁定。参考MIDI不进入生成程序。

## 运行

仓库根目录、原有本地环境和模型已准备时：

```sh
.venv/bin/python scripts/run_piano_b.py /绝对路径/音频.mp3 --output-dir outputs/runs/piano-b/新目录
```

相同输入已有已核验SW缓存，可显式加：

```sh
--stems work/two-methods/sw-full
```

缓存必须绑定本次输入原文件SHA、SW模型/配置/上游版本、上游receipt及piano WAV哈希，并核验声道/采样率/时长。不同输入缓存或Demucs缓存不接受。首次没有缓存会新跑分离；复用缓存报告会明确不含分离耗时。

输出：钢琴-B.mid、钢琴-B试听.wav、运行报告.json。目录已存在直接拒绝；不改用户音频，不打开音频设备或界面。CPU2线程、单阶段1800秒、6GiB上限，沿用worker至多一次重试。节拍120/4拍只是编码默认；MIDI含GM乐器指令，不含真实采样。

## 本轮验证及限制

原60秒MP3复用SW缓存后真实重跑Transkun18.88秒，269音与原批准B逐音对象完全一致（含音高/时间/力度）；原B在开发标准上F1 99.63%，不是所有歌曲正确率。六项锁定/污染缓存测试先失败后通过，全套80测试通过。没有重新跑SW重型分离；新入口的首次分离分支尚未独立端到端重演，复用了先前已实测的同哈希分离wrapper。

模型/音色不推送GitHub，现有SW权重商业许可未完整核实，固定路线不等同商用许可获批。
