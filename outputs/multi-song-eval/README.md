# 多曲评测：基线 vs 当前最优路线（2026-11-18）

**结论**：在 25 段公开数据上，当前"最优路线"没有普遍胜过基线。只有在双方都没见过的 MAESTRO 测试曲上，钢琴 B 小幅领先（F1 0.983 vs 0.975）；在 BabySlakh 上，基线三轨全面领先。但 BabySlakh 来自 YourMT3 的训练集，这部分结果偏向基线，**不能据此判定 MuScriptor 贝斯/鼓更差**，只能说明这份数据无法证明它更好。单曲《唯一》上贝斯 25%→72% 的提升仍只是单曲结果，需要真实录音的多轨数据来复核。

## 1. 数据

| 来源 | 段数 | 内容 | 说明 |
|---|---|---|---|
| BabySlakh（Slakh2100 train 的 Track00001–00020） | 20 | 每首取 30–90 s 的 60 s 窗口，合成混音 | 钢琴 19 首、贝斯 19 首、鼓 19 首；参考为逐乐器 MIDI |
| MAESTRO v3.0.0 test split 最短 5 首 | 5 | 整首真实钢琴录音（66–125 s） | Scarlatti K.525、K.9，Rachmaninoff Op.32 No.8，Schubert Op.90 No.4，Chopin Op.10 No.9 |

数据只在本地，不上传仓库（`work/datasets/`、`outputs/runs/multi-song-eval/`）。

## 2. 路线与指标

- **基线**：YourMT3 `yptf_moe_nops` 整曲转写。
- **最优**：钢琴换成钢琴 B（BS-RoFormer SW 分离 → Transkun 2.0），贝斯和鼓换成 MuScriptor Medium，其余轨沿用基线。
- **主指标**：一对一匹配，同类别同音高（鼓：同 GM 键位），起音误差 ≤ 50 ms，报告合并全部歌曲后的 micro F1。
- **鼓补充指标**：
  - kit-piece：把 GM 键位归并成底鼓、军鼓、踩镲、通鼓、镲片后再匹配。
  - kit-only：在 kit-piece 基础上，再从参考和预测里去掉架子鼓以外的打击乐（铃鼓、沙锤等）。Slakh 鼓参考里这类音符占 24%（2096/8762）。

## 3. 结果（micro F1）

| 轨道 | 来源 | 歌曲数 | 基线 | 最优 |
|---|---|---|---|---|
| 钢琴 | MAESTRO | 5 | 0.975 | **0.983** |
| 钢琴 | BabySlakh | 19 | **0.891** | 0.794 |
| 贝斯 | BabySlakh | 19 | **0.978** | 0.697 |
| 鼓（GM 键位） | BabySlakh | 19 | **0.852** | 0.553 |
| 鼓（kit-piece） | BabySlakh | 19 | **0.933** | 0.648 |
| 鼓（kit-only） | BabySlakh | 19 | **0.944** | 0.762 |

完整数字（precision、recall、逐曲 F1、众数音高偏移）见 `results.json`。

## 4. 误差来源

1. **钢琴 B 在 Slakh 上主要多报音**。分离出的钢琴轨混进其他乐器，例如 Track00009 多出 241 个假音、Track00011 多出 176 个。Slakh 的"钢琴"还包括电钢、羽管键琴、Clavinet，并不是 Transkun 擅长的原声钢琴。Track00016（电钢 2 + 大钢琴）只有 0.27。在真实原声钢琴（MAESTRO）上，钢琴 B 5 首全部领先，幅度 0.001–0.015。
2. **MuScriptor 贝斯**有两首八度错误（Track00008、00019 众数偏移 −12）。另有几首同时漏音和多报音，召回率只有 0.49–0.53（Track00003、00005、00012），Track00003 还多报了 171 个音。
3. **MuScriptor 鼓的主要混淆**：
   - 漏掉闭镲 42（557 次）。
   - 把沙锤类打击乐 69（Cabasa）认成底鼓或踩镲（526 次）。
   - 把 40 认成 38（240 次），这一项 kit-piece 指标已经不计较。
   - 把 ride 51 认成底鼓（128 次）。

## 5. 必须知道的限制

- **训练集污染**：YourMT3 的训练数据包含 Slakh2100 train，BabySlakh 正好取自该划分。基线在这 20 段上的贝斯 F1 达到 0.978，接近满分，说明它见过这些歌。所以 Slakh 结果只能当作参考，不是公平对比。MAESTRO test 是双方训练时都没见过的划分。
- **Slakh 贝斯参考改低一个八度**：Slakh 贝斯 MIDI 比实际发声高一个八度。用 pYIN 对 5 首的贝斯分轨测音高，音频中位数约 MIDI 43，MIDI 文件中位数约 55。两条路线都输出实际发声音高，所以打分时 Slakh 贝斯参考统一 −12。改后基线 19 首的众数音高偏移全部是 0。
- **两首按原始音符打分**：Track00017 没有贝斯，Track00018 没有鼓。MuScriptor 替换入口要求基线恰好有一条贝斯和一条鼓，所以这两首拼接失败（退出码 1）。MuScriptor 本身已经跑完，打分直接读取日志里的原始音符，见 `results.json` 的 `muscriptor_scored_from_raw_log`。这暴露了入口的问题：遇到缺轨歌曲会直接报错。
- **Slakh 是合成音频**，与真实录音的音色、混音差异很大；MAESTRO 只有 5 首、只有钢琴。
- 只评估音符级 F1，没有做听感或人工修改时间评估。
- MuScriptor 权重为 CC BY-NC，仅限非商业使用。

## 6. 下一步

- 找真实录音、带逐轨标注、且不在 YourMT3 训练集里的多轨数据（例如 MedleyDB 或 URMP 中可用的部分，使用前须确认许可和下载量），复核贝斯和鼓。
- 钢琴 B 只在检测为原声钢琴时启用；电钢等其他键盘先沿用基线。
- 让 MuScriptor 入口在缺贝斯或缺鼓时只替换存在的那一轨，而不是报错。

## 7. 复现

在仓库根目录运行：

```bash
PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/prepare.py work/datasets/babyslakh/babyslakh_16k work/datasets/maestro-download outputs/runs/multi-song-eval/items
```

```bash
PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/run_routes.py outputs/runs/multi-song-eval/items
```

```bash
PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/score.py outputs/runs/multi-song-eval/items outputs/multi-song-eval/results.json
```

每段约 9 分钟（基线约 1 分钟，钢琴 B 约 5–9 分钟，MuScriptor 约 2–4 分钟），25 段合计约 3.5 小时。MAESTRO 的 5 首通过 HTTP 分段请求从官方 zip 里只取所需文件，脚本在本地 `work/eval-tools/maestro_fetch.py`（未纳入仓库）。
