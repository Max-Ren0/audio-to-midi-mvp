"""Render the completed local RWC-P pilot as a Chinese Markdown report."""
import argparse
from collections import Counter
from pathlib import Path
from statistics import mean

from prepare import digest
from run_pilot import FIXED_ROUTES, pilot_songs, read_json


ROUTES = {
    'P1': 'YourMT3 直转混音，取钢琴',
    'P2': 'SW 钢琴分轨 → Transkun 2.0',
    'P3': 'Transkun 2.0 直转混音',
    'P5': '根据 P2 音符与钢琴分轨检测泛音偏移，有足够证据用 P2，其余用 P1',
    'B1': 'YourMT3 直转混音，取贝斯',
    'B2': 'MuScriptor Medium F16 直转混音，取贝斯',
    'B5': 'SW 贝斯分轨 → YourMT3，使用 PRD 允许的 YourMT3 实现',
    'B7': 'B2 结合 SW 贝斯分轨的基频与谐波证据，只移动单个音符 ±1 八度',
    'D1': 'YourMT3 直转混音，取鼓',
    'D2': 'MuScriptor Medium F16 直转混音，取鼓',
    'D3': 'SW 鼓分轨 → YourMT3，仅取鼓',
    'D4': 'SW 鼓分轨 → ADTOF Frame RNN，随包阈值 ×0.75',
}


def table(lines, headers, entries):
    lines.extend(['', '| ' + ' | '.join(headers) + ' |',
                  '| ' + ' | '.join('---' for _ in headers) + ' |'])
    lines.extend('| ' + ' | '.join(map(str, row)) + ' |' for row in entries)
    lines.append('')


def scores(route, metric):
    values = [route[variant][metric]['f1'] for variant in ('uncorrected', 'corrected')]
    return ' → '.join(f'{value:.1%}' if value is not None else '—' for value in values)


def render(work, result, test_summary, code_commit):
    manifest = read_json(work / 'manifest.json')
    if digest(work / 'manifest.json') != result['manifest_sha256']:
        raise ValueError('Result and manifest hashes differ')
    items = result['items']
    if [row['id'] for row in items] != [song['id'] for song in pilot_songs(manifest)]:
        raise ValueError('Incomplete pilot or pilot results are from different songs')
    strata = Counter((song['drum_information'], song['split']) for song in manifest['songs'])
    lines = [
        '# Noto · RWC-P 三轨路线试跑', '',
        '本轮覆盖 5 首调参曲目，每首一个约 60 秒片段。成绩是**与 RWC-P 参考的一致度**，'
        '用于验证候选输出、计分和成本。路线选择及上线门槛留待后续，测试集保持封存。', '',
        '## 1. 冻结清单', '',
        f'- 清单 SHA-256 **{result["manifest_sha256"]}**。随机种子 {manifest["seed"]}，'
        f'评测脚本提交 {code_commit}。本地清单 {work / "manifest.json"}。',
        '- 按抽查盘点，钢琴为 GM 0–5 并排除明确借用键盘编号的轨，人声按官方映射排除，'
        '贝斯 GM 32–39，鼓为 GM 第 10 通道。整曲三轨均有才进入 72 首曲目池。',
        '- 按 DrumInformation 分层，调参 22 首、测试 50 首。'
        '各层先向下取整，再按最大余数分配名额。试跑取调参中按洗牌顺序排列的前三首音序器鼓和前两首现场鼓。',
        '- 中心起点取最靠近 60 秒的官方拍点，终点取最靠近起点加 60 秒的官方拍点。'
        '两端各保留 1 秒 WAV 上下文。P009 的已知问题段 0–3 秒在其评分片段之外。'
        '测试集只参与统一的清单与偏移冻结，试跑入口强制只接受冻好的五首调参曲目。',
    ]
    table(lines, ['DrumInformation', '调参', '测试'],
          [(label, strata[label, 'tuning'], strata[label, 'test'])
           for label in ('Drum sequences', 'Live drums', 'Drum loops', 'Without drums')])
    table(lines, ['试跑曲目', '中心区间（秒）', '参考偏移（毫秒）', '峰值相关 / 零偏移相关', '开始时 1 分钟负载'],
          [(item['id'], '–'.join(f'{point:.3f}' for point in item['center_seconds']),
            f'{item["offset"]["seconds"] * 1000:+.1f}',
            f'{item["offset"]["peak"]:.3f} / {item["offset"]["at_zero"]:.3f}',
            f'{item["one_minute_load"]:.2f}') for item in items])
    lines.extend([
        '## 2. 计分', '',
        '- 每个音符按起点归入中心半开区间。匹配沿用 e2e 的同类、同音高、起音偏差 ≤ 50 ms 的'
        '一对一最大匹配。汇总用五段 TP、FP、FN 计算 micro F1。',
        '- 每曲将非人声 MIDI 起点合成 10 ms 脉冲序列，用 ±249 ms 的平滑归一化互相关，'
        '与 22,050 Hz 混音的谱通量包络对齐。全曲有效音乐区间估计一个偏移。'
        '校正分将参考 MIDI 平移到音频时间线后再裁片，正值表示参考 MIDI 要后移。'
        'P052 的负偏移较大，周期性节奏与整曲局部漂移都可能影响估计，保留原始分和校正分。',
        '- 鼓只计底鼓 35/36 和军鼓 38/40，各组内等价。其他 GM 鼓件另计音符数。'
        '参考在中心窗内无该评分类别时，预测音符另列误报，同时保留在汇总 FP 中。',
        '- 贝斯同时报精确音高与音高 mod 12 的 F1。抽查发现八度歧义，参考 MIDI 保留原音高。'
        '钢琴**参考可靠性低**，混音抽查未能验证 MIDI 的音高和完整性。', '',
        '## 3. 候选可运行性',
    ])
    summary = result['summary']
    table(lines, ['候选', '本轮实现', '成功片段'],
          [(route, description, f'{summary.get(route, {}).get("songs", 0)}/5')
           for route, description in ROUTES.items()])
    lines.extend([
        '本机已有所有路线所需的包和权重。D4 使用已装的 adtof-pytorch 0.1.0 Frame RNN，'
        '权重实测 3,617,805 字节并通过 SHA-256 核对。原始模型内容 CC BY-NC-SA 4.0。'
        '本轮的 MuScriptor Medium 权重为 CC BY-NC 4.0。SW 和 Transkun 的商用权重许可仍待核实。'
        ' [ADTOF 原仓库](https://github.com/MZehren/ADTOF) · [PyTorch 移植](https://github.com/xavriley/ADTOF-pytorch)', '',
        'P5 是试验性音色判据，采样中高音区，至少 8 个可信音符且 60% 出现符合阈值的泛音偏移才启用 P2。'
        '分离串音、共鸣与采样钢琴会影响判断，琴种识别仍需验证。B7 阈值同样在跑分前固定。'
        'P1/B1/D1 共用一次混音 YourMT3，B2/D2/B7 共用一次混音 MuScriptor，'
        'P2/B5/B7/D3/D4 及 P5 共用一次 SW 分离。', '',
        '## 4. 与 RWC-P 参考的一致度', '',
        '每格为未校正 → 校正 F1。若路线失败，以「—」标示。有效片段数见上表。',
    ])
    score_rows, drums, absent = [], [], []
    for route, (category, _) in FIXED_ROUTES.items():
        metrics = ('exact', 'octave_free') if category == 'bass' else ('exact',)
        valid = [item['routes'][route] for item in items if item['routes'][route]['status'] == 'ok']
        for metric in metrics:
            label = route + ('（忽略八度）' if metric == 'octave_free' else '')
            per_song = [scores(item['routes'][route], metric) if item['routes'][route]['status'] == 'ok'
                        else '—' for item in items]
            total = scores(summary[route], metric) if route in summary else '—'
            score_rows.append((label, *per_song, total))
        if valid:
            absent.append((route, *(summary[route][variant]['exact']['absent_category_false_positives']
                                   for variant in ('uncorrected', 'corrected'))))
        if category == 'drums' and valid:
            parts = [entry['corrected']['other_drum_notes'] for entry in valid]
            drums.append((route, *(sum(sum(part[kind].values()) for part in parts)
                                   for kind in ('reference', 'prediction'))))
    song_ids = [item['id'] for item in items]
    table(lines, ['候选', *song_ids, 'micro F1'], score_rows)
    table(lines, ['鼓路线', '其他 GM 鼓参考音符数（校正后）', '其他 GM 鼓预测音符数'], drums)
    nonzero_absent = [row for row in absent if any(row[1:])]
    if nonzero_absent:
        table(lines, ['候选', '空参考类别误报（未校正）', '空参考类别误报（校正）'], nonzero_absent)
    else:
        lines.extend(['本轮成功路线的空参考类别误报统计为 0。', ''])
    table(lines, ['曲目', 'P5 实际选择', '可测 / 泛音偏移符合阈值的音符'],
          [(item['id'], item['p5']['route'], f'{item["p5"]["usable_notes"]} / {item["p5"]["stretched_notes"]}')
           if item['p5'] else (item['id'], '—', '—') for item in items])
    lines.extend([
        '## 5. 本机耗时与内存', '',
        'Apple Silicon，本轮各模型 CPU 2 线程、逐阶段串行。墙钟含加载、推理与阶段输出。'
        '峰值为约每 30 ms 采样的子进程树聚合 RSS，快速进程的采样值可能偏低。'
        '表中保留首跑阶段回执，避免将缓存命中计作模型时间。', '',
        f'开跑前 uptime 为 **{(work / "preflight-uptime.log").read_text().strip()}**。'
        '开跑时 1 分钟负载若超过 4，相关耗时会受同时运行的系统和应用进程影响。',
    ])
    names = list(dict.fromkeys(name for item in items for name in item['stages']))
    timings = []
    total_seconds = 0
    for name in names:
        entries = [item['stages'].get(name, {}) for item in items]
        successes = [entry for entry in entries if entry.get('status') == 'ok']
        average = mean(entry['elapsed_seconds'] for entry in successes) if successes else 0
        total_seconds += average
        timings.append((name, *(f'{entry["elapsed_seconds"]:.2f}' if entry.get('status') == 'ok' else '—'
                                 for entry in entries),
                        f'{average:.2f}' if successes else '—',
                        f'{max(e["peak_memory_bytes"] for e in successes) / 1024**3:.2f}' if successes else '—'))
    table(lines, ['阶段', *song_ids, '平均秒', '最高 RSS GiB'], timings)
    if all(summary.get(route, {}).get('songs') == 5 for route in FIXED_ROUTES):
        serial_hours = 72 * total_seconds / 3600
        elapsed = sum(item['wall_seconds_including_cache'] for item in items)
        lines.extend([
            f'本次五段运行的歌曲级墙钟合计 **{elapsed / 60:.1f} 分钟**（含裁片、缓存写读与计分）。'
            f'共享后每首各阶段均值合计 **{total_seconds:.1f} 秒**。'
            f'按每首一段、12 个候选外推到 72 首，串行约 **{serial_hours:.2f} 小时**。'
            f'两条歌曲流水线并行、每个进程仍用 2 线程，理想约 **{serial_hours / 2:.2f} 小时**。'
            '并行值假设吞吐完整翻倍，CPU、内存带宽和峰值 RSS 争用均待实测。'
            '估算覆盖每首八次模型阶段和关联的解码、音色判断、八度修正。'
            '正式选拔只在调参集比较单轨候选，测试集留给冻结组合。', '',
        ])
    else:
        lines.extend([
            f'可测阶段的平均值合计 {total_seconds:.1f} 秒。'
            '有候选缺少成功实测，72 首 × 全部候选的完整耗时尚不可估计。', '',
        ])
    lines.extend([
        '## 6. 待决定事项', '',
        '- 现有候选均有本地资产，本轮无需重新下载或安装。P5 琴种判断若保留，待决定如何提供独立琴种标注。',
        '- 由项目负责人决定是否按实测成本削减候选，并在使用剩余调参曲目之前冻结调整。'
        '本次五段试跑未产生赢家。',
        '- 正式选拔前待决定是否抽听偏移较大的曲目，并独立校核钢琴与贝斯参考。', '',
        f'本地验证 **{test_summary}**。逐段分数、鼓键计数、输入及阶段输出哈希见 {work / "pilot-results.json"}。'
        '音频、MIDI、缓存和结果均保存在主检出被忽略的 work/rwcp-eval/。', '',
    ])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--test-summary', required=True)
    parser.add_argument('--code-commit', required=True)
    args = parser.parse_args()
    body = render(args.work, read_json(args.work / 'pilot-results.json'), args.test_summary, args.code_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as report:
        report.write(body)


if __name__ == '__main__':
    main()
