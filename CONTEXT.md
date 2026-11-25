# CONTEXT.md

最后更新：2026-11-25（Asia/Taipei）

## 交接给新 agent（2026-11-24）

- 11-25 一键三轨（public.11）新增可选并行，默认串行。开启后，YourMT3 识别到钢琴时并行运行钢琴 B 和 MuScriptor，结束后合并。两段 60 秒对照分别节省 19.9% 和 21.8%，每段的串并行 MIDI 哈希一致。两路线程各可设为 1 或 2，默认各 2。详见 README 与 CHANGELOG。
- 11-25 PRD 2.0（public.10）确立真值集逐轨 F1 为北极星和唯一上线门槛，差异化选定 A+B。路线选拔用 RWC-P 主考和单科诊断，按歌曲 30%／70% 划分，每首 60 秒。先在调参集选路线，再对封存测试集一次性评组合。
- 11-25 修复 MuScriptor 贝斯和鼓的缺轨拼接，新增只需输入 MP3 的一键三轨入口 `scripts/run_noto.py`，完成 8 段端到端评测。8/8 段成功，钢琴、贝斯、鼓的 micro F1 分别为 94.74%、54.79%、49.80%，贝斯和鼓相对条件评测的降幅均来自空类别误报。详见 `outputs/e2e-eval/README.md`。
- 已完成（11-18 至 11-24）：
  - 8 页作品集 PDF（源文件 `outputs/portfolio-pdf/index.html`，提交 6c23d09），成品不入库。
  - 结论：项目没用大模型，接入 Dify 意义不大；Dify 自带的网页做不了多轨 MIDI 界面。
  - 竞品公开信息（11-24 查看，未实测）：Audio Jam 是练习工具，做分轨、和弦、变速，官网未提音频转 MIDI，美区 App Store（id6745493736）Pro 周付 $6.99、月付 $12.99，年付有 $29.99 和 $39.99 两种条目（2026-11-24 查看，以商店实时为准）；灵谱是网页版可编辑多轨 MIDI 工作台，支持粘贴抖音/小红书/B 站链接、歌曲最长 30 分钟、有曲谱广场和微信群，首页无标价，按转录时长充值、新用户送 10 分钟，具体价格未见。灵谱广场里的《唯一》可能经过人工编辑，不能当盲测。详见 `outputs/competitor-analysis/README.md`。
  - 11-24 新增竞品对比 `outputs/competitor-analysis/README.md`。Noto 贝斯/鼓替换路线与 NeuralNote v2 同属 MuScriptor 家族，差异可从按乐器组合多模型、统一逐轨评测口径和交付流程验证。
- 建议的下一步（用户还没选）：
  1. 真值评测：RWC-P 下载与抽查事项进行中。下载并通过 MIDI 抽查后，先用调参集 5 个片段跑全候选测成本，再启动正式选拔。
  2. 用户调研：访谈 3–5 人。
  3. 小范围试用：试用 5–8 人，记使用卡点。A/B 盲听留到上线后、有资源时补测。人工修改时间也待有专家或目标用户参与时再测。
  - 另可补：增长闭环和冷启动方案、用户故事和低保真原型、处理成本估算。端到端评测已记录逐段和阶段耗时，见 `outputs/e2e-eval/README.md`。
- 约束：
  - 用中文回答。
  - 新下载、花钱、对外提交都要先问用户。
  - 不干扰用户正在用的应用。
  - 不在外部请求里带用户邮箱。

## 最近完成：多曲评测（2026-11-18，v0.1.0-public.6）

- 报告 `outputs/multi-song-eval/README.md`，脚本 prepare.py → run_routes.py → score.py，另有 drum_confusions.py、bass_octave_check.py。数据在 `work/datasets/`，转写产物在 `outputs/runs/multi-song-eval/items/`，均不入库。
- 结论：MAESTRO 测试集 5 首真实钢琴上，钢琴 B 0.983 对基线 0.975，5 首全部提升；BabySlakh 20 段上基线三轨领先（钢琴 0.891/0.794，贝斯 0.978/0.697，鼓 0.852/0.553）。BabySlakh 取自 Slakh train，YourMT3 的训练数据预设包含这一划分；本次所用权重的训练曲目未逐一核实，结果可能偏向基线，不能据此判定 MuScriptor 更差。MAESTRO 是官方测试集，但各模型是否见过这些录音未核实。这是按参考乐器列表选轨的条件评测，不是端到端评测。
- 口径要点：
  - Slakh 贝斯参考 −12，有测频和基线偏移两组证据。
  - 这是按参考乐器列表选轨的条件评测。
  - Track00017/00018 按 MuScriptor 原始日志音符打分。
- Codex 只读复核 852119e，结果一致；5 条意见已在 public.6 中修复。
- 下一步候选：寻找不在训练集里的真实录音多轨数据（URMP 在 YourMT3 预设内，不适合），验证钢琴 B 只对原声钢琴启用的策略。

## 当前目标

- Noto 音频转多轨 MIDI 项目处于本地研究原型阶段；优先验证转写质量，再考虑完整前端。
- 2026-11-17 用户明确要求将 GitHub 仓库改为公开，已执行并验证。

## 用户明确要求

- 忽略人声输出；目标为钢琴、木吉他、清音电吉他、贝斯、鼓和弦乐。
- 项目集中在 `/Users/ringscherry/Desktop/AGENT/Codex项目/吉他产品/`，代码仓库是其中的 `音频转MIDI/`。历史文档可能仍引用迁移前的路径，使用前应确认。
- 可用版本按项目规则检查、记录、提交和同步；音频、私有素材、模型权重及大批结果不上传。
- 可检查版本先提交冻结，再由独立子 agent 只读验证；发现问题后修复并复验。
- 操作电脑不干扰用户正在使用的界面或进程；未经确认不新增付费。

## 已完成事项

- 仓库现为公开：<https://github.com/Max-Ren0/audio-to-midi-mvp>，默认 `main`。匿名 GitHub API 返回 HTTP 200。
- 已搭建本地多轨 MIDI 实验、钢琴 B 固定路线和贝斯/鼓 MuScriptor 替换实验；详细版本与实验见 `CHANGELOG.md`、`outputs/` 和 Git 历史。
- 2026-11-17 整理展示首页：README 项目概览、GitHub Pages 在线作品集 <https://max-ren0.github.io/audio-to-midi-mvp/>（`gh-pages` 分支只放 `outputs/portfolio-preview/index.html` 副本，需手动同步）、仓库简介与 topics。
- 2026-11-17 作品集新增"听一听"对比演示（自写合成片段，YourMT3 基线；素材 `outputs/portfolio-preview/demo/`，复现见 `outputs/demo-synthetic/README.md`），Claude 实现、Codex 独立核验与复验。
- 已制作项目作品集、PDF 和 PRD；旧版完整项目上下文归档于 `outputs/history/CONTEXT-before-public-visibility.md`。

## 关键决策

- 钢琴：BS-RoFormer SW 分离 → Transkun；吉他和弦乐仍有显著错误。
- 贝斯/鼓：MuScriptor Medium 分别处理贝斯和鼓。当前一键三轨入口 `scripts/run_noto.py` 从本地 MP3 运行基线、钢琴 B 和贝斯/鼓替换，输出多轨 MIDI 与回执。
- 多种模型按乐器任务组合；未从零训练，也未完成微调。未来可引入音乐专业人士标注与校对，扩充评测集并在条件允许时探索微调。
- 2026-11-18 用户同意按建议收窄 MVP：先承诺钢琴、贝斯、鼓三轨；六类目标不变，吉他和弦乐作为研究轨道继续输出，不计入 MVP 验收。README、作品集、PRD 1.2 已同步。
- 用户已明确授权此次公开仓库；现有 AGENTS.md 中要求“私有仓库”的历史表述与该决定冲突时，以用户此次决定及实际 PUBLIC 状态为准，不擅自切回私有。

## 重要文件

- `README.md`：运行入口与限制；`CHANGELOG.md`：版本记录。
- `outputs/Noto-产品需求文档.md`：PRD 2.0，含 A+B、真值 F1 上线门槛及 4.5 三轨路线选拔评测计划。
- `outputs/eval-dataset-research/README.md`：评测集来源、训练重叠风险、自录和盲听方案。
- `outputs/multi-song-eval/`：多曲评测脚本、结果与报告。
- `scripts/run_noto.py`：从 MP3 生成三轨 MIDI 与运行回执的一键入口。
- `outputs/e2e-eval/`：端到端评测脚本、结果与报告。
- `outputs/competitor-analysis/README.md`：竞品对比、证据边界和低成本验证计划。
- `outputs/portfolio-preview/index.html`：作品集网页（改动后需手动同步到 `gh-pages` 分支才会上线）；`outputs/portfolio-pdf/index.html`：作品集 PDF 源文件。
- `outputs/muscriptor-route/`：贝斯/鼓替换入口说明、实验和验证；`scripts/run_muscriptor_bass_drums.py`：本地入口。
- `outputs/weiyi-noto/`：新歌生成报告；`outputs/runs/` 下的本地音频/MIDI产物不上传。
- `outputs/history/CONTEXT-before-public-visibility.md`：原始长上下文及历史详细记录。

## 验证结果

- 《唯一》单曲、既定对齐与 50ms 起音容差下，MuScriptor 替换前后：贝斯 F1 25.45%→71.92%，鼓 55.22%→55.99%；不代表其他歌曲表现或听感准确率。
- 全量测试 180 项通过，2 项因缺少本地音色库跳过。参考 MIDI 来源及完整性未独立核实，未系统试听。
- 本次公开前扫描 Git 可达历史中常见音频、MIDI、权重文件名和常见凭据格式，未发现匹配；扫描不能保证涵盖全部敏感内容。0d263f7 冻结后独立核验了公开状态、匿名访问、文档一致性及上下文归档；未逐条审查所有历史私人信息。

## 未完成事项

- 一键三轨入口已实现，仍需补充乐器是否存在的判断，并检查长音频接缝。
- 公开数据多曲评测首轮已完成。独立真值评测集和 F1 验收待做。
- 单独确认各模型权重、依赖及商业使用许可；MuScriptor 当前权重标注为非商业使用。

## 风险与注意点

- 2026-11-18 已把 `.venv` 与 `work/sep-env` 中 64 个入口脚本和 .pth 的迁移前路径改为当前路径（备份 `work/venv-path-fix-backup-20261118.tgz`，清单 `work/venv-path-fix.list`）；`.venv/bin/audio-midi` 恢复可用。项目再搬家需重做此步或重建环境。

- 仓库及可达提交历史已公开。PRD、实验记录中的歌曲名、路径和其他已提交文字也对公众可见；本地素材与权重不随仓库自动公开。
- 训练或微调尚未开展；研究结果不等于正式产品验收。
- 本次只确认 GitHub API 匿名可访问，不代表已上线可交互演示。

## 下一步建议

- 【计划 2026-11-25】已确认顺序为钢琴 B 与 MuScriptor 并行 → 节拍检测与小节对齐 → 乐器是否存在判断（依赖 RWC-P 调参集）。可选并行已在独立工作区实现并实测，默认串行。
- 对外分享时可给公开仓库地址和在线作品集链接，说明项目仍处于研究原型阶段。
- 若继续开发，先读取本文件与相应实验报告，检查当前 Git 状态，避免改写冻结结果。
