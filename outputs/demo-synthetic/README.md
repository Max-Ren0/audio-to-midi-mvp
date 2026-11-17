# 作品集对比演示（自写合成片段）

作品集"听一听"区块的素材与复现方法。

- 原曲：`compose.py` 自写的 30 秒片段（96 BPM，C–G–Am–F 循环 3 次），钢琴、贝斯、鼓三轨，共 301 个音符。没有使用任何现成歌曲。
- 音色：`work/models/GeneralUser-GS.sf2`（许可允许用于音乐制作，含商业用途）。
- 转写：基线路线 YourMT3 `yptf_moe_nops`，整段混音一次转写，CPU，用时约 25 秒。
- 评测：项目自带 `evaluate`，音高一致、起音误差 ≤ 50ms。

| 音轨 | 原曲音符 | 识别对 | 多识别 | 漏识别 | F1 |
|---|---|---|---|---|---|
| 钢琴 | 111 | 104 | 33 | 7 | 83.9% |
| 贝斯 | 56 | 34 | 0 | 22 | 75.6% |
| 鼓 | 134 | 104 | 28 | 30 | 78.2% |

限制：原曲是同一音色库合成的干净音频，比真实录音简单，分数偏乐观；只有一个样本，按项目规则属于合成样本，不计入真实歌曲评测。

## 复现（仓库根目录）

```sh
B=outputs/runs/demo-synthetic
PYTHONPATH=src .venv/bin/python outputs/demo-synthetic/compose.py $B
# 用 audio_midi.render.render_midi 把 $B/reference.mid 渲染为 $B/original.wav（tail 1.0s），再用 ffmpeg 编码为 160k MP3
PYTHONPATH=src .venv/bin/python -m audio_midi.cli transcribe $B/original.mp3 --output $B/yourmt3/result.mid
PYTHONPATH=src .venv/bin/python -m audio_midi.cli evaluate $B/reference.json $B/yourmt3/result.report.json
```

页面素材在 `outputs/portfolio-preview/demo/`：`original.mp3`、`transcribed.mp3`（转写 MIDI 用同一音色重新合成）、`reference.mid`、`transcribed.mid`、`notes.json`（卷帘与分数数据）。

注：`.venv` 入口脚本仍指向迁移前路径，暂用 `PYTHONPATH=src .venv/bin/python -m audio_midi.cli` 代替 `.venv/bin/audio-midi`。
