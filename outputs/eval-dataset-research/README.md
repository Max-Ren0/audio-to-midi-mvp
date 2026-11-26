# Noto 三轨评测集调研报告（钢琴 / 贝斯 / 鼓）

【调研 2026-11-25】资料来自公开网页、论文和 YourMT3 代码。调研时未下载新增候选。表内【页面】和【本地】指调研来源，【推断】指尚未验证的判断。

## 0. 核心结论

1. 本轮未找到同时满足流行风格、真实录音、三轨逐音真值且可排除训练重叠的公开集。**RWC-P 用于三轨路线的相对比较**。它有 100 首流行棚录和对齐 MIDI，许可 CC BY-NC 4.0。YourMT3 所查预设仅用于评测，MuScriptor 论文称其报告的模型未用 RWC-P 训练。RWC 论文记载原 MIDI 由专业人员在录音后转写，新版用自动对齐和人工核听修正时间，仍有漏音、错音和多余音。抽查后的评分约定见第 2 节。
2. 分乐器补充：**钢琴用 SMD**（Disklavier 演奏时同步记录的 MIDI，属于真正的真值，但曲目是古典）；**鼓用 MDB Drums**（真实多轨录音加人工标注，MIREX 2017 用过）；**贝斯用 FiloBass**（人工校验，但乐器是爵士低音提琴）。
3. 有三个新候选**不适合当真值**：
   - JazzSAMBA 的贝斯 MIDI 由 MuScriptor 自动转写得到，拿它评 MuScriptor 等于循环论证。
   - MulTTiPop 的 MIDI 来自 Lakh 的网友编曲加节拍对齐。MuScriptor 的合成训练数据用过 Lakh MIDI。
   - STAR Drums 的标签是自动转写，鼓声还经过重新合成。
4. 【计划 2026-11-25】上线按真值评测集逐轨 F1 判定。A/B 盲听在上线后、有资源时补测，MUSHRA、MOS 是备选。人工修改时间也留到有专家或目标用户参与时再测。


## 1. 候选核实总表

字段说明：乐器覆盖里 ✅ 表示有逐音真值，◐ 表示部分有或真值质量存疑，✗ 表示没有。重叠风险指"被评模型训练时见过这批音频或 MIDI"的可能性。

### 1.1 评测集候选

| 名称 | 乐器覆盖（钢琴/贝斯/鼓） | 真实还是合成 | MIDI 真值来源 | 风格 | 规模 | 能否拿到音频 | 许可 | 下载体积 | 与 YourMT3 / MuScriptor 训练的重叠风险 | 对 Noto 的适用度 | 来源（2026-11-25 查看） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **JazzSAMBA**（arXiv 2609.34931） | 钢琴✅ / 贝斯✗（MuScriptor 自动转写） / 鼓◐（仅异步录制部分有真值） | 真实棚录，有近距离话筒串音，提供 clean 和 bleed 两版【页面】；原声还是电声未查到 | 演示页写"Ground-truth MIDI for piano (and drums on async)"，表 2 注"remaining MIDI is from MuScriptor AMT"；采集方式未查到 | 爵士 standards（含小号、萨克斯） | 76 首、8 位乐手；优选 take 约 8.1 h，两层合计约 16.1 h | 已找到 Zenodo 发布记录，未实际下载 | 许可待核实 | 未核实 | 【推断】训练重叠风险较低，仍需核对实际权重（数据集晚于两篇模型论文），**贝斯是循环论证** | **中**：钢琴、鼓（异步部分）可用，贝斯不能当真值；风格是爵士，获取与许可待核实 | [arXiv](https://arxiv.org/abs/2609.34931)、[HTML](https://arxiv.org/html/2609.34931v1)、[演示页](https://pnlong.github.io/jazzsamba-demo/)、[Zenodo](https://zenodo.org/records/22943963) |
| **MDB Drums** | 鼓✅ | 真实多轨录音（MedleyDB 中的 MusicDelta 子集） | 人工标注：madmom 先检测起音，人工标类，专家交叉复核 | 多风格短曲 | 23 首、7994 个起音；6 大类或 21 细类 | GitHub 直接下载（含鼓分轨、混音和原始多轨） | CC BY-NC-SA 4.0 | 未查到 | YourMT3 预设中无 MedleyDB【本地】；MuScriptor 未提 MedleyDB，内部数据是否含有未查到 | **高（鼓）**：真实录音加人工真值，有混音，MIREX 2017 用过；量小，只有鼓 | [GitHub](https://github.com/CarlSouthall/MDBDrums)、[论文](https://www.open-access.bcu.ac.uk/6179/1/Southall2017a.pdf) |
| **SMD（Saarland Music Data，MIDI-Audio Piano）** | 钢琴✅ | 真实录音（Yamaha Disklavier） | 演奏时乐器记录：Disklavier 同步输出 MIDI；新版修正了 v0 的全局偏移 | 古典钢琴（音乐学院学生演奏） | 50 首、约 261 分钟 | 直接下载（官网 / Zenodo） | CC BY-NC-SA 3.0 | 未查到 | YourMT3 预设没有 SMD（有 MAESTRO、MAPS）【本地】；MuScriptor 未提及；是否与公开测试重合未查到 | **高（钢琴）**：真值质量最好；缺点是古典独奏，不是流行混音 | [AudioLabs](https://www.audiolabs-erlangen.de/resources/MIR/SMD/midi)、[Zenodo v2](https://zenodo.org/records/13753319) |
| **RWC Popular Music + AIST Annotation / rwc-annotations** | 钢琴◐ / 贝斯◐ / 鼓◐（有 aligned MIDI，逐音准确度未查到） | 真实棚录，为数据库专门制作的版权清理曲目 | 录音后由专业人员转写，先有 AIST 人工对齐，新版又经自动对齐及人工核听，仍有音符错误。元数据区分音序器与现场鼓 | 流行（含日语及英语歌曲） | 100 首 | **Zenodo 直接下载**（2026-02 起；"Dataset Open"）；MIDI 和标注在 GitHub | 音频 CC BY-NC 4.0；标注 README 写 CC BY-NC 4.0 | 旧版合包 13.4 GB；新版 `RWC-P.zip` 4.1 GB | YourMT3：`rwc_pop_*` 的 `train_split=None`，只评测不训练【本地】；MuScriptor：论文称所选基准不在训练集中，并报告了 RWC-P 鼓的结果【页面】 | **高（三轨主集候选）**：先抽查 MIDI 与音频逐音一致性，只有经核验的片段才纳入真值评测 | [Zenodo 音频 v2](https://zenodo.org/records/18656623)、[v1](https://zenodo.org/records/17177919)、[rwc-annotations](https://github.com/rwc-music/rwc-annotations)、[AIST Annotation](https://staff.aist.go.jp/m.goto/RWC-MDB/AIST-Annotation)、[TISMIR 2026](https://transactions.ismir.net/articles/10.5334/tismir.326) |
| **Lakh MIDI：LMD-aligned / LMD-matched** | MIDI 里有三轨，但是网友编曲，不是对应录音的演奏真值 | 音频是 7digital 试听片段，不随包提供 | 自动对齐：MIDI 匹配到 Million Song Dataset，再自动对齐到试听 MP3，附匹配置信度 | 流行、摇滚为主 | 45,129 个匹配 MIDI | 不提供音频，主页写"If you need the preview clips themselves, contact me." | CC BY 4.0 | 未查到 | **MuScriptor 高**：合成训练数据明写用了 Lakh MIDI【页面】；YourMT3 用的 Slakh 由 Lakh MIDI 渲染而来 | **低**：真值不等于实际演奏，音频难拿，MIDI 侧和训练数据重叠 | [LMD 主页](https://colinraffel.com/projects/lmd/) |
| **ADTOF** | 鼓◐（众包谱面） | 真实商业音乐 | 人工标注：节奏游戏玩家众包谱面，经清洗对齐 | 以摇滚、金属为主【推断：节奏游戏曲库】 | README 写 359 h；ISMIR 2021 论文表为 114 h（版本差异） | **只提供 mel 频谱**，需在 Zenodo 申请 | 仓库 CC BY-NC-SA 4.0；数据集单独许可未查到 | 未查到 | 两模型都未列出；商业歌曲可能出现在 MuScriptor 的 17 万首内部数据中【推断】 | **低**：拿不到波形，Noto 整条流程跑不了 | [GitHub](https://github.com/MZehren/ADTOF)、[论文](https://arxiv.org/abs/2111.11737) |
| **FiloBass** | 贝斯✅ | 真实录音（Aebersold 伴奏唱片的低音提琴），提供分离出的贝斯分轨 | 人工转写加人工校验："manually verified"，超过 5 万个音符，附演奏对齐 MIDI 和 MusicXML | 爵士（walking bass） | 48 首 | Hugging Face 托管；是否含完整音频需进页面确认（未逐文件核实） | HF 页标 MIT（音频版权另议，未查到） | 未查到 | YourMT3 未列；Aebersold 是商业唱片，可能在 MuScriptor 内部数据中【推断】 | **中（贝斯）**：人工真值可靠；但是原声低音提琴、爵士风格，与流行电贝斯有差距 | [ISMIR 论文](https://archives.ismir.net/ismir2023/paper/000059.pdf)、[HF](https://huggingface.co/datasets/xavriley/FiloBass)、[项目页](https://aim-qmul.github.io/FiloBass/about) |
| **STAR Drums**（TISMIR 2025） | 鼓◐ | 半合成：真实音乐分离出非鼓部分，鼓轨用 20 套虚拟鼓重新合成 | 自动标注：先分离，再用 18 类 CRNN 自动转写，按转写结果重新合成鼓（标签和合成鼓完全吻合，但不代表原鼓手的演奏） | 电子、爵士布鲁斯、流行摇滚、金属朋克、世界音乐 | 124.5 h（训练 114.7 / 验证 8.3 / 测试 1.6 h） | Zenodo（DOI 10.5281/zenodo.15690078，来自摘要转述）；MUSDB18 中 102 首需用脚本自行混音 | 数据集许可未查到（论文 CC BY 4.0） | 未查到 | 两模型都未列；源曲 MUSDB18、Jamendo 等是否在 MuScriptor 内部数据中未查到 | **低到中**：鼓声是合成的，标签是自动的，不能衡量对真实鼓手录音的准确度 | [TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.244) |
| **IDMT-SMT-Drums** | 鼓◐（只有底鼓、军鼓、踩镲） | 混合：RealDrum（真实原声鼓）、WaveDrum（采样库）、TechnoDrum（合成器） | 随附 XML 标注；制作方式未查到 | 鼓 loop，无伴奏 | 608 个 WAV，约 2 小时 10 分；104 条多声部 loop | Zenodo 直接下载 | CC BY-NC-ND 4.0 | 287.1 MB | 两模型都未列 | **低**：没有混音，只有三类鼓 | [Zenodo](https://zenodo.org/records/7544164)、[IDMT](https://www.idmt.fraunhofer.de/en/publications/datasets/drums.html) |
| **Groove MIDI Dataset（GMD）** | 鼓✅（对它自己的音频而言） | 音频由 Roland TD-11 电子鼓音源输出（"synthesized audio from the TD-11"），不是话筒录音 | 演奏时乐器记录：电子鼓 MIDI | 多风格鼓 groove，无伴奏 | 13.6 h、1,150 个 MIDI | 直接下载 | CC BY 4.0 | 完整包 4.76 GB；仅 MIDI 3.11 MB | **YourMT3 高**：E-GMD 在训练预设中，而 E-GMD 是同一批演奏换音色重新渲染的【本地 + 页面推断】 | **低**：无混音，演奏与训练集重叠 | [Magenta](https://magenta.tensorflow.org/datasets/groove) |
| **Slakh2100 test split** | 钢琴✅ / 贝斯✅ / 鼓✅ | **合成**（Lakh MIDI 用采样音源渲染） | 先有谱后合成，真值精确 | 流行、摇滚等 | 原版测试 225 首；redux 测试 151 首 | Zenodo 直接下载 | 许可名未在检索结果中看到（未查到） | 未查到 | YourMT3 训练用 Slakh train，测试集同分布；MuScriptor 合成训练用 Lakh MIDI，**MIDI 层面可能重合** | **低到中**：适合回归测试，不能代表真实录音；项目已用 BabySlakh 测过 | [slakh-utils](https://github.com/ethman/slakh-utils)、[Zenodo](https://zenodo.org/record/4599666) |
| **MoisesDB** | ✗（只有分轨和文字描述，无 MIDI） | 真实多轨 | 无 MIDI | 流行、摇滚等多风格 | 240 首 | GitHub 或申请（未细查） | 仅限非商业研究（README 写 NC-RCL / CC BY-NC-SA 4.0，有冲突） | 未查到 | 不适用 | **低**：没有音符真值；只能当"乐器是否存在"判断的素材 | [GitHub](https://github.com/moises-ai/moises-db)、[论文](https://arxiv.org/abs/2307.15913) |
| **Cadenza（CAD1 / CAD2）** | 未查到 MIDI | CAD2 木管：OpenScore 乐谱经 Dorico 用采样库渲染（合成）；CAD1 是流行摇滚歌词可懂度任务 | CAD2 先有谱后合成，是否附 MIDI 未查到 | 古典木管 / 流行摇滚 | 未查到 | Zenodo（部分版本受限） | 未查到 | 未查到 | 不适用 | **低**：没有钢琴、贝斯、鼓真值 | [Zenodo CAD2](https://zenodo.org/records/14335552) |

### 1.2 补充候选

| 名称 | 乐器覆盖（钢琴/贝斯/鼓） | 真实还是合成 | MIDI 真值来源 | 风格 | 规模 | 能否拿到音频 | 许可 | 下载体积 | 重叠风险 | 适用度 | 来源（2026-11-25 查看） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **MulTTiPop**（arXiv 2607.08756，2026） | 多轨（论文未逐项列出乐器，按有音高 / 无音高两类评测） | 真实商业录音（YouTube 片段） | 自动加人工确认：LMD-matched MIDI 经 TheoryTab 元数据匹配，madmom 节拍追踪后线性形变，人工从最多 4 个候选中选锚点拍，"reject samples without a perfect match" | 流行 | 572 段、374 首、约 3.5 h（dev 61 分钟 / test 152 分钟） | **不提供音频**，只给 YouTube ID 和时间戳，需自行获取 | 数据集许可未查到；作者要求只用于评测 | 未查到 | **MuScriptor 高**：MIDI 来自 Lakh（其合成训练数据用过），商业歌曲也可能在内部数据中；YourMT3 中（Slakh 源自 Lakh） | **中低**：最贴近流行场景，但 MIDI 是编曲稿不是演奏真值（YourMT3+ 只有约 29% onset F1，部分原因可能是标签本身不准【推断】）；获取 YouTube 音频涉及平台条款，需用户决定 | [arXiv](https://arxiv.org/abs/2607.08756)、[项目页](https://gclef-cmu.org/multtipop) |
| **Jazz Trio Database（JTD，TISMIR 2024）** | 钢琴◐（自动转写 MIDI）/ 贝斯、鼓只有起音时间 | 真实商业录音 | 自动：先分离，再自动转写和起音检测（起音 F 值 0.94） | 爵士钢琴三重奏 | 1,294 条、约 44.5 h | 音频需为研究项目申请 | 论文 CC BY 4.0；标注开源 | 未查到 | 商业录音可能在 MuScriptor 内部数据中【推断】 | **低**：不是真值，没有逐音贝斯和鼓 | [mirdata](https://mirdata.readthedocs.io/en/stable/_modules/mirdata/datasets/jtd.html)、[GitHub](https://github.com/HuwCheston/Jazz-Trio-Database) |
| **2025 AMT Challenge 测试集**（NeurIPS 2025 AI for Music） | 8 种乐器，是否含钢琴、贝斯、鼓未查到（提到巴松等稀有乐器） | **合成** MP3 | 先有谱后合成（5 位作曲家新写，含无调性作品），附 PDF 乐谱和 MIDI | 古典或现代 | 76 段，每段约 20 秒 | 未查到 | 论文 CC BY 4.0；数据未查到 | 未查到 | 低（新创作） | **低**：合成音频，风格远离流行；它的评测口径值得借鉴（乐器 + 音高 + onset ±50 ms，按乐器宏平均） | [arXiv 2603.27528](https://arxiv.org/abs/2603.27528) |
| **ENST-Drums**（参考项） | 鼓✅ | 真实录音（3 位职业鼓手，8 声道，部分有伴奏） | 人工标注 | 多风格伴奏 | 约 225 分钟 | 接受用户许可后下载 | 需同意的用户许可 | 未查到 | **YourMT3 高**（`enstdrums_dtp/dtm` 在训练预设中）【本地】 | **低**：真值好，但 YourMT3 见过 | [Telecom Paris](https://adasp.telecom-paris.fr/resources/2009-11-25-enst-drums) |
| **IDMT-SMT-Bass-Single-Track** | 贝斯✅ | 真实电贝斯录音【推断：与 IDMT-SMT-Bass 同系列】 | 人工：每个音标有 onset、offset 和 pitch | 17 条不同风格的贝斯线，无伴奏 | 17 条 | IDMT 页面（访问方式未细查） | 未查到 | 未查到 | YourMT3 训练用的是 IDMT-SMT-Bass（单音集）；Single-Track 是否在训练里未查到 | **中低**：真实电贝斯加人工真值，但很少且无伴奏，可以叠加伴奏做半人工混音 | [IDMT bass lines](https://idmt.fraunhofer.de/en/publications/datasets/bass_lines.html) |
| PianoCoRe（2026，参考项） | 钢琴（只有 MIDI） | 无音频 | 多来源合并精炼 | 古典为主 | 25 万条演奏 | 无音频 | 未查到 | 16.43 GB | — | **低**：没有音频，不能做转写评测 | [arXiv 2605.06627](https://arxiv.org/abs/2605.06627) |

### 1.3 补充核实

- **YourMT3 的 rwc_pop 预设**【本地】。`rwc_pop_bass` 的 `eval_vocab` 为 `BASS_SOLO_CLASS`，`rwc_pop_full` 为 `GM_INSTR_CLASS_PLUS`，两者均为 `train_split: None`。所查配置将 RWC-P 用于贝斯与全乐器评测，只说明该预设的用途。Slakh、MAESTRO、MAPS、ENST-Drums、E-GMD、URMP、IDMT-SMT-Bass 等出现在训练预设中。
- **MuScriptor 的训练和评测**【页面】：
  - 外部评测集：Bach10、Dagstuhl ChoirSet、PHENICX-Anechoic，以及 RWC-P、C、G、J、R，原文是"not contained in either model's training set"。论文表 2 的 RWC-P 鼓 F1 为 YourMT3+ 36.5、MuScriptor 1.3B 42.1。声明适用于论文中的对比模型，本项目使用的 Medium 权重未单独核验曲目。
  - 合成训练数据：约 145 万个 MIDI，来自 Lakh MIDI 和商业数据商。
  - 真实训练数据：17 万首，大部分靠音频和乐谱同步得到标签。
  - 论文说明按相似标题剔除内部测试集相关曲目。音频指纹去重与否未查到。

## 2. 推荐组合

【决策 2026-11-25】RWC-P 用作三轨路线相对排名参考，结果表述为与 RWC-P 参考的一致度。抽查后固定报告未校时和校时分数，鼓以底鼓、军鼓计分，贝斯另报忽略八度的 F1，钢琴标注参考可靠性低。SMD、MDB Drums、FiloBass 用于单科诊断，Slakh 用于合成回归。 [公开评测摘要与复现](../rwcp-eval/README.md)

当前只调路由和阈值。按歌曲约 30%／70% 划分调参集与测试集，同曲只在一侧，每首取 60 秒。交叉验证只在调参集内做，测试集封存到团体赛。当前无需 7:2:1 划分。将来微调使用评测集以外的训练数据。

本轮纳入 P1/P2/P3/P5、B1/B2/B5/B7、D1/D2/D3/D4 及 S1/S3/S5/S6。未入选 P4/P6/B3/B4/B6/D5/D6，其中 D6 需要外部 API 账号。 [PRD 路线选拔计划](../Noto-产品需求文档.md#45-三轨路线选拔评测计划)

【实测 2026-10-16】D3 的 SW 分离鼓 → YourMT3 在开发片段为 55.49%。README 的 56.00% → 77.25% 和同曲另一片段 37.04% → 44.07% 来自固定鼓件组合。该组合保留 Demucs＋YourMT3 的其他鼓键，只用 SW＋ADTOF 替换军鼓和闭镲，分数不能归给 D3。 [鼓轨升级报告](../drums/鼓轨升级报告.md)／[评测范围澄清](../drums/评测范围澄清.md)

| 角色 | 数据集 | 用途 | 理由 | 主要风险 |
|---|---|---|---|---|
| **三轨路线比较** | **RWC-P** | 比较与统一参考的逐轨 F1，另报空参考类别误报 | 流行风格，真实棚录，100 首，可直接下载。YourMT3 所查预设只评测，MuScriptor 论文称对比模型未训练 | MIDI 有漏音、错音和额外音，分层应保留音序器与现场鼓。重复使用同一基准可能产生选择偏差。CC BY-NC |
| **钢琴真值** | **SMD** | 钢琴 B 路线的精确上限 | Disklavier 演奏时记录，真值精确；不在 YourMT3 预设内 | 古典独奏，不能代表流行混音里的钢琴；建议叠加 RWC-P 的伴奏分析难度变化【推断】 |
| **鼓真值** | **MDB Drums** | 真实鼓手录音上的鼓 F1 | 真实多轨录音，人工标注加专家复核，有混音版本 | 只有 23 首；类别需要映射到 Noto 的鼓类口径 |
| **贝斯真值（补充）** | **FiloBass**（必要时再加 IDMT-SMT-Bass-Single-Track） | 贝斯音高和八度误差 | 人工校验的逐音真值 | 原声低音提琴、爵士，和流行电贝斯有差距；FiloBass 的音频来自商业唱片，可能与 MuScriptor 重叠 |

不推荐当真值：JazzSAMBA 的贝斯部分（MuScriptor 自动转写）、MulTTiPop 和 LMD（编曲稿 MIDI，和 MuScriptor 训练数据重叠）、STAR Drums（合成鼓加自动标签）、Slakh 测试集（合成音频的谱准确，仅用于回归）。

**贝斯是公开数据里最薄弱的一环**：没有找到"流行、电贝斯、真实混音、人工逐音真值、模型都没见过"的公开集。所以自录真值集最值得补的就是贝斯。

## 3. 自录真值集可行方案

### 3.1 思路

钢琴、鼓同步记录演奏 MIDI 和音频，贝斯用 DI 录音和人工逐音标注。

| 乐器 | 推荐做法 | 设备 | 真值质量 | 注意 |
|---|---|---|---|---|
| 钢琴 | 数码钢琴 USB-MIDI 和音频同时进 DAW | 带 USB-MIDI 的数码钢琴、音频接口、DAW；想要声学感可外放后用话筒收音 | 高 | 数码钢琴内置音色与真钢琴有差距；用话筒收音能更接近真实混音 |
| 鼓 | 电子鼓 MIDI 加音源音频；更真实的选项是原声鼓加触发器（混合鼓），同时用话筒收音 | 电子鼓（网面）及音源、音频接口；混合方案另需鼓触发器和 2–4 支话筒 | 高（MIDI 是演奏记录） | 电子鼓音源的声音是"电声"，与流行唱片里的原声鼓差别大；触发器可能漏触发或串触发，需人工检查 |
| 贝斯 | **首选：DI 录音加人工标注**（先用 Basic Pitch 或 Melodyne 预标，再人工逐音修正）；备选：分弦 MIDI 拾音器；最后选项：先写 MIDI，乐手看谱按节拍器演奏，再人工修正偏差 | 电贝斯、DI 盒或音频接口；分弦拾音器方案需支持贝斯的转换器（具体型号和精度未核实） | 人工标注高但耗时；MIDI 拾音器在低音区追踪慢、易出八度错误【推断】 | 不建议"暂缺"：贝斯正是公开数据最缺的部分 |

### 3.2 每段的流程

```
选曲或写曲（自创曲、公版旋律，或仅内部使用的翻奏）
→ 节拍器加统一采样率
→ 三轨分别录（或同场录，保留串音）
→ 拍手或军鼓击打做延迟校准，测 MIDI 与音频的偏移
→ 人工清理 MIDI（误触发、踏板）
→ 贝斯逐音标注
→ 混音（可加和声或伴奏）
→ 抽听复核（MIDI 渲染与原音频同步播放）
→ 冻结哈希
```

### 3.3 工作量估计（10–20 段，每段 30–60 秒；以下全是估计，没有实测）

| 项目 | 每段耗时 | 10 段 | 20 段 |
|---|---|---|---|
| 准备（一次性：接线、延迟校准、模板） | — | 0.5–1 天 | 0.5–1 天 |
| 录音（三轨，含重录） | 30–45 分钟 | 约 6 h | 约 12 h |
| 钢琴和鼓 MIDI 清理 | 15–20 分钟 | 约 3 h | 约 6 h |
| 贝斯人工标注 | 30–60 分钟 | 5–10 h | 10–20 h |
| 混音、复核、冻结 | 15–20 分钟 | 约 3 h | 约 6 h |
| **合计** | — | **约 3–4 人天** | **约 5–7 人天** |

- 人员：至少需要会弹钢琴、打鼓、弹贝斯的乐手（可以 1–3 人）。请乐手或租设备都要花钱，需要用户先确认。
- 素材优先自创，翻奏流行歌的使用与发布权限另行确认。
- 【推断】先冻结待测权重，再新录且保持录音未公开，可避免该录音进入这些权重的训练集。选材可贴近流行歌。是否投入由项目所有者决定。

## 4. 后续听感与用户评测

【计划 2026-11-25】上线门槛只用独立真值集逐轨 F1，具体阈值待后续确定。听感和人工修改时间待有资源时补测。

| 方法 | 做法 | 听者人数 | 适合 Noto 的场景 |
|---|---|---|---|
| **A/B 成对偏好**（强制二选一或带"无差别"） | 同一片段的两份转写用同一音色渲染，随机顺序盲听，选哪份更像原曲 | 没有统一标准；Ycart 等 2020 年在钢琴转写感知效度研究中用的就是线上成对比较 | **首选**：比较 Noto 新旧版本或 Noto 与竞品，最直接 |
| **MUSHRA**（ITU-R BS.1534-3） | 同屏 0–100 打分，含隐藏参考和低质锚点。用于转谱时可尝试用核验过的真值 MIDI 渲染参考 | BS.1534-3 的听者人数和剔除规则待核实。BS.1284-2 为通用指南 | 多个系统一起比较并评分，可在核验后的 RWC-P 或自录集尝试 |
| **MOS / ACR**（ITU-T P.800 一类，5 分制） | 单独听一份转写打 1–5 分 | 通常需要更多听者（P.800 的人数要求未核实） | 没有真值、只有原曲时用，例如用户真实歌曲 |
| **任务式评测：人工修改时间** | 让目标用户把转写改到"能用来练习"，记录分钟数 | 需要专家或目标用户参与，当前无资源 | 后续验证，不用于上线判定 |

**怎样和 F1 搭配：**

1. **同一批片段报告 F1 和听感分。** 有资源时可逐段算 Spearman 相关系数。Ycart 2020 的研究显示，只看起音的 note F1 与听感较一致，系统分数接近或转写很差时，一致性会下降。
2. **无真值流行歌的 A/B 对照。** 上线后可选基线或竞品作对照。向竞品提交音频前须经项目所有者同意。
3. **听者构成**：以目标用户（学贝斯、鼓、钢琴的人）为主，加 2–3 名有经验的乐手当"专家组"，两组分开统计。
4. **控制变量**：所有系统用同一套 SoundFont 渲染，响度对齐，片段 10–20 秒，盲测随机化，记录听者设备。
5. 可参考的新工作：arXiv 2608.04511（2026）的检索摘要主张分别评估乐谱和回放听感，正文待核对。

## 5. 未查到或待确认清单

- RWC-P 钢琴与贝斯逐音校订，以及底鼓、军鼓之外的独立鼓件复核。
- JazzSAMBA 下载包内容、许可及演奏 MIDI 的采集方式。
- MulTTiPop 的数据许可、具体乐器列表。
- FiloBass 的 Hugging Face 包是否含完整音频，以及音频版权。
- Slakh 许可名；STAR Drums 许可和体积；MDB Drums、SMD 的下载体积。
- BS.1534-3 对听者人数和剔除规则的原文。

## 来源（均于 2026-11-25 查看）

- JazzSAMBA：<https://arxiv.org/abs/2609.34931>、<https://arxiv.org/html/2609.34931v1>、<https://pnlong.github.io/jazzsamba-demo/>
- MulTTiPop：<https://arxiv.org/abs/2607.08756>、<https://gclef-cmu.org/multtipop>
- MuScriptor：<https://arxiv.org/html/2607.08168>
- RWC：[Zenodo v2](https://zenodo.org/records/18656623)、[Zenodo v1](https://zenodo.org/records/17177919)、<https://github.com/rwc-music/rwc-annotations>、<https://staff.aist.go.jp/m.goto/RWC-MDB/AIST-Annotation>、<https://transactions.ismir.net/articles/10.5334/tismir.326>
- MDB Drums：<https://github.com/CarlSouthall/MDBDrums>、<https://www.open-access.bcu.ac.uk/6179/1/Southall2017a.pdf>
- SMD：<https://www.audiolabs-erlangen.de/resources/MIR/SMD/midi>、<https://zenodo.org/records/13753319>
- LMD：<https://colinraffel.com/projects/lmd/>
- ADTOF：<https://github.com/MZehren/ADTOF>、<https://arxiv.org/abs/2111.11737>
- FiloBass：<https://archives.ismir.net/ismir2023/paper/000059.pdf>、<https://huggingface.co/datasets/xavriley/FiloBass>、<https://aim-qmul.github.io/FiloBass/about>
- STAR Drums：<https://transactions.ismir.net/articles/10.5334/tismir.244>
- IDMT-SMT-Drums：<https://zenodo.org/records/7544164>
- IDMT-SMT-Bass 系列：<https://idmt.fraunhofer.de/en/publications/datasets/bass.html>、<https://idmt.fraunhofer.de/en/publications/datasets/bass_lines.html>
- Groove：<https://magenta.tensorflow.org/datasets/groove>
- Slakh：<https://github.com/ethman/slakh-utils>、<https://zenodo.org/record/4599666>
- MoisesDB：<https://github.com/moises-ai/moises-db>、<https://arxiv.org/abs/2307.15913>
- Cadenza：<https://zenodo.org/records/14335552>
- JTD：<https://github.com/HuwCheston/Jazz-Trio-Database>
- AMT Challenge 2025：<https://arxiv.org/abs/2603.27528>
- ENST-Drums：<https://adasp.telecom-paris.fr/resources/2009-11-25-enst-drums>
- PianoCoRe：<https://arxiv.org/abs/2605.06627>
- 听感评测：Ycart 等 2020 <https://doi.org/10.5334/tismir.57>（刺激材料 <https://zenodo.org/records/3746863>）；ITU-R BS.1534-3 <https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1534-3-201510-I!!PDF-E.pdf>；ITU-R BS.1284-2 <https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1284-2-201901-I!!PDF-E.pdf>；[ITU-T P.800](https://www.itu.int/rec/T-REC-P.800/en)；[arXiv 2608.04511](https://arxiv.org/abs/2608.04511)
