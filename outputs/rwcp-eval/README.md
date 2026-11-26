# Noto · RWC-P 三轨路线评测

在封存的 50 首测试曲中，现有组合 S3 的钢琴、贝斯和鼓与 RWC-P 参考的一致度均高于全 YourMT3 的 S1，micro F1 分别高出 26.47、49.63 和 4.38 个百分点，所有测试曲均沿用原时间轴计分。

## 数据与许可

RWC Music Database 的 Popular Music 子集（RWC-P / RWC-MDB-P-2001）含 100 首流行棚录，本评测从中选了钢琴、贝斯、鼓参考齐全的 72 首。音频及配套标注按 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 发布，仅限非商业使用。署名为 RWC Music Database 制作团队，原始论文作者为 Masataka Goto、Hiroki Hashiguchi、Takuichi Nishimura 和 Ryuichi Oka，更新标注由 RWC 2.0 团队维护。评测从音频中截取评分片段，仓库只发布代码、冻结配置及汇总，音频、参考 MIDI、预测 MIDI 和逐曲结果均不入库。 [原始论文](https://doi.org/10.5281/zenodo.1416473) · [音频发布及引用说明](https://zenodo.org/records/18656623) · [标注来源](https://github.com/rwc-music/rwc-annotations) · [更新说明](https://doi.org/10.5334/tismir.326)

## 冻结流程与计分

1. **清单冻结。** 按鼓来源分层，以歌曲为单位固定 22 首调参、50 首测试。每首约 60 秒，另留上下文供推理。清单 SHA-256 为 `21a9a1879f33ec84d2191b3deab083f9f6cbe5ef0c0e887f366c0dc1578ff00e`。
2. **规则 v2。** 先试跑 5 首调参曲，审核后冻结规则，再运行其余 17 首。每首所有候选共享同一个偏移估计，搜索范围约 ±100 ms，相关峰至少 0.30、比竞争峰至少高 0.05。通过置信检查后先减去谱通量的 20 ms 延迟，再对绝对值小于 50 ms 的偏移应用死区。低置信或落入死区均使用 0 ms。
3. **单项赛。** 用全部 22 首调参曲比较 12 个候选。每轨以校正后 micro F1 为主，与最高分差距严格小于 2 个百分点的路线按平均独立路线耗时决胜。
4. **阈值与组合冻结。** 用调参集确定 [S6 存在判断配置](presence-config.json)，再冻结 [团体组合](team-config.json)。S1 是全 YourMT3，S3 是现有三轨方案，S5 由单项赢家组成，S6 在 S5 上使用冻结的存在阈值。
5. **封存测试。** 组合和评分规则冻结后才在 50 首测试曲上运行团体赛一次，评分使用实际组装并回读的 MIDI。测试集 45 首估计落入死区，5 首因竞争峰判为低置信。应用偏移全部为 0 ms，测试分数未经偏移校正，未校正与校正后分数完全相同。

中心评分窗内的起音以 ±50 ms 容差一对一匹配，再按所有曲目的 TP、FP、FN 计算 micro F1。贝斯主指标用精确音高，另报忽略八度。鼓只计底鼓 GM 35/36 和军鼓 GM 38/40，其他打击乐单列。整轨空输出按零预测计分并另计次数。参考缺轨仍预测的音符计误报。

## 调参集单项赛

| 轨道 | 入选路线 | 校正后 micro F1 | 选择依据 |
|---|---|---:|---|
| 钢琴（参考可靠性低） | P2 · BS-RoFormer SW 分离 → Transkun | 69.62% | 主指标最高 |
| 贝斯（精确音高） | B2 · MuScriptor 混音转写 | 68.85% | 与 B7 打平，耗时更短 |
| 鼓（底鼓及军鼓） | D2 · MuScriptor 混音转写 | 78.20% | 与 D4 打平，耗时更短 |

## 封存测试集团体赛

| 轨道 | S1 micro F1（95% 区间） | S3 micro F1（95% 区间） | S3 − S1，百分点（95% 区间） |
|---|---:|---:|---:|
| 钢琴（参考可靠性低） | 55.82%（49.38%～61.84%） | 82.29%（76.22%～87.22%） | +26.47（+22.11～+31.17） |
| 贝斯（精确音高） | 26.56%（21.05%～32.27%） | 76.19%（70.67%～81.26%） | +49.63（+43.73～+56.03） |
| 鼓（底鼓及军鼓） | 75.45%（69.77%～80.42%） | 79.83%（73.12%～85.77%） | +4.38（+0.89～+7.80） |

95% 区间按歌曲配对重采样 10,000 次，随机种子 20261126。贝斯忽略八度时 S1 为 45.29%、S3 为 79.62%。仅汇总 45 首偏移高置信曲时，S1 钢琴／贝斯（精确）／鼓为 56.63%／28.51%／76.47%，S3 为 82.24%／77.63%／80.74%。四个配方均成功生成 50/50 首可回读的 MIDI。S3、S5、S6 的 MIDI 逐首一致。本批样本支持保留 S3。评测运行器发布固定组合，产品入口的钢琴触发和缺轨回退需单独验证。

## 局限

- F1 衡量**与 RWC-P 参考的一致度**。参考有错音、漏音和时序偏差，钢琴参考可靠性低。产品准确率及验收门槛需用独立校订或录制的真值进一步验证。
- v2 来自五首调参试跑及候选偏移扫描，调参成绩存在选择偏差。20 ms 补偿是试跑中得到的近似值，各模型的起音延迟也可能不同。50 首测试曲的应用偏移均为 0 ms，本批测试分数没有经过任何偏移校正。
- 所选歌曲均有三轨，22 首调参的评分片段也没有缺轨负例。S6 的三轨阈值全为 0，故 S6 ≡ S5 ≡ S3。**乐器是否存在判断本轮未得到检验。**
- 调参曲 P092 的贝斯参考疑似高一个八度，B2 的 262 对起音匹配中有 258 对预测比参考低 12 半音。剔除 P092 后 B2 精确 micro F1 从 68.85% 升至 74.12%，赢家保持不变。测试集以 S3 逐曲检查忽略八度与精确 F1 之差，差距超过 30 个百分点的曲目为 0 首。
- P058、P059、P091 的参考有其他 GM 打击乐，评分窗内没有底鼓或军鼓。这三首的底鼓及军鼓预测计入鼓分数的假阳性，整轨缺失统计保持原定义。剔除这三首作敏感性分析时，S1 和 S3 的鼓 micro F1 分别为 78.54% 和 82.34%。

## 复现

从包含本评测代码的仓库根目录运行。资源检出须使用与钢琴路线锁文件匹配的 SW 包装脚本。合入后的锁文件记录了新的包装脚本哈希，依赖该锁文件的旧 SW 和 Transkun 阶段缓存无法命中。使用旧模型资产复现时请另建评测工作目录。按[项目安装说明](../../README.md)准备 Python 环境、FFmpeg 与本地模型。评测的模型版本和文件校验见 [钢琴路线锁文件](../../config/piano-b.lock.json) 和 [运行器资源检查](run_pilot.py)。资源预检还会校验 ADTOF 0.1.0 的权重，D4 单项路线使用该模型。完整模型推理使用本地 CPU。将 `RWC-P.zip` 解压到 `work/datasets/rwc-p/`，保留子目录 `RWC-P/`，并将上游标注提交 [`0a1a6c31dbe73a7f5d44f7caef8cd0999402a4c2`](https://github.com/rwc-music/rwc-annotations/commit/0a1a6c31dbe73a7f5d44f7caef8cd0999402a4c2) 解压或检出到同级的 `annotations/`。原评测的两份元数据 CSV 仅保留表头和 RWC-P 行，下面的命令在本地标注副本执行同样的筛选。

```sh
resources=.
dataset="$resources/work/datasets/rwc-p"
work="$resources/work/rwcp-eval"
python="$resources/.venv/bin/python"

git check-ignore "$work/manifest.json" "$work/team-results.json"
mkdir -p "$work"
for csv in "$dataset/annotations/metadata.csv" \
  "$dataset/annotations/01_annotations_preprocessed/MIDI_aligned/metadata_mapping_vocals.csv"; do
  awk 'NR == 1 || /^RWC_P[0-9]+;/' "$csv" > "$csv.rwc-p" && mv "$csv.rwc-p" "$csv"
done
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR="$PWD/$work/numba"
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

"$python" outputs/rwcp-eval/prepare.py "$dataset" "$work/manifest.json"
(cd "$work" && shasum -a 256 -c manifest.sha256)
manifest_sha="$(cut -d ' ' -f 1 "$work/manifest.sha256")"
"$python" outputs/rwcp-eval/run_pilot.py --resources "$resources" --work "$work" \
  --manifest-sha256 "$manifest_sha"

"$python" outputs/rwcp-eval/run_dev.py freeze-offsets --resources "$resources" --work "$work"
dev_sha="$(shasum -a 256 "$work/dev-offsets-v2.json" | cut -d ' ' -f 1)"
"$python" outputs/rwcp-eval/run_dev.py run --resources "$resources" --work "$work" \
  --offset-sha256 "$dev_sha"
"$python" outputs/rwcp-eval/report_dev.py --work "$work" --output "$work/dev-report.md"
```

公开版已带有原先冻结的阈值与组合。复现团体赛时沿用两份配置，并确认清单 SHA-256 与上文一致。续跑时保留当前评测目录和已冻结偏移，跳过对应的生成步骤。

```sh
"$python" outputs/rwcp-eval/run_team.py freeze-offsets --resources "$resources" --work "$work"
team_sha="$(shasum -a 256 "$work/team-offsets-v2.json" | cut -d ' ' -f 1)"
"$python" outputs/rwcp-eval/run_team.py run --resources "$resources" --work "$work" \
  --offset-sha256 "$team_sha" --jobs 1
"$python" outputs/rwcp-eval/report_team.py --work "$work" --output "$work/team-report.md"
```
