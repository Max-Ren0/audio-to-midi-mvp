# RWC-P 五段试跑

先冻结清单，再运行固定的五首调参曲目。清单包含 72 首的窗、分层和全曲 MIDI 偏移。模型入口只生成五首调参曲目的预测和分数。

## 本机复现

在该试验分支的仓库根运行。参数 `resources` 指向带有现成数据、Python 环境和模型的主检出。

```sh
resources="/path/to/main/checkout"
work="$resources/work/rwcp-eval"
python="$resources/.venv/bin/python"
git -C "$resources" check-ignore -v work/rwcp-eval/manifest.json work/rwcp-eval/pilot-results.json
mkdir -p "$work"
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR="$work/numba"
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
nice -n 10 "$python" outputs/rwcp-eval/prepare.py "$resources/work/datasets/rwc-p" "$work/manifest.json"
uptime | tee "$work/preflight-uptime.log"
nice -n 10 "$python" outputs/rwcp-eval/run_pilot.py --resources "$resources" --work "$work" \
  --manifest-sha256 "$(cut -d ' ' -f 1 "$work/manifest.sha256")"
"$python" outputs/rwcp-eval/report.py --work "$work" --output "/path/to/pilot/README.md" \
  --test-summary "实际测试结果" --code-commit "$(git rev-parse --short HEAD)"
```

复跑时保留现有清单，跳过准备步骤。运行器校验输入及成功阶段的产物哈希，读取耗时回执并只重试未完成的模型阶段。原始数据按只读输入处理，输出位于主检出忽略的 `work/`。运行前确认同一机器没有其他转写或训练任务。若 1 分钟负载超过 4，在试跑报告中标记。

计分结果以与 RWC-P 参考的一致度表示。时间偏移来自非人声 MIDI 脉冲与原混音的互相关。鼓按底鼓和军鼓两个类别计分，其他 GM 鼓件另计。贝斯保留原音高，另报忽略八度的分数。钢琴参考可靠性低。完整计分口径以及模型依赖见脚本及本地报告。

## 调参单项赛冻结规则 v2

- 沿用原清单哈希及 22 首调参曲目，先对这 22 首冻结新偏移。估计只读原本约 62 秒的实际 WAV 输入与相同区间内的非人声 MIDI 起音。候选完全共用每曲偏移。50 首测试曲目仅在旧清单中保留分组。
- 搜索 ±10 帧（约 ±100 ms）。最高峰必须 ≥0.30、高于 ±3 帧邻域外的次峰 ≥0.05，且避开搜索边缘，否则偏移标为低置信，使用 0 ms。单独记录 ±25 帧内的竞争峰和相关曲线，供诊断。
- 在通过置信检查的估计上减去 20 ms，补偿审核发现的谱通量估计延迟。补偿后绝对偏移 <50 ms 时保持 0 ms。保留原估计、补偿后估计和实际应用值。
- 空输出指目标乐器在含上下文输入上完全没有预测音符。分数按零预测计入，另记空输出次数。模型或文件错误视为未完成。成品中只有非评分鼓键的结果仍属于非空。
- 主指标为完整 22 首的校正后 micro F1。贝斯用精确音高，鼓只计底鼓和军鼓。报告同时列未校正、剔除偏移低置信曲目的校正分、贝斯忽略八度分，以及候选两两逐曲胜／平／负。逐曲同分才记为平，任一 F1 未定义单列。
- 每轨先找主指标最高者，与其差值严格小于 2 个百分点的候选进入打平组。使用 22 首的平均独立路线耗时决胜，计入所需的解码、分离、模型和后处理阶段。P5 算上 P2 和判据的成本，选 P1 时再计入 P1。若耗时完全相同，取主指标较高者，再按候选编号。全流程实际耗时按共享阶段另计。
- v2 来自对五段试跑及候选扫描的审核，存在选择偏差。钢琴结论标记参考可靠性低。胜负是与 RWC-P 参考的一致度，独立真值和最终效果留待后续。

```sh
nice -n 10 "$python" outputs/rwcp-eval/run_dev.py freeze-offsets --resources "$resources" --work "$work"
uptime
offset_sha="$(shasum -a 256 "$work/dev-offsets-v2.json" | cut -d ' ' -f 1)"
nice -n 10 "$python" outputs/rwcp-eval/run_dev.py run --resources "$resources" --work "$work" --offset-sha256 "$offset_sha"
```

运行按单阶段串行，开始每首前等待 1 分钟负载 ≤4。原试跑的模型产物按哈希复用，每首写一份增量检查点，重启沿用已有偏移文件与已完成曲目的结果。

## S6 乐器存在判断的调参规则

S6 仅对 S5 各赢家输出作整轨判定。用中心约 60 秒的预测起音数，鼓包含所有 GM 键。预测数严格低于该轨阈值则不发布该轨，阈值 0 表示停用判断。运行时只读取预测，参考只用来校准和评估。

阈值从 0、2、4、8、16 选择。使用 22 首调参集的校时后片段，至少 3 个该乐器参考为空的片段且有正例才启用筛选。允许的阈值在调参集须保留所有原本有预测的正例轨，再最大化缺轨样本上去掉的误报音符数。效果相同取最小阈值。证据不足取 0。使用这一批 RWC-P 真值口径一致的近一分钟片段校准，BabySlakh／MAESTRO 的异分布与不同时长留作后续单独验证。

## 封存团体赛执行

提交调参赛结果文档、存在判断配置，再提交组合配置后才执行测试切片与 v2 偏移冻结。团体赛使用实际发布并回读的 MIDI，计分规则保持 ±50 ms 及固定鼓件口径。按歌曲配对重采样 10,000 次，固定种子 20261126。至少一轨有效 MIDI 且能回读算一键成功，空轨单列。

默认路线建议保守地沿用 S3。若 S5 各轨点估计都达到 S3 且至少一轨配对区间下限大于零，把 S5 列为下一版默认候选。正式切换需要独立真值验证。报告记录 S6 的误删与误报证据，当前默认入口保持原样。

```sh
# 先完成调参赛。各配置生成后单独审核并提交。
"$python" outputs/rwcp-eval/presence.py --work "$work" --config outputs/rwcp-eval/presence-config.json
"$python" outputs/rwcp-eval/run_team.py freeze-combinations --resources "$resources" --work "$work"
# 组合配置和评分代码提交后，才读取封存 50 曲的音频及 MIDI。
uptime
"$python" outputs/rwcp-eval/run_team.py freeze-offsets --resources "$resources" --work "$work"
test_offset_sha="$(shasum -a 256 "$work/team-offsets-v2.json" | cut -d ' ' -f 1)"
nice -n 10 "$python" outputs/rwcp-eval/run_team.py run --resources "$resources" --work "$work" \
  --offset-sha256 "$test_offset_sha" --jobs 2
```

每个组合的等效串行耗时计所需去重阶段与组装读写，一次执行的实际耗时另计。双流水线根据本机内存可用量检查自动降为单流水线。中断可使用同一个命令续跑，原测试偏移与已完成检查点保留。
