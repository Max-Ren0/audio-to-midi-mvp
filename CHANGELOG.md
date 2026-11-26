# 版本记录

## v0.1.0-public.13 — 2026-11-26（RWC-P 路线选拔评测）

- 公开[评测摘要与复现](outputs/rwcp-eval/README.md)，包含冻结清单、计分规则、团体差值的 95% 配对区间与已知局限。音频、参考 MIDI、预测 MIDI 和运行产物留在 Git 忽略目录。
- 22 首调参入选 P2、B2、D2。50 首封存测试中，S3 相对全 YourMT3 的 S1，钢琴、贝斯、鼓 micro F1 分别高 26.47、49.63、4.38 个百分点。分数衡量与 RWC-P 参考的一致度，钢琴参考可靠性低。
- 测试集实际应用偏移均为 0 ms。S3、S5、S6 逐首输出一致，缺轨判断尚待验证。保留一键三轨默认路线与 public.11–12 的并行、节拍对齐行为。
- 同步 PRD 2.3 与 CONTEXT。冻结配置和评测规则的 SHA-256 在 rebase 前后相同。全量测试 234 项通过，模型资源预检通过。

## v0.1.0-public.12 — 2026-11-25（一键三轨可选节拍与小节对齐）

- `scripts/run_noto.py` 增加默认关闭的 `--beat-align`。沿用已有 librosa，使用节拍、频谱和和声重音推断小节，用 4/4 或 3/4 拍号及可变速度写出。检测或拟合速度图异常时仍发布原 120 BPM、4/4 网格，并在回执记录原因。
- 对齐只重写最终 MIDI 网格。30,720 PPQ 下的时间误差以对应速度的半个 tick 为限，慢速回归样本最大实测 35.81 μs。单独指定 `--quantize` 时才吸附起音，回执记录实际移动数量。
- `scripts/eval_noto_beat_align.py` 使用冻结清单的 22 首 RWC-P 调参曲，以 ±70 ms 一对一匹配评估漏掉和多出的拍点。小节线宏平均 F1 由 5.11% 升至 51.36%，节拍宏平均 F1 由 25.53% 升至 83.76%，BPM 平均绝对误差由 28.63 降至 27.26。8 首检测为约两倍于官方标注的 BPM，小节线数量为官方的 2.00–2.12 倍。
- 全量 209 项测试通过。真实调参曲的评分窗口均为 4/4。对齐保持默认关闭，待验证真实 3/4 曲目和音乐软件的节奏图导入。

## v0.1.0-public.11 — 2026-11-25（一键三轨可选并行）

- `scripts/run_noto.py` 默认串行。传入 `--parallel` 时，YourMT3 基线识别到钢琴后同时启动钢琴 B 和 MuScriptor，两路结束后合并。
- 任一路失败，或并行期间父进程收到 `SIGINT`、`SIGTERM`，入口会等两路结束再写失败回执并退出 `1`。最终 MIDI 只在未中断的成功运行中发布。
- 两路各支持 1 或 2 个计算线程，默认各 2。钢琴 B 报告分别记录锁文件和实际 `cpu_threads`。1 线程下的串并行一致性有桩测试覆盖，真实模型实测使用各 2 线程。
- 回执新增并行开关与执行状态、各阶段 UTC 起止时间和进程树 RSS 采样峰值。总耗时使用单调时钟。
- Apple M3 Pro 上，两个 60 秒片段分别用串行和并行各跑一次，基线和两路均为 2 个计算线程。同一片段的两份 MIDI SHA256 一致。

| 片段 | 串行墙钟 | 并行墙钟 | 耗时变化 | RSS 峰值（串行 → 并行） |
| --- | ---: | ---: | ---: | ---: |
| `slakh-Track00018`（实现者实测） | 424.82 秒 | 340.25 秒 | −19.9% | 2.89 → 3.38 GiB |
| `slakh-Track00001`（审核者实测，含鼓轨） | 443.11 秒 | 346.67 秒 | −21.8% | 2.78 → 4.11 GiB |

- `slakh-Track00018` 的 MIDI SHA256 为 `d0c56304c0438bf34ef6867083348a21c8a065df0d6d46b819122735a717f613`。`slakh-Track00001` 的 MIDI SHA256 为 `2c0a5d003faa6e18f529240a3ce41d2be91b5775670c67a3a5540b849cdcde1c`，逐轨 MIDI 消息也完全一致。计时和峰值为本机各片段的单次对照。
- 全量测试 195 项通过，0 项跳过。用桩子进程向父进程发送两种信号，检查失败回执只在两路都退出后写入。
- 修改范围包括一键入口、两路线程参数与进程监控、钢琴 B 锁文件、测试、README 与 CONTEXT。
- 记录提交：以本节所在提交为准。

## v0.1.0-rwcp-team.2 — 2026-11-26（审核后报告补录）

- 终报结论与计分口径补明，测试集 45 首偏移落在死区、5 首判为低置信，实际应用偏移全为 0 ms，两列分数逐项相同。
- 补充参考有其他 GM 打击乐但无底鼓、军鼓时的计分与存在统计差异，另报剔除 P058、P059、P091 的鼓分数。统一逐曲表空分图例，记录测试集未发现符合 P092 八度筛查特征的曲目。调参报告同步补注 S6 阈值全 0。
- 在原冻结结果上只读复核，更新两份本地报告及 PRD 2.2.1。终报 SHA-256 为 `ec76be3f8a3a750472891e3bd01f3503e4d387ec6eb8a53fa144744a7eacdbe9`，调参报告为 `d4775a76a612e791548216b251a37527ff1c156b1d67e61102d7ac1a433d3a73`。记录提交以本节所在提交为准。

## v0.1.0-rwcp-team.1 — 2026-11-26（本地冻结团体赛）

- [阈值](outputs/rwcp-eval/presence-config.json)与[组合](outputs/rwcp-eval/team-config.json) 先于读取 50 首测试音频和 MIDI 冻结。三轨调参各有 22 个正例、0 个负例，S6 阈值为 0，S3、S5、S6 的 MIDI 逐首一致。存在判断仍需专项验证。
- 校正后 micro F1，S3 钢琴／贝斯／鼓为 82.29%／76.19%／79.83%，比 S1 高 26.47／49.63／4.38 个百分点。配对歌曲 bootstrap 95% 区间均高于零，钢琴参考可靠性低。建议保留当前默认 S3。
- 四组均成功发布 50/50 首。实测批次合计 7.56 小时。双歌曲批次耗时上升，按用户指示等在跑阶段结束后复用检查点切回串行，最后一首在负载 ≤6 时启动。
- 复核 450 项缓存产物和 200 个 MIDI 哈希，逐首偏移与冻结文件一致。测试结果 JSON SHA-256 为 `546530ed6df907710d9322feb2223389f72b894224093fd97a5b2afa7590039c`。
- P092 的贝斯敏感性分析见[公开摘要](outputs/rwcp-eval/README.md#局限)。同步 PRD 2.2。详细报告和产物不入库。

## RWC-P 调参单项赛完成 — 2026-11-26

- 按早先冻结的 v2 完成 22 首 × 12 条路线，5 首复用试跑模型结果，新跑 17 首。复核 374 项缓存产物哈希。
- P2 钢琴 69.62%，B2 贝斯 68.85%（与 B7 打平后按耗时入选），D2 鼓 78.20%（与 D4 打平后按耗时入选）。成绩为校正后 micro F1，即与 RWC-P 参考的一致度。钢琴参考可靠性低。
- 22 首无偏移低置信曲目，只有 P029 应用 +59.8 ms。D3 两首空输出作为零预测计分。有效阶段累计 3.80 小时，新增实际工作墙钟 2.95 小时。
- 清单及冻结规则见 `outputs/rwcp-eval/`，调参结果 SHA-256 为 `dfe68885f4d8450d35ab2585f39e5ddfe6056e9250fb56b4b7cb8928f0dea8b6`，结果摘录见[公开摘要](outputs/rwcp-eval/README.md)。

## RWC-P 单项赛规则 v2 冻结

- 独立审核指出旧偏移搜索误选周期峰且整曲估计稀释局部漂移。v2 采用局部音频、窄搜索、峰值置信度、20 ms 延迟补偿及 50 ms 死区。
- 冻结调参赛主指标、逐曲胜负与耗时决胜口径。目标轨空输出按零预测计分并单列，失败不参与选拔。参数基于先前五首试跑，存在选择偏差。
- 此规则提交先于其余 17 首的模型运行。

## v0.1.0-rwcp-pilot.1 — 2026-11-26（RWC-P 五段路线试跑，本地分支）

- 冻结 72 首三轨齐全曲目，按 `DrumInformation` 分为 22 首调参、50 首测试。清单 SHA-256 为 `21a9a1879f33ec84d2191b3deab083f9f6cbe5ef0c0e887f366c0dc1578ff00e`。清单与首轮计分规则先于推理冻结。
- 五首调参曲目 × 12 个单轨候选共 60 个结果全部生成，团体方案和测试集留待后续。成绩称为与 RWC-P 参考的一致度，报告同时保留未校时／校时分数、底鼓与军鼓、贝斯精确与忽略八度 F1。钢琴参考可靠性低。
- 共计 50.9 分钟有效阶段墙钟。SW 平均 295.87 秒，混音 MuScriptor 153.71 秒，混音 YourMT3 66.65 秒。按 72 首外推串行 12.21 小时，理想双流水线 6.11 小时。后者未经并行实测。
- 原 SW 计时过程出现系统权限错误，改为直接读取子进程退出状态和原生 RSS 后复测。P5 修复证据计数的 JSON 序列化，触发条件保留。五段 P5 均走 P1，正向触发分支仅通过合成音测试。
- 全量测试 192 项通过，复核 85 项缓存产物哈希及分数汇总，`git diff --check` 无输出。结果 JSON SHA-256 为 `64ff5a35623211304207ff26afcc52a13d8b9e46a305cd28eafcb68d763b4bd7`。
- 新增 `outputs/rwcp-eval/` 和 `tests/test_rwcp_eval.py`，同步 PRD 2.1、评测集调研及 CONTEXT。报告和运行产物保存在本机，记录提交以本节所在提交为准。
- 待定是否削减候选、如何独立验证 P5 琴种判断，以及如何复核钢琴、贝斯参考和偏移异常的曲目。

## v0.1.0-public.10 — 2026-11-25（PRD 2.0）

- 按需求分析、定义问题、方案设计、测试验收和上线迭代重构 PRD。主用户收窄为想跟流行歌练贝斯、鼓或钢琴的学习者。
- 补充 LALAL.AI 调研和版本沿革。真值集逐轨 F1 为北极星及唯一上线门槛，最低线待首轮结果校准。差异化选定可信三轨草稿与可直接编辑。
- 新增评测集调研与路线选拔评测计划。RWC-P 主考，SMD、MDB Drums、FiloBass 单科诊断。按歌曲约 30% 调参、70% 测试，每首取 60 秒。先单项选路线，再封存测试集一次性评组合。
- 梳理 YourMT3 基线和专门路线的职责。【计划 2026-11-25】已确认先做钢琴 B 与 MuScriptor 并行，再做节拍检测与小节对齐，最后做乐器是否存在判断（依赖 RWC-P 调参集）。【进行中 2026-11-25】并行在独立工作区开发，默认串行，并行通过开关启用，耗时待实测。
- 修改清单：`outputs/Noto-产品需求文档.md`、`outputs/eval-dataset-research/README.md`、`CHANGELOG.md`、`CONTEXT.md`。
- 仅更新文档。RWC-P 下载与抽查事项进行中，路线选拔尚未运行。A/B 盲听和人工修订计时留到有资源时补测。
- 记录提交：以本节所在提交为准。

## v0.1.0-public.9 — 2026-11-25（缺轨入口、一键三轨、端到端评测）

- MuScriptor 贝斯和鼓缺轨修复（`4e4a79d`）
  - 贝斯与鼓各自处理，回执标记四种状态：替换 `replaced`、新增 `added`、保留基线 `kept_baseline`、无轨 `absent`。
  - 推理日志没有任何 `NOTE` 记录时，入口明确报错。
  - 回执新增 `track_note_counts`，记录最终 MIDI 中贝斯与鼓各自的音符数。
- 一键三轨入口 `scripts/run_noto.py`（`69d53a8`）
  - MP3 依次经过 YourMT3 基线、钢琴 B 与 MuScriptor 贝斯和鼓替换。基线未识别到钢琴轨时跳过钢琴 B。
  - 所有应执行的阶段成功后才发布最终 `noto.mid`。阶段失败时保留回执与日志。
  - `receipt.json` 记录运行状态、输入及模型哈希、实际命令与参数、Git 提交和工作树状态、阶段耗时、失败阶段及各轨来源和音符数。
  - 资源预检失败会写入失败回执并以退出码 `2` 结束，模型无需启动。
- 端到端评测 `outputs/e2e-eval/`（`1bc9ee5`）
  - 仅输入音频，8/8 段成功。micro F1 为钢琴 94.74%、贝斯 54.79%、鼓 49.80%。
  - 相对同批条件评测变化为 +0.00/−8.92/−0.94 个百分点。贝斯和鼓的降幅全部来自参考缺失类别中的误报。
  - 单段处理耗时为音频时长的 2.68–10.93 倍，钢琴 B 占合计耗时的 58.4%。逐段结果和阶段耗时见 [端到端评测报告](outputs/e2e-eval/README.md)。

| 现象 | 原因 | 解决 |
|---|---|---|
| 缺贝斯或鼓的样本拼接报错 | 旧入口要求基线恰好各有一条贝斯和鼓轨 | 分别处理两类轨道，按基线轨和预测音符决定替换、新增、保留或留空 |
| 零 `NOTE` 日志静默成功 | 引擎退出成功后，入口没有检查日志是否包含音符记录 | 解析和拼接前检查 `NOTE` 记录，缺失时明确报错 |
| 回执未标记未提交改动 | Git 提交号只能定位已提交的版本 | 增加 `git_dirty`，在运行开始时记录工作树是否有未提交改动 |

- 独立复核：三段均由 Codex 执行、Claude 独立只读审核。S1、S2 各返工 1 轮，S3 未返工。
- 审核者根据回执和最终 MIDI 重算 S3 评分，结果与交付 JSON 一致。
- PRD 已同步。作品集网页与 `gh-pages` 未同步，留待后续。
- 修改清单：`scripts/run_muscriptor_bass_drums.py`、`src/audio_midi/muscriptor_routing.py`、`tests/test_muscriptor_routing.py`、`scripts/run_noto.py`、`src/audio_midi/one_click.py`、`tests/test_run_noto.py`、`README.md`、`outputs/muscriptor-route/使用说明.md`、`outputs/e2e-eval/`（`README.md`、`results.json`、`run_e2e.py`、`score_e2e.py`）、`tests/test_e2e_eval.py`、`outputs/Noto-产品需求文档.md`、`CHANGELOG.md`、`CONTEXT.md`。
- 运行产物（MIDI、回执）不入库。
- 遗留：样本少，训练数据可能重叠。空类别误报需要增加乐器是否存在的判断，钢琴 B 是耗时瓶颈。听感和人工修改时间仍待测。
- 记录提交：以本节所在提交为准。

## v0.1.0-public.8 — 2026-11-24（竞品对比）

- 新增竞品对比 `outputs/competitor-analysis/README.md`：
  - Audio Jam 侧重分轨跟练，灵谱提供网页改谱与多轨导出；以 Moises、RipX DAW、NeuralNote v2 分别参照练习、逐音编辑和 DAW 工作流。
  - NeuralNote v2 与 Noto 贝斯/鼓替换路线同属 MuScriptor 家族；差异可从按乐器组合多模型、统一逐轨评测口径和交付流程验证。
  - 区分公开调研、仓库历史实测和推断；拟用保留未经编辑首稿的同片段对照与人工修改计时验证三轨草稿是否省工。
- 校正 CONTEXT：Audio Jam 美区 App Store（id6745493736）Pro 周付 $6.99、月付 $12.99，年付有 $29.99 和 $39.99 两种条目（2026-11-24 查看，以商店实时为准）；灵谱首页无标价，按转录时长充值、新用户送 10 分钟，具体价格未见；历史批测包含 BabySlakh 60 秒片段与 MAESTRO 约 66–125 秒整曲，每个样本约 9 分钟。
- 独立复核：Codex 执行、Claude 独立审核，返工 1 轮。主要补充 NeuralNote v2 的底层模型 MuScriptor，并纠正 Audio Jam 定价周期。
- 修改清单：新增 `outputs/competitor-analysis/README.md`，更新 `CHANGELOG.md`、`CONTEXT.md`。
- 仅文档变更；作品集未改，无需同步 gh-pages。
- 记录提交：以本节所在提交为准。
- CONTEXT.md 移除求职相关内容和求职材料的本地路径，只保留项目信息（git 历史中的旧版本仍可见）。

## v0.1.0-public.7 — 2026-11-18（简历附件作品集 PDF）

- 新增 16:9 八页作品集 PDF，用作简历附件，内容按当前进度编写：需求与 MVP 三轨、方案、贝斯迭代、多曲评测、独立复核与版本管理、反思。
- 源文件 `outputs/portfolio-pdf/index.html`，用 Chrome headless 打印；PDF 存于 `../作品集/Noto-音频转MIDI-作品集-2026-11.pdf`（不入库），旧版 PDF 保留。
- 验证：用 PDFKit 逐页渲染检查；共 8 页，960×540 pt，两处链接可点击。所有数字均与 CHANGELOG、多曲评测 results.json 和贝斯迭代报告核对过。
- 记录提交：以本节所在提交为准。

## v0.1.0-public.6 — 2026-11-18（多曲评测）

- 新增多曲评测 `outputs/multi-song-eval/`：BabySlakh 20 段（合成多轨，60 s 窗口）+ MAESTRO v3 test 最短 5 首（真实钢琴整曲），逐轨比较基线 YourMT3 与当前最优路线（钢琴 B + MuScriptor 贝斯/鼓）。
- 结果（micro F1，基线 → 最优）：MAESTRO 钢琴 0.975 → 0.983（5 首全部提升）；BabySlakh 钢琴 0.891 → 0.794、贝斯 0.978 → 0.697、鼓 0.852 → 0.553（kit-only 0.944 → 0.762）。BabySlakh 取自 Slakh train，YourMT3 的训练数据预设包含这一划分；本次所用权重的训练曲目未逐一核实，结果可能偏向基线，不作公平对比；MAESTRO 是官方测试集，各模型是否见过这些录音未核实。按参考乐器列表选轨，属条件评测。
- 同步：README 概览新增多曲结果表；作品集"验证结果"新增多曲区块；PRD 1.2 → 1.3（P0 状态、8.1、8.4、9）；CONTEXT。

| 现象 | 原因 | 解决 |
|---|---|---|
| 第一次准备数据时参考里没有任何音符 | BabySlakh metadata 中所有 stem 都标 `audio_rendered: false` | 改为按 stem WAV 是否存在筛选 |
| 两条路线的贝斯 F1 都接近 0 | Slakh 贝斯 MIDI 比实际发声高一个八度 | Slakh 贝斯参考 −12；pYIN 测频与基线偏移两组证据，脚本 `bass_octave_check.py` |
| Track00017/00018 的 MuScriptor 退出码 1 | 替换入口要求基线恰有一条贝斯和一条鼓，这两首分别缺贝斯、缺鼓 | MuScriptor 已识别完，打分读日志原始音符；入口改进列入下一步 |
| MAESTRO 下载 SSL 证书校验失败 | 系统 Python 找不到 CA 证书 | 用 `.venv` 中 certifi 的证书文件；只按 HTTP 分段取 5 首 |
| Codex 早先无法连接 | chatgpt.com 不可达 | 本次恢复连接，由 Codex 完成复核 |

- 独立复核：Codex 只读复核冻结提交 852119e，在内存中重跑打分，结果与 results.json 完全一致；提出 5 条意见（训练重叠表述过度、参考选轨的条件评测、鼓混淆缺少统计脚本、续跑以目录判断、降八度证据范围）。本版全部处理：
  - 改写报告措辞。
  - `score.py` 输出 `absent_category_extra_notes_total`。
  - 新增 `drum_confusions.py`、`bass_octave_check.py` 及其结果。
  - `run_routes.py` 改为按最终 MIDI 判断是否完成，失败目录改名后重试。
- 第二轮复核（e47eb99）：复算一致，又提出 5 条意见，本版已全部处理：
  - 对外页面的训练重叠措辞改为"预设包含、实际权重未核实"。
  - README 概览、作品集、PRD 的结果旁注明条件评测。
  - 原始日志回退改为要求推理完成且是缺轨拼接报错（`raw_fallback_ok`，打分和续跑共用）。
  - 收紧贝斯证据的总括句。
  - 作品集"暂未进行多歌曲验证"改为当前状态。
- 修改清单：`outputs/multi-song-eval/`（prepare.py、run_routes.py、score.py、drum_confusions.py、bass_octave_check.py、README.md、results.json、drum_confusions.json、bass_octave_check.json）、README.md、outputs/portfolio-preview/index.html、outputs/Noto-产品需求文档.md、CONTEXT.md、CHANGELOG.md。
- 不入库：数据集（`work/datasets/`）、转写产物（`outputs/runs/multi-song-eval/`）、MAESTRO 取数脚本（`work/eval-tools/`）。
- 遗留：没有真实录音多轨数据复核贝斯/鼓；没有不依赖参考乐器列表的端到端评测；MuScriptor 入口遇缺轨报错。
- 记录提交：以本节所在提交为准；外部状态：`gh-pages` 同步作品集。

## v0.1.0-public.5 — 2026-11-18（三轨范围表述补齐）

- 按独立复核意见补齐现行文档：PRD 1.2 项目阶段、P0 多轨转谱验收重点、8.5 第 3 条改为 MVP 三轨口径；README 明确吉他/弦乐"不计入 MVP 验收"，基线段与"尚未通过的验收"标注 v0.0 口径并新增三轨验收项。
- 复核：Codex 因本机连不上 chatgpt.com 两次失败，改由独立子代理只读复核 7fe03be；数字核对、doctor、139 项测试通过，提出的 5 处表述问题本版已修。
- 仅文档变更；作品集未改，无需同步 gh-pages。
- 记录提交：以本节所在提交为准。

## v0.1.0-public.4 — 2026-11-18（MVP 范围收窄 / 环境路径修复）

- MVP 先承诺钢琴、贝斯、鼓三轨；木吉他、清音电吉他、弦乐保留为研究轨道，照常输出但不计入 MVP 验收。依据《唯一》替换后逐轨 F1（钢琴 92.36%、贝斯 71.92%、鼓 55.99%，其余三轨低于 10%）。
- 同步：README 项目概览、作品集（FOCUS 标签、需求与范围、吉他/弦乐标"研究中"）、PRD 1.1 → 1.2（2.1、2.2、2.3）、CONTEXT。
- 环境：`.venv` 与 `work/sep-env` 共 64 个入口脚本 / .pth 仍指向迁移前路径，改为当前路径（本地环境，不入库；备份 `work/venv-path-fix-backup-20261118.tgz`）。

| 现象 | 原因 | 解决 |
|---|---|---|
| `.venv/bin/audio-midi` 报 bad interpreter，`import audio_midi` 失败 | 项目从 `Desktop/Codex项目` 迁到 `Desktop/AGENT/Codex项目`，入口脚本 shebang 与可编辑安装 .pth 未更新 | 备份后批量替换旧路径 |

- 验证：`.venv/bin/audio-midi doctor` 正常；`import audio_midi` 指向当前 `src/`；`work/sep-env` 中 transkun 2.0.1 可读取；`pytest -q` 139 项通过。
- 修改清单：README.md、outputs/portfolio-preview/index.html、outputs/Noto-产品需求文档.md、outputs/demo-synthetic/README.md、CONTEXT.md、CHANGELOG.md。
- 遗留：其他非标准环境（无 pyvenv.cfg 的目录）未逐一检查；项目再迁移需重做。
- 记录提交：以本节所在提交为准；外部状态：`gh-pages` 同步作品集。

## v0.1.0-public.3 — 2026-11-17（作品集对比演示）

- 作品集新增"听一听"区块：自写 30 秒片段（钢琴/贝斯/鼓）原曲与转写结果对照试听、同步卷帘对比、逐轨 F1、两个 MIDI 下载。
- 转写用 YourMT3 基线路线整段转写；逐音 F1（音高一致、起音 ≤50ms）：钢琴 83.9%、贝斯 75.6%、鼓 78.2%。合成干净音频、单样本，分数偏乐观，页面已注明。
- 版权：原曲为自写 MIDI，用 GeneralUser GS（许可允许商用）渲染；不含任何现成歌曲。
- 修改清单：`outputs/demo-synthetic/`（compose.py、README）、`outputs/portfolio-preview/index.html`、`outputs/portfolio-preview/demo/`、`.gitignore`（仅放行 `outputs/portfolio-preview/demo/*.mp3`）。

| 现象 | 原因 | 解决 |
|---|---|---|
| `.venv/bin/audio-midi` 报 bad interpreter | 项目迁移后 venv 入口和 .pth 仍指向旧路径 | 暂用 `PYTHONPATH=src .venv/bin/python -m audio_midi.cli`；venv 未修 |
| 推送 Actions 发布流程被拒 | 令牌无 `workflow` 权限 | 沿用 `gh-pages` 分支手动同步 |
| 独立核验发现 4 处页面/文档问题 | 加载失败无提示、进度线越界、播放状态不同步、复现步骤不全 | 650282d 修复，Codex 复验通过 |
| 复验发现快速切换播放器误报"无法播放" | 被互斥暂停中断的 play() 以 AbortError 拒绝 | 忽略 AbortError |

- 验证：Codex 独立核验 4b0cca2（音符、MIDI、分数、音频字节级复现通过），修复后复验 650282d；本地浏览器检查桌面/手机宽度、播放互斥与进度线。
- 遗留：未用钢琴 B / MuScriptor 最优路线；真实录音演示与多曲评测未做；venv 入口未修。
- 记录提交：以本节所在提交为准；外部状态：`gh-pages` 同步后上线。

## v0.1.0-public.2 — 2026-11-17（展示首页整理）

- 为公开展示整理首页：README 开头新增"项目概览"（痛点、流程、阶段性结果与限制、仓库导航），原技术说明保留在下方。
- 新增 GitHub Pages 在线作品集：`gh-pages` 分支只含 `outputs/portfolio-preview/index.html` 的副本（当前令牌无 `workflow` 权限，未用 Actions），地址：<https://max-ren0.github.io/audio-to-midi-mvp/>。
- 注意：改了作品集页面后需手动同步到 `gh-pages` 分支。
- 仓库设置：补充简介、主页链接与 topics（GitHub 设置，不在文件中）。
- 无模型、代码或评测变更；PRD 无需同步。
- 限制：已公开的提交历史中仍有本地路径和测试歌曲名，本次不改写历史。
- 分支 `docs/showcase-homepage`；记录提交以本节所在提交为准。

## v0.1.0-public.1 — 2026-11-17（仓库公开 / 文档同步）

- 按用户要求将 GitHub 仓库设为公开，更新 README 和 PRD 1.1 的仓库可见性；无模型或功能变更。
- 验证：GitHub 返回 PUBLIC，未登录访问 GitHub API 返回 HTTP 200；历史可达对象的媒体/权重文件名及常见凭据格式扫描未发现匹配。
- 限制：格式扫描无法保证发现所有敏感信息；项目记录和历史提交现已公开。
- 记录提交：以本节所在提交为准；外部状态：公开仓库，无新版本功能标签。

## v0.1.0-rc.1 — 2026-10-15（实验，质量未达标）

- 交付免费本地六类器乐路线：Transkun钢琴、原混音YourMT3电吉他、已有分离路线的木吉他/贝斯/鼓/弦乐；忽略人声。
- 同一开发片段固定映射评分整体F1约61.02%（v0.0约45.36%）；逐轨薄弱项仍未通过，开发分数不能充当盲测。
- 新增独立于标准的运行脚本、固定配置、输入及候选哈希验证、单轨试听和只读评测脚本；67测试通过。
- 记录两套逐轨方案，商业路线只作未测候选，不产生新增API费用；ADTOF、BasicPitch贝斯与起音回溯未胜出，如实保留对照。
- 额外曲内回归与冻结后独立验证的最终结果见outputs/v0.1/最终对照报告.md。

## v0.1质量升级规划 — 2026-10-15

- 记录原始候选错类现象，提出原混音/分离对照、专用模型与可用额度API的有限实验设计。
- 规定共享时间对齐、开发/额外验收片段、无标准泄漏、逐类与整体指标和独立验证。
- 仅为待评审规划；没有更新转谱产物或宣称准确率提升，未产生外部API费用。

## 标准 MIDI 校对与范围调整 — 2026-10-15

- 按用户指定改编标准对照最新多乐器产物，公开速度/起点校正与逐音匹配口径，报告六类器乐一致度。
- 后续忽略人声；固定版本后由独立验证子 agent 只读检查的流程写入项目规则与交付验收。
- 本轮不修改转谱算法，不覆盖用户媒体；结果不是多歌曲质量验收。

## v0.0.0-spike.2 — 2026-10-15

- 根据用户新MP3重做先分离再转谱的本地质量实验，用户批准更长耗时，生产默认限制不变。
- MIDI新增稳定乐器音色、Bank选择、名称与轨道音量；另交付采样音色WAV及主旋律钢琴MIDI/WAV。
- 修复中性弯音的渲染值域、同音重复起音丢失、相同时长分离文件的来源校验；59项测试及真实产物检查通过。
- 新结果591音符，电吉他只有1候选；尚无准确率或听辨通过结论，不作为正式v0.0.0。
- 备份更新v0.0规格中的音色交付需求，增加复现脚本、环境要求和来源记录。

## 质量反馈记录 — 2026-10-15

- 用户试听反馈现有MIDI无法辨认原曲；标记音乐可用性未通过，工程测试不能替代质量验收。
- 核对解码问题与轨道输出，调查音乐转谱工具及下一轮对比方法；本轮未修改算法或安装工具。

## v0.0.0-spike.1 — 2026-10-15

- 首个可运行离线实验版：校验MP3、YourMT3转录、七类映射、音符整理、Type1多轨MIDI、报告及评测命令。
- 用户授权的60秒歌曲片段最终端到端运行65.2秒，峰值约2.35GiB，得到1134音符和七类输出标签；准确率未经人工标注评测。
- 固定模型与依赖版本，下载校验权重；默认3.2GiB CPU内存上限，超时终止整个进程组，最多重试一次。
- 50项自动测试及真实产物复读验证；修复长音丢失与超时后代进程残留。
- 未完成音乐质量、可靠纯讲话检测及音乐软件验收，保留实验分支，不发布正式v0.0.0。

## 开发中：首个工程闭环 — 2026-10-15

- 增加MP3校验、Type1 MIDI导出、类别映射、音符整理、限时和有限重试、命令入口与音符评测。
- 首批41项自动测试通过；真实模型实验发现依赖不兼容，固定版本后重试，音乐质量尚未验收。
- 用户授权取歌曲60–120秒片段用于本地实验，媒体不上传。

## 实施计划 — 2026-10-15

- 根据用户构建请求完成本机环境预检，编写分阶段实施与验收计划。
- 固定MP3≤180秒、七类目标与正式版本验收条件；产品代码与模型实测尚未开始。

## 规格文档修订 — 2026-10-15

- 按用户要求为 v0.0-spec.md 新增版本维护与 GitHub 同步一节。
- 明确提交与上传流程、阶段标签、正式版本验收条件、验证记录和回退规则。
- 验证：原有正文保持不变；桌面修订稿与仓库副本一致；保留修改前备份。
- 未修改产品功能，未进行模型实测。

## v0.0.0-planning — 2026-10-15

- 保存竞品调研、MVP 范围、候选架构、异常处理和验证建议。
- 建立 Git 历史、私有 GitHub 仓库同步流程与版本标签约定。
- 状态：规划文档；无可运行的转录功能，无音频模型测试结果。


## RipX 分离对照启动 — 2026-10-15

- 固定同输入、同对齐的C0/C1基线复算；登记RipX分离及原生MIDI两项待测候选。
- RipX已保存未编辑工程，但窗口控制超时，尚无可评分导出，不作质量改善结论。
- 输入、参考、原生工程SHA与阻塞证据见outputs/ripx-comparison/。


## RipX单轨导出检查 — 2026-10-15

- 检查用户MID：只有一条Piano音符轨，未取得完整多轨；保存哈希与原样评分并明确不可作为RipX质量排名。
- 不改用户音符、标签或时间线；完整MIDI与WAV对照继续待补。


## RipX多轨重试评测 — 2026-10-15

- 读取用户更新MID，独立Voice可排除，器乐1339音；保存原始文件及去人声试听。
- 固定旧对齐下F1=2.07%，明确导出时间原点未验证、不当作分离器质量排名；木电未分，WAV路线待执行。


## 六轨分离候选更新 — 2026-10-15

- 按官方公开榜更新钢琴、贝斯、鼓、弦乐优先方法；木吉他、电吉他专用服务列为待测候选。
- 冻结后独立核对数值与服务参数通过；仅研究建议，无音频上传、付费或新质量分数。


## 六轨双方法实验：本地阶段 — 2026-10-15

- 本地SW新分离＋固定转谱对照；钢琴本片段F1从86.93%到99.63%，各轨改善不一致。
- 交付整轨开发选择的六轨阶段稿，整体F1 68.86%（原61.02%）；不是完整双Top候选实验或盲测通过。
- 六份独立参考MID加载/哈希与类别验证，4项新增测试先RED后GREEN，全套71通过。
- 专用服务缺API访问、Logic自动控制阻塞，均明确未运行；无新增付费/外部音频上传。

- 独立验证重算三版评分、整轨来源及交付文件通过；修复空/未知音色标准静默通过，增加3回归，全套74测试，评分不变。

- 2026-10-16：冻结ee56eb1独立复验通过（74测试、真实六参考、评分及产物哈希不变）。完成本地阶段交付；完整双候选尚待服务访问。

- 将已有本地预测按乐器/方法分开交付11个MID及逐轨评分，电吉他缺独立B明确标注；完整Top双候选仍未完成。

- 将既有SW总吉他原始电吉他14预测单独导出B，补齐12份本地逐轨A/B；专用Top实验仍未完成。

- c27e101独立验证12份本地逐轨A/B通过，新增电吉他B原预测和F1独立复核一致，ZIP/所有文件校验通过。

- 固定钢琴B，新增五轨错误诊断与分阶段提升计划；无新模型运行或MIDI改动，显式记录专用分离/转谱/时间切分待测边界。

- 五轨诊断与提升计划独立核验通过；补齐诊断复现参数，澄清贝斯已有起音检测，未变更预测或分数。

## 钢琴B固定入口 — 2026-10-16

- 固定SW/Transkun资产及唯一钢琴路径，严格验证缓存来源，禁止自动回退。真实复跑269音与已批准B一致，80测试通过。
- 历史多轨入口保留复现；新入口首次分离分支未重跑，权重许可边界保持。

## 鼓首轮研究升级 — 2026-10-16

- 13个鼓候选保留MID/试听，固定整键组合开发F1 56.00%→77.25%；规则冻结后同曲额外回归37.04%→44.07%，不宣称全曲/多曲通过。
- 钢琴B保持不变，六轨开发组合F1 68.86%→72.24%；其他四类不改。全88测试通过，无外部音频上传或新增付费。研究非商业许可边界保持。

- 最终冻结209109c独立复验通过：88测试、额外规则/来源/评分、六轨不变声部及42项交付包全部通过；缓存校验遗漏已修复。保留研究许可与同步/多曲/人工听辨限制。

- 澄清本轮60秒音频与历史60–120缓存的区别；历史额外/汇总分数仅作条件性附录，不作为本轮指定测试集或独立验证成绩。六参考MID实际为整曲，主评分仅取对应窗口。

- 固定后续评测顺序：0–60六轨逐轨确定→冻结完整版本→60–120六轨统一回归，保留历史已见及同步限制。

## v0.1.0-drums.2 — 2026-10-16（鼓研究版）

- 仅当前约0–60秒优化鼓，固定钢琴B和其余四轨；未用60–120继续调参。
- 实跑OaF/YODO/IDM（含失败共13模型进程尝试）；188参数候选、129不同MID。无新增费用、远程上传或训练。
- 固定多模型鼓件路由与一致性过滤：开发集80TP/93预测/94标准，F185.56%，上版77.25%。开镲/crash仍缺，不能称新曲准确率。
- 新增可复现固定组合函数和输入/缓存哈希校验的重建入口；最终鼓单轨与仅换鼓六轨、11段代表试听和全候选包本地交付。模型/输入/批量产物不上传。
- 独立验证在冻结提交后执行，结论另记录，不提前宣称通过。

- 鼓强化版d0c0b93已获独立只读验证：188候选/最终80TP93pred94ref、来源重解、五轨消息不变、100测试和ZIP/11WAV校验均通过，无阻断项。审查与剩余限制详outputs/drums-v2/独立验证.md。

## 鼓剩余错误诊断 — 2026-10-16

- 固定最终MID只读复算：放宽50到150ms无新增同键匹配，残余6组跨鼓件近时事件仅提示分类混淆。优先开镲/crash及鼓件级分离；新方案尚未推理，不宣称提升。
- 50efe99冻结后独立复算通过，原MID不变，官方F1仍85.56%。

## v0.1.0-openhat-experiment.1 — 2026-10-16（未提升鼓评分）

- 实测YourMT3／IDM／YODO已知开闭镲小样、新DrumSep六鼓件分离及同份hh输入，再补原SW鼓YODO对照。22次模型进程含失败，80规则候选／36不同MID；只用当前0–60，无训练、额外付费或外传。
- 修复YODO配置与权重通道不匹配导致NaN被过滤为零检测；新增非有限输出拒绝回归，先RED后GREEN，全102测试通过。旧零检测结论更正，原85.56组合不使用YODO所以不受影响。
- IDM宽门槛找回1/4开镲但新增5误击，其他模型无有效开镲净提升。保留85.56原版及所有五类乐器，生成三个代表测试MID／试听、hh与控制素材、完整候选包。冻结后进行只读独立核验，结论另记。

- 开镲实验4f22bbf已获独立只读核验：102测试、24小样参数、完整输入链、80候选来源／评分、22尝试与107产物／ZIP通过。无阻断问题，原85.56鼓及六轨不变；数值故障修复不等于音乐质量提升。

## 当前鼓选用版本显式冻结 — 2026-10-16

- 保留v0.1.0-drums.2最高开发F1鼓85.56%，增加带SHA256的选用清单；不移动旧标签、不改MID、不以开镲实验替换当前鼓。
- 记录鼓的实际逐鼓件融合路线与缓存重建边界，以及当前Demucs+pYIN贝斯的参数、41.38%开发F1和未解决限制。
- 本轮102测试通过；冻结后进行只读独立复核及GitHub远端检查，结果另记。媒体/权重/批量结果留本地。
- 6f106ad独立只读复核通过：实际哈希、缓存字节重建、鼓/贝斯最大匹配评分、六轨贝斯消息/tick及旧标签均一致。无阻断发现，未修改产物。审查记录随main上传，模型/媒体依旧留本地。

## 贝斯逐音诊断 — 2026-10-16

- 增加可选逐帧/切分trace与独立错误证据分析，不改默认音符输出。一次pYIN回放与当前贝斯MID字节一致，正式F1仍41.38%。
- 完整列出33FP/18FN、18匹配对、过滤和切分证据，生成102本地局部音频；记录固定规则下容差诊断、八度邻近候选和不确定性。
- 107测试通过；当前证据优先指向置信度过滤/起音解耦和部分切分问题，尚非修复收益或分离器因果证明。冻结后独立审查，结果另记。
- 冻结41f0bc9独立只读核验通过：旧/新contour相同帧和MID字节一致，3752帧、51错误和全部诊断数值、102片段PCM及118项ZIP均通过，无需修改产物。以v0.1.0-bass-diagnostics.1保存诊断里程碑，非贝斯质量升级。

## 贝斯逐步转写优化 — 2026-10-17（研究版）

- 固定Demucs/pYIN来源，新增局部置信度扩展与起音引导音高投票；原默认路径保持不变，预登记12候选后统一评估。
- 仅置信度39.56%低于原41.38%；仅起音49.32%；组合53.33%（20TP/39预测/36标准，19FP/16FN）。新增8命中同时丢失6，逐音变化完整记录，不声明新歌泛化。
- 新贝斯/试听和仅替换贝斯六轨另存；其他五轨及conductor原消息/tick不变，六轨F174.98%。113测试、12候选临时字节重建与错误输入/保护已有输出通过。
- 冻结后独立只读验证，结论另记；音频/权重/批量产物保留本地，代码和来源/评分/报告上传Git。
- 6e503f7独立只读核验通过：113测试、12候选来源/规则/独立评分、逐音变化、仅换贝斯六轨、62项包/5WAV均通过。无必须修正项，以v0.1.0-bass-refinement.1保存研究里程碑，保留基线。

## 贝斯音高模型与边界/分离对照 — 2026-10-17（研究版）

- 真实比较pYIN/CREPE full/PENN，神经模型未胜出；固定pYIN后测试起音/投票边界，再比较ft/SW。
- 最优原Demucs6s+pYIN+短窗起音/投票硬边界：53.33→62.34%，24TP/41预测/36标准，17FP/12FN。新增7丢3；六轨75.61%，其他5轨与conductor不变。
- 9模型进程、11候选；隔离兼容、初始解码、Hz转换和生成顺序偏离完整披露，评分前修正。116测试和临时重建通过，冻结后独立核验。
- 新MID/试听和研究锁另存，保留旧基线，不改旧默认runner；无训练/付费/外传/60–120。
- 冻结420e4a5独立只读核验通过：116测试、全部候选来源/评分与逐音得失、模型适配/时间格、保护轨和包均一致，无必须修正项。保存v0.1.0-bass-models.1研究里程碑。

## 2026-10-17 — bass acoustic evidence refinement (research)
- Added audio-supported same-pitch retrigger merging, neural-consensus additions and local onset refinement; 12 preregistered profiles, 4 distinct MIDIs, no new inference or paid calls.
- Seen 0–60 bass onset F1 62.34→70.59→72.22→75.00 (27 TP / 36 predicted / 36 reference; 9 FP / 9 FN). No previous matched reference lost. Octave profiles made no edits.
- New six-track F1 76.5625%, only bass replaced; other five tracks and conductor messages preserved. Old artifacts/locks retained; default runner unchanged.
- 120 tests and temporary three-stage byte/evidence/score rebuild passed. Frozen commit 3e3270d independently verified: own tempo parser/SciPy maximum matching, sources, byte rebuild, protected tracks, 44 clips, 5 re-rendered WAVs and 107-member ZIP passed; no blocking findings. No held-out or recording-truth claim.

## 2026-10-17 — bass multisource and note sequence trials (research)
- Added three-source evidence, source-local choices and note-level sequence decoding; kept the original 75% stream after negative source/fusion/sequence trials. Four isolated new pitch jobs, all single-attempt, no new separation/API/training.
- Selected evidence-constrained W64 additions: 29 TP / 39 predicted / 36 reference, F1 77.3333% vs 75%; two new reference matches, none lost, one new false positive. 10 preregistered IDs / 9 distinct MIDIs, full negative results retained.
- Only bass replaced in six-track output, F1 76.7283%; five tracks/conductor and old 75% artifacts unchanged. Added 18-event diagnostics and 84 local excerpts. No short-note or held-out accuracy claim.
- 124 tests and four-stage temporary rebuild passed. Frozen c0bafd9 independently verified: own tempo parser/SciPy matching, source hashes, 84 PCM excerpts, 12 WAV re-renders, unchanged old notes/protected tracks and 176-file ZIP; no required fixes.

## 2026-10-17 — freeze bass and diagnose strings
- Explicitly froze selected D75+W64 bass path via release/implementation/artifact hash guard; no bass or other existing prediction changed.
- Diagnosed current SW-other→YourMT3 strings: 3/39/7 strict F1 13.04%; segmentation-invariant absolute-pitch/time F1 29.37%, pitch-class/time 41.34%, activity-time 79.11%, not listening scores.
- Traced missing sustained high notes, a raw 23-note ascending run and 10 raw block-end terminations; decoder logs are evidence signals, not proof of root cause. No new inference or string edits.
- 127 tests and temporary diagnostic/freeze rebuild passed. Frozen 32ff5ea independently verified: own tempo/SciPy matching and interval-union metrics, freeze hashes, 9 source clips, 3 WAV re-renders and 29-file ZIP. No required fixes; supplement clarifies current boundary pitches differ from reference.

## v0.1.0-strings-bounded.1 — 2026-10-17
- Add bounded strings diagnostics: mir_eval onset/offset/chroma, reference coverage, 2×2 source/label comparison, fixed postprocessing and raw-token half-block controls.
- On this seven-note development excerpt only, exploratory A-M removes/merges 15 events (39→24), preserves three onset matches and changes onset F1 from13.04% to19.35%; missing high notes remain. No strings default or six-track replacement.
- All four raw captures completed; only3/10 other boundary notes follow the shifted grid,0/5 mix, so conditional overlap was not run. Preserve all negative results and disclose supplemental preregistration timing.
- 135 tests pass; no-forward temporary reconstruction checks MIDI/evidence/scores. Local media/bundle stay outside Git. Independent verification recorded separately before release.

## 2026-11-04 — Consolidate project location
- Move the repository, local model/runtime assets and outputs into Desktop/Codex项目/吉他产品/音频转MIDI; archive two early planning folders under the same product directory.
- Verify every file/link before and after moving and preserve existing product files. Keep old absolute paths as compatibility symlinks without duplicating data or changing frozen media/model hashes.
- Persist project-based, non-date directory preference in global/project AGENTS and add a product-directory entry guide. No model or musical-output changes.

## 2026-11-04 — Remove obsolete location symlinks
- Remove only five explicitly confirmed legacy symlinks; preserve all canonical project directories.
- Repair local virtualenv launchers/editable path with rollback copies, keeping frozen model/media content unchanged. Historical experiment scripts containing old absolute inputs require adaptation before reuse.

## MuScriptor Medium 同片段对照（研究）
- 运行自动识别和指定六类乐器两次，与冻结Noto六轨按同一参考与对齐进行比较；结果与限制见 outputs/muscriptor-comparison/结果.md。

## 用户 NeuralNote 导出评估（研究）
- 对用户提供的 MIDI 使用既有六轨参考和严格对齐评分，结果及限制见 outputs/neuralnote-user-eval/结果.md。

## 完整标准 MIDI 评估（研究）
- 按用户指定的完整标准 MIDI 直接重新评价 1.mid，记录固定对齐、音轨结果和限制；见 outputs/full-reference-eval/结果.md。

## 《唯一》MIDI 对照评估（研究）
- 对用户测试 MIDI 和指定标准进行起点对齐、六轨比较与限制记录，见 outputs/weiyi-eval/结果.md。

## 《唯一》新歌生成（研究）
- 分段运行固定钢琴 B、SW 弦乐和历史可运行 v0.1 多轨基线并拼接；记录与冻结鼓、贝斯研究版差异及评估限制，见 outputs/weiyi-noto/生成报告.md。

## MuScriptor 贝斯与鼓研究路线
- 新增基于本地 MuScriptor Medium 的贝斯、鼓转写与 Noto MIDI 安全替换入口；保护其他轨道，记录同曲评估、使用范围与权重许可。详 outputs/muscriptor-route/实验报告.md。

## Noto 作品集预览
- 新增本地项目案例预览，展示产品问题、处理链路、模型选择与带限制说明的单曲评测。

## 作品集模型反思
- 补充通用模型与音乐专业模型的取舍、模型组合及资源限制，明确微调属于未来探索。

## 作品集展示文案
- 删除预览及制作过程提示，调整为适合展示讲解的项目案例表述。

## Noto 产品需求文档
- 汇总当前目标、研究原型状态、各轨路线、评测验收和后续规划。
