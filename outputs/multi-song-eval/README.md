# 多曲评测：基线 vs 当前最优路线（2026-11-18）

**结论**：在 25 段公开数据上，当前"最优路线"没有普遍胜过基线。只在 MAESTRO 官方测试集的真实钢琴录音上，钢琴 B 小幅领先（F1 0.983 vs 0.975，5 首全部提升）；在 BabySlakh 上，基线三轨全面领先。BabySlakh 取自 Slakh2100 train，而本地 YourMT3 代码的训练数据预设包含这一划分，所以这部分结果很可能偏向基线，**不能据此判定 MuScriptor 贝斯/鼓更差**，只能说明这份数据无法证明它更好。单曲《唯一》上贝斯 25%→72% 的提升仍只是单曲结果，需要真实录音的多轨数据来复核。

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
- **这是"已知参考里有哪些乐器"的条件评测**：是否运行钢琴 B、MuScriptor，以及某首歌计入哪一轨的 F1，都按参考标注里的乐器列表决定。参考里没有的乐器类别，预测出的音符不计入任何 F1，单独统计在 `results.json` 的 `absent_category_extra_notes_total`：基线多出木吉他 11、弦乐 1 个音；最优路线另外在没有贝斯的 Track00017 上多出 58 个贝斯音。真实使用时不知道歌里有哪些乐器，端到端表现还需另测。
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

完整数字（precision、recall、逐曲 F1、众数音高偏移）见 `results.json`。Codex 对冻结提交 852119e 做了只读复核，在内存中重跑 `score.py`，得到的 JSON 与 `results.json` 完全一致。

## 4. 误差来源

1. **钢琴 B 在 Slakh 上主要多报音**。分离出的钢琴轨混进其他乐器，例如 Track00009 多出 241 个假音、Track00011 多出 176 个。Slakh 的"钢琴"还包括电钢、羽管键琴、Clavinet，并不是 Transkun 擅长的原声钢琴。Track00016（电钢 2 + 大钢琴）只有 0.27。在真实原声钢琴（MAESTRO）上，钢琴 B 5 首全部领先，幅度 0.001–0.015。
2. **MuScriptor 贝斯**有两首八度错误（Track00008、00019 众数偏移 −12）。另有几首同时漏音和多报音，召回率只有 0.49–0.53（Track00003、00005、00012），Track00003 还多报了 171 个音。
3. **MuScriptor 鼓的常见错误**（`drum_confusions.py` → `drum_confusions.json`）。统计规则：对每个参考鼓击，看 ±50 ms 内的 MuScriptor 鼓预测。有同键位的算对；一个都没有记为"附近无预测"；否则记录最近那个预测的键位。一个预测可能同时对应几个参考鼓击，所以下面只说明"附近出现了什么"，不等于模型把 A 听成了 B。8762 个参考鼓击中，4041 个附近有同键位预测。
   - 闭镲 42：附近无预测 557 次。
   - Cabasa 69（Slakh 鼓轨里的辅助打击乐）：附近出现的是底鼓 36 或闭镲 42，共 526 次（325 + 201）。
   - 军鼓 40：附近出现的是 38，共 240 次。kit-piece 指标不区分这两者。
   - Ride 51：附近出现的是底鼓 36，共 128 次。如果不先检查同键位、直接取最近的预测，Codex 复算为 131 次。

## 5. 必须知道的限制

- **训练集重叠**：
  - 本地 YourMT3 代码的数据预设（`work/mt3-infer/.../yourmt3/config/data_presets.py`）用 Slakh 的 train 划分训练（`slakh_final` 还合并了 validation），BabySlakh 正好取自 Slakh train。基线在这里的贝斯 F1 是 0.978，与"训练时见过"的推断一致，但高分本身不能证明这一点。本次使用的 `yptf_moe_nops` 权重具体用了哪个预设、哪些曲目，没有逐一核实。
  - MAESTRO 用的是官方 test 划分。上述预设训练时只用 MAESTRO 的 train 和 validation，Transkun 也按官方划分报告 MAESTRO 结果。但本次实际使用的各个权重，以及 BS-RoFormer SW 分离模型，是否接触过这 5 段录音，**未核实**。
  - MuScriptor 的训练数据与 Slakh 是否重叠，**未核实**。
  - 所以 Slakh 结果只作参考，不是公平对比；MAESTRO 结果相对更可信，但只有 5 首。
- **Slakh 贝斯参考改低一个八度**：在本次 19 段里，Slakh 贝斯 MIDI 比分轨实际发声高一个八度，所以打分时贝斯参考统一 −12。证据有两组：
  - 测频：`bass_octave_check.py` 用 pYIN 对每个时长 ≥ 0.2 s 的贝斯音测频，结果在 `bass_octave_check.json`。19 段中 18 段的"音频 − MIDI"众数是 −12，这 18 段里 −12 的占比都在 92% 以上（Track00019 只有 1 个音够长，Track00009 有 10 个，其余每段 32–159 个）。Track00012 测频不稳定，众数是 −43，判为测频失败；但基线在这一段 218 个参考音里有 214 个音高偏移为 0（按修正后的参考），支持同样的修正。
  - 基线偏移：修正后，基线在全部 19 段的众数音高偏移都是 0。
  - 修正只针对本样本；不代表所有 Slakh 贝斯轨都逐音验证过。Codex 复核时，其他类别的众数偏移都集中在 0，没有发现需要同样修正的证据。
- **两首按原始音符打分**：Track00017 没有贝斯，Track00018 没有鼓。MuScriptor 替换入口要求基线恰好有一条贝斯和一条鼓，所以这两首拼接失败（退出码 1）。MuScriptor 本身已经跑完，打分直接读取日志里的原始音符，见 `results.json` 的 `muscriptor_scored_from_raw_log`。这暴露了入口的问题：遇到缺轨歌曲会直接报错。
- **Slakh 是合成音频**，与真实录音的音色、混音差异很大；MAESTRO 只有 5 首、只有钢琴。
- 只评估音符级 F1，没有做听感或人工修改时间评估。
- MuScriptor 权重为 CC BY-NC，仅限非商业使用。

## 6. 下一步

- 找真实录音、带逐轨标注、且不在各模型训练集里的多轨数据，复核贝斯和鼓。URMP 已在 YourMT3 的部分训练预设里，不适合；MedleyDB 等候选使用前须核实训练重叠、许可和下载量。
- 做不依赖参考乐器列表的端到端评测：所有路线都跑，所有类别的误报都计入。
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

```bash
PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/drum_confusions.py outputs/runs/multi-song-eval/items outputs/multi-song-eval/drum_confusions.json
```

```bash
PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/bass_octave_check.py work/datasets/babyslakh/babyslakh_16k outputs/runs/multi-song-eval/items outputs/multi-song-eval/bass_octave_check.json
```

`run_routes.py` 可以重跑续跑：最终 MIDI 已存在的路线会跳过。MuScriptor 拼接失败但日志里有原始音符的，也算已完成。其他失败留下的目录会改名为 `*.failed-<时间>` 后重试。

每段约 9 分钟（基线约 1 分钟，钢琴 B 约 5–9 分钟，MuScriptor 约 2–4 分钟），25 段合计约 3.5 小时。MAESTRO 的 5 首通过 HTTP 分段请求从官方 zip 里只取所需文件，脚本在本地 `work/eval-tools/maestro_fetch.py`（未纳入仓库）。
