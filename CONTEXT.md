# CONTEXT.md

最后更新：2026-11-17（Asia/Taipei）

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
- 已制作项目作品集、PDF 和 PRD；旧版完整项目上下文归档于 `outputs/history/CONTEXT-before-public-visibility.md`。

## 关键决策

- 钢琴：BS-RoFormer SW 分离 → Transkun；吉他和弦乐仍有显著错误。
- 贝斯/鼓：新增 MuScriptor Medium 本机替换入口，依赖已存在的同源 Noto MIDI 基线；尚非任意 MP3 的一键六轨完整流程。旧贝斯/鼓研究冻结版本保留。
- 多种模型按乐器任务组合；未从零训练，也未完成微调。未来可引入音乐专业人士标注与校对，扩充评测集并在条件允许时探索微调。
- 用户已明确授权此次公开仓库；现有 AGENTS.md 中要求“私有仓库”的历史表述与该决定冲突时，以用户此次决定及实际 PUBLIC 状态为准，不擅自切回私有。

## 重要文件

- `README.md`：运行入口与限制；`CHANGELOG.md`：版本记录。
- `outputs/Noto-产品需求文档.md`：当前需求文档（PRD）。
- `outputs/portfolio-preview/index.html`：作品集网页（改动后需手动同步到 `gh-pages` 分支才会上线）；`../作品集/Noto-音频转MIDI-作品集.pdf`：作品集 PDF。
- `outputs/muscriptor-route/`：贝斯/鼓替换入口说明、实验和验证；`scripts/run_muscriptor_bass_drums.py`：本地入口。
- `outputs/weiyi-noto/`：新歌生成报告；`outputs/runs/` 下的本地音频/MIDI产物不上传。
- `outputs/history/CONTEXT-before-public-visibility.md`：原始长上下文及历史详细记录。

## 验证结果

- 《唯一》单曲、既定对齐与 50ms 起音容差下，MuScriptor 替换前后：贝斯 F1 25.45%→71.92%，鼓 55.22%→55.99%；不代表其他歌曲表现或听感准确率。
- 此前路由版本 139 项测试通过并经独立核验；参考 MIDI 来源及完整性未独立核实，未系统试听。
- 本次公开前扫描 Git 可达历史中常见音频、MIDI、权重文件名和常见凭据格式，未发现匹配；扫描不能保证涵盖全部敏感内容。0d263f7 冻结后独立核验了公开状态、匿名访问、文档一致性及上下文归档；未逐条审查所有历史私人信息。

## 未完成事项

- 将各轨研究路线整合为新歌曲的统一流程，并检查长音频接缝。
- 建立多曲、专业标注或校对的独立评测集，进行听辨和人工修改时间验证。
- 单独确认各模型权重、依赖及商业使用许可；MuScriptor 当前权重标注为非商业使用。

## 风险与注意点

- 仓库及可达提交历史已公开。PRD、实验记录中的歌曲名、路径和其他已提交文字也对公众可见；本地素材与权重不随仓库自动公开。
- 训练或微调尚未开展；研究结果不等于正式产品验收。
- 本次只确认 GitHub API 匿名可访问，不代表已上线可交互演示。

## 下一步建议

- 面试时可分享公开仓库地址、在线作品集链接及本地作品集 PDF，说明项目仍处于研究原型阶段。
- 若继续开发，先读取本文件与相应实验报告，检查当前 Git 状态，避免改写冻结结果。
