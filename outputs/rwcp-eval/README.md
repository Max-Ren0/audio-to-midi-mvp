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
