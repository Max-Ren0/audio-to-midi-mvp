"""Render a completed paired RWC-P team evaluation."""
import argparse
from collections import Counter
from pathlib import Path

from prepare import digest
from report import ROUTES, table
from report_dev import OFFSET_STATUS, fmt
from run_dev import CONFIDENT, MANIFEST_SHA
from run_pilot import HERE, read_json, verify_hash
from run_team import COMBOS, TRACKS, summarize, test_songs


LABEL = {'piano': '钢琴', 'bass': '贝斯', 'drums': '鼓'}


def interval(bounds, delta=False):
    if bounds is None:
        return '—'
    if delta:
        return '[' + ', '.join(f'{bound * 100:+.2f}' for bound in bounds) + ']'
    return '[' + ', '.join(f'{bound:.2%}' for bound in bounds) + ']'


def render(work):
    path = work / 'team-results.json'
    result = read_json(path)
    dev = read_json(work / 'dev-results.json')
    presence = read_json(work / 'presence-tuning.json')
    verify_hash(work / 'manifest.json', MANIFEST_SHA)
    verify_hash(work / 'team-offsets-v2.json', result['offset_sha256'])
    verify_hash(HERE / 'team-config.json', result['combinations_sha256'])
    verify_hash(HERE / 'presence-config.json', result['presence_sha256'])
    config = read_json(HERE / 'team-config.json')
    songs = test_songs(read_json(work / 'manifest.json'))
    if set(result['items']) != {song['id'] for song in songs}:
        raise ValueError('Expected exactly the frozen test cohort')
    items = [result['items'][song['id']] for song in songs]
    scores = summarize(items)
    if scores != result['summary']:
        raise ValueError('Stored team score summary differs from a new calculation')
    combos, intervals = scores['combinations'], scores['intervals']
    dev_summary = dev['summary']
    confident = [row for row in items if row['offset']['status'] in CONFIDENT]
    low = [row for row in items if row['offset']['status'] not in CONFIDENT]
    deltas = {}
    for c in TRACKS:
        values = {combo: combos[combo]['tracks'][c]['corrected']['exact']['f1'] for combo in COMBOS}
        deltas[c] = {pair: values[a] - values[b] for pair in intervals[c]['deltas']
                     for a, b in [pair.split('-')]}
    delta_summary = '、'.join(f'{LABEL[c]} {deltas[c]["S5-S3"] * 100:+.2f}' for c in TRACKS)
    suppressed = sum(combos['S6']['tracks'][category]['gated'] for category in TRACKS)
    lines = [
        '# Noto · RWC-P 冻结团体赛', '',
        f'**在 50 首封存曲目上，S5 相对当前组合 S3 的校正后 micro F1 差值为 {delta_summary} 个百分点。**'
        f'S6 的存在判断抑制了 {suppressed} 条非空预测轨。', '',
        '分数表示**与 RWC-P 参考的一致度**。钢琴参考可靠性低。',
        '', '## 1. 单项赛与被冻结的组合', '',
    ]
    table(lines, ['轨道', '22 首入选路线', '调参校正后 F1', '决定依据'], [
        (LABEL[c], dev_summary['winners'][c]['winner'],
         fmt(dev_summary['routes'][dev_summary['winners'][c]['winner']]['corrected']['exact']['f1'], '.2%'),
         '2 个百分点内打平，按耗时决胜' if len(dev_summary['winners'][c]['ties']) > 1 else '主指标最高')
        for c in TRACKS
    ])
    table(lines, ['组合', '钢琴', '贝斯', '鼓', '存在判断'], [
        (combo, *config['recipes'][combo], '应用冻结阈值' if combo == 'S6' else '关闭')
        for combo in COMBOS
    ])
    lines += [
        f'- 偏移与单项赛规则提交 {dev["rule_commit"]}，团体组合冻结提交 {result["freeze_commit"]}。',
        f'- 测试偏移冻结 SHA-256 {result["offset_sha256"]}，组合配置 SHA-256 {result["combinations_sha256"]}。',
        '- 使用规则 v2 的局部偏移，宽度 ±100 ms，置信筛选后减 20 ms，再应用 50 ms 死区。'
        '曲目的所有模型使用同一偏移。各组合按实际组装并回读的 MIDI 计分。',
        f'- 校正后为主指标，仅高置信分析用 {len(confident)}/50 首。'
        '贝斯精确音高为主，另报忽略八度。鼓只计底鼓 35/36 和军鼓 38/40。',
        f'- 95% 区间用同一批按歌曲配对的 {config["bootstrap_replicates"]:,} 次重采样，'
        f'随机种子 {config["bootstrap_seed"]}。对每次采样汇总 TP、FP、FN 后算 micro F1 与差值。'
        '区间跨 0 时，这批歌曲支持的差异方向仍不明确。', '',
        '## 2. 测试集成绩', '',
    ]
    for category in TRACKS:
        lines += [f'### {LABEL[category]}', '']
        entries = []
        for combo in COMBOS:
            values = combos[combo]['tracks'][category]
            for metric in ('exact', 'octave_free') if category == 'bass' else ('exact',):
                label = combo if metric == 'exact' else combo + '（忽略八度）'
                entries.append((label, *(fmt(values[key][metric]['f1'], '.2%') for key in
                                         ('uncorrected', 'corrected', 'confident')),
                                interval(intervals[category]['absolute'][combo]) if metric == 'exact' else '—'))
        table(lines, ['组合', '未校正', '校正后', '仅高置信', '主指标 95% CI'], entries)
        lines += ['<details>', f'<summary>{LABEL[category]} 逐曲分数（未校正 → 校正）</summary>', '']
        table(lines, ['曲目', *COMBOS], [
            (i['id'], *[' → '.join(fmt(i['combinations'][combo]['scores'][category][variant]['exact']['f1'], '.1%')
                                    for variant in ('uncorrected', 'corrected'))
                        + ('（空）' if i['combinations'][combo]['scores'][category]['status'] == 'empty' else '')
                        for combo in COMBOS]) for i in items])
        lines += ['</details>', '']
    table(lines, ['校正后差值（百分点）', *[LABEL[c] for c in TRACKS]], [
        (pair, *(f'{deltas[c][pair] * 100:+.2f}，95% CI {interval(intervals[c]["deltas"][pair], True)}'
                 for c in TRACKS)) for pair in intervals['piano']['deltas']
    ])
    lines += ['## 3. 空输出、误报与存在判断', '']
    table(lines, ['轨道', '调参参考存在／缺失', '阈值（音符）', '调参删除误报音符', '正例误删'], [
        (LABEL[c], f'{presence[c]["positive"]} / {presence[c]["negative"]}', presence[c]['threshold'],
         presence[c]['saved_false_notes'], presence[c]['removed_positive_tracks']) for c in TRACKS
    ])
    lines += [
        '阈值 0 表示关闭，对参考缺失片段不足 3 个的轨保持保守。'
        '预测缺失也可能来自模型输出为空。以下误报按参考确实为空的中心片段统计，鼓以所有 GM 键判断存在。', '',
    ]
    table(lines, ['组合', '轨道', '模型空', '发布空', '判断移除', '误删正例', '参考缺失', '误报轨／音符'], [
        (combo, LABEL[c], data['model_empty'], data['empty'], data['gated'], data['gated_positive'],
         data['reference_absent'], f'{data["absent_false_tracks"]} / {data["absent_false_notes"]}')
        for combo in COMBOS for c, data in combos[combo]['tracks'].items()
    ])
    if not any(config['thresholds'].values()):
        lines += ['所有阈值均为 0，这次 S6 的实际输出与 S5 一样。此次数据无法验证存在判断能否减少适用场景中的误报。', '']
    lines += ['## 4. 低置信偏移与一键耗时', '']
    if low:
        table(lines, ['曲目', '低置信原因', '峰值', '领先次峰'],
              [(i['id'], OFFSET_STATUS[i['offset']['status']], fmt(i['offset'].get('peak')),
                fmt(i['offset'].get('margin'))) for i in low])
    else:
        lines += ['50 首均通过偏移置信检查。', '']
    table(lines, ['组合', '一键有效 MIDI', '平均等效串行秒', '累计等效小时'], [
        (combo, f'{combos[combo]["success"]}/50', f'{combos[combo]["mean_seconds"]:.2f}',
         f'{combos[combo]["total_seconds"] / 3600:.2f}') for combo in COMBOS
    ])
    batches = Counter(batch['jobs'] for batch in result['batches'])
    seconds = sum(batch['elapsed_seconds'] for batch in result['batches'])
    lines += [
        f'同一次裁片共用可复用模型阶段，实测批次合计 **{seconds / 3600:.2f} 小时**'
        f'（{batches[1]} 个串行批次、{batches[2]} 个双歌曲批次）。'
        '各组合的等效耗时汇总其实际需要的独立阶段及组装读写，不重复跑模型计时。'
        '一键成功要求至少一轨有效 MIDI 且能回读。', '',
        '## 5. 局限与默认路线建议', '',
        '- RWC-P 的 MIDI 参考存在计时及音高误差，钢琴参考可靠性低，贝斯的八度有歧义。'
        '这些成绩衡量候选与参考的相对一致度。v2 看过五段试跑及其候选扫描后设计，存在选择偏差。',
        '- 72 首整曲均从三轨齐全的池中选出，真实缺轨片段稀少。弱轨误删与真实无乐器的误报仍需另作专项验证。',
        '- RWC-P 许可为 CC BY-NC 4.0，本轮用作本地研究比较。', '',
    ]
    if config['recipes']['S5'] == config['recipes']['S3']:
        lines += ['S5 与 S3 的路线相同，建议保留现有 S3，继续用独立参考验证。', '']
    elif (all(deltas[c]['S5-S3'] >= 0 for c in TRACKS)
          and any(intervals[c]['deltas']['S5-S3'] and intervals[c]['deltas']['S5-S3'][0] > 0 for c in TRACKS)):
        lines += ['建议把 S5 作为下一版默认路线候选。它各轨一致度均未低于 S3，且至少一轨的配对区间高于零。'
                  '正式采用前仍需通过独立真值的验证。', '']
    else:
        lines += ['沿用现有 S3 作为保守默认建议。S5 作为冻结的备选组合，'
                  '根据各轨差值和区间，结合独立真值确认哪些轨道值得替换。', '']
    lines += [
        '当前一键入口的默认值保持原样。', '',
        f'测试结果 JSON SHA-256 **{digest(path)}**。报告中的测试集差值均由同一轮 50 首配对数据生成。', '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    body = render(args.work)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as report:
        report.write(body)


if __name__ == '__main__':
    main()
