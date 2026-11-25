"""Render the completed RWC-P tuning round to Markdown."""
import argparse
from collections import Counter
from pathlib import Path

from prepare import digest
from report import ROUTES, table
from run_dev import CONFIDENT, MANIFEST_SHA, summarize, tuning_songs
from run_pilot import FIXED_ROUTES, read_json, verify_hash


TRACKS = {'piano': '钢琴', 'bass': '贝斯', 'drums': '鼓'}
OFFSET_STATUS = {
    'applied': '已应用', 'dead_zone': '死区', 'weak_peak': '峰值不足',
    'ambiguous': '竞争峰过近', 'search_edge': '搜索边缘', 'insufficient_support': '缺少起音证据',
}


def fmt(value, pattern='.3f'):
    return format(value, pattern) if value is not None else '—'


def render(work):
    manifest_path = work / 'manifest.json'
    result_path = work / 'dev-results.json'
    offset_path = work / 'dev-offsets-v2.json'
    result = read_json(result_path)
    verify_hash(manifest_path, MANIFEST_SHA)
    verify_hash(offset_path, result['offset_sha256'])
    frozen = read_json(offset_path)
    songs = tuning_songs(read_json(manifest_path))
    if set(result['items']) != {song['id'] for song in songs}:
        raise ValueError('Only a complete tuning run can produce a report')
    items = [result['items'][song['id']] for song in songs]
    if any(item['offset'] != frozen['offsets'][item['id']] for item in items):
        raise ValueError('Result offsets differ from the frozen input')
    summary = summarize(items)
    if summary != result['summary']:
        raise ValueError('Stored score summary differs from a new calculation')
    low = [item for item in items if item['offset']['status'] not in CONFIDENT]
    labels = {cat: choice['winner'] for cat, choice in summary['winners'].items()}
    lines = [
        '# Noto · RWC-P 调参单项赛', '',
        '22 首调参曲目 × 12 条单轨路线。分数表示**与 RWC-P 参考的一致度**。'
        '本报告只使用调参集。50 首封存测试曲目留给另行冻结的团体赛，独立真值的上线门槛待定。', '',
        '## 1. 按冻结规则选出的路线', '',
    ]
    rows = []
    for cat, choice in summary['winners'].items():
        winner = choice['winner']
        winner_score = summary['routes'][winner]['corrected']['exact']['f1']
        decision = ('与 ' + '、'.join(route for route in choice['ties'] if route != winner)
                    + ' 打平，比平均独立路线耗时更低') if len(choice['ties']) > 1 else '主指标最高'
        rows.append((TRACKS[cat], winner, fmt(winner_score, '.2%'), choice['leader'], decision))
    table(lines, ['轨道', '入选', '校正后 micro F1', '主指标最高', '决定依据'], rows)
    lines += [
        '**钢琴参考可靠性低。** RWC-P 含错音、漏音及录音与 MIDI 的时间差。钢琴未完成独立逐音校订，'
        '贝斯同时给出忽略八度的结果以揭示音高歧义。', '',
        '## 2. 规则和分数', '',
        f'- 规则冻结提交 {result["rule_commit"]}，先于其余 17 首模型运行。'
        f'原清单 SHA-256 **{MANIFEST_SHA}**。v2 偏移清单 SHA-256 **{result["offset_sha256"]}**。',
        '- 估计仅使用片段含上下文的 WAV 和匹配的非人声 MIDI。±100 ms 取峰，要求峰 ≥0.30、'
        '高于 ±3 帧外次峰 ≥0.05 且避开搜索边缘。候选共用同一偏移。'
        '通过后减去谱通量系统延迟 20 ms，补偿后绝对偏移 <50 ms 保持不校正。低置信曲目也保持不校正。',
        '- v2 的设计使用五段试跑和试跑候选的偏移扫描，存在选择偏差。'
        '完整调参集成绩仍用于路线选择，须以封存测试集上冻结组合的成绩做后续验证。',
        '- 只计中心窗内的起音，使用 ±50 ms 一对一匹配。贝斯以精确音高为主，鼓只计 GM 35/36、38/40 两组。',
        '主指标是 22 首校正后 micro F1。距最高分差值严格小于 2 个百分点的候选打平，'
        '按平均独立路线耗时决胜。逐曲对决以各首校正后 F1 的精确值比较。',
        f'- 高置信敏感性分析保留 {len(items) - len(low)}/22 首。空输出作为零预测计分，'
        '另列次数。只有未计分的鼓件仍算非空。', '',
    ]
    for category, label in TRACKS.items():
        lines += [f'### {label}', '']
        routes = [route for route, (cat, _) in FIXED_ROUTES.items() if cat == category]
        rows = []
        for route in routes:
            m = summary['routes'][route]
            for metric in ('exact', 'octave_free') if category == 'bass' else ('exact',):
                rows.append((route if metric == 'exact' else f'{route}（忽略八度）',
                             *(fmt(m[key][metric]['f1'], '.2%')
                               for key in ('uncorrected', 'corrected', 'confident')),
                             fmt(m['seconds'], '.2f') if metric == 'exact' else '—',
                             m['empty'] if metric == 'exact' else '—'))
        table(lines, ['路线', '未校正', '校正后', '仅高置信', '独立路线均秒', '空输出次数'], rows)
        lines += ['<details>', f'<summary>{label}逐曲分数与两两对决</summary>', '']
        table(lines, ['曲目', *routes],
              [(item['id'], *[
                  ' → '.join(fmt(item['routes'][route][variant]['exact']['f1'], '.1%')
                             for variant in ('uncorrected', 'corrected'))
                  + ('（空）' if item['routes'][route]['status'] == 'empty' else '')
                  for route in routes]) for item in items])
        table(lines, ['两条路线（左对右）', '胜', '平', '负', '未定义'],
              [(f'{pair["left"]} 对 {pair["right"]}', pair['win'], pair['draw'], pair['loss'], pair['undefined'])
               for pair in summary['head_to_head'][category]])
        lines += ['</details>', '']
    lines += ['## 3. 偏移低置信与空输出', '']
    if low:
        table(lines, ['低置信曲目', '原因', '原估计 ms', '峰值', '领先次峰'],
              [(i['id'], OFFSET_STATUS[i['offset']['status']],
                fmt(i['offset'].get('raw_seconds', 0) * 1000, '+.1f'),
                fmt(i['offset'].get('peak')), fmt(i['offset'].get('margin'))) for i in low])
    else:
        lines += ['本轮没有偏移低置信曲目。', '']
    lines += ['<details>', '<summary>22 首偏移记录</summary>', '']
    table(lines, ['曲目', '原估计 ms', '补偿后 ms', '应用 ms', '峰值', '领先次峰', '判断', '周期歧义'],
          [(i['id'], *(fmt(i['offset'][key] * 1000, '+.1f') if key in i['offset'] else '—'
                       for key in ('raw_seconds', 'calibrated_seconds', 'seconds')),
            fmt(i['offset'].get('peak')), fmt(i['offset'].get('margin')),
            OFFSET_STATUS[i['offset']['status']], '有' if i['offset'].get('periodic_ambiguity') else '—')
           for i in items])
    lines += ['</details>', '']
    empty = [(route, m['empty'], '、'.join(m['empty_ids']))
             for route, m in summary['routes'].items() if m['empty']]
    if empty:
        table(lines, ['路线', '次数', '空输出曲目'], empty)
    else:
        lines += ['全部路线均输出了目标音符。', '']
    gates = Counter(item['p5']['route'] for item in items)
    lines += [f'- P5 实际分支 P1 {gates["P1"]} 首、P2 {gates["P2"]} 首。', '',
              '## 4. 耗时与资源', '']
    stage_names = list(dict.fromkeys(stage for item in items for stage in item['stages']))
    stage_rows = []
    shared = 0.
    for stage in stage_names:
        records = [item['stages'][stage] for item in items]
        seconds = sum(r['elapsed_seconds'] for r in records)
        shared += seconds
        stage_rows.append((stage, f'{seconds / len(items):.2f}', f'{seconds / 60:.2f}',
                           f'{max(r["peak_memory_bytes"] for r in records) / 1024**3:.2f}'))
    table(lines, ['共享阶段', '平均秒', '累计分钟', '最高 RSS GiB'], stage_rows)
    active = sum(item['elapsed_seconds'] for item in items)
    waiting = sum(item['wait_seconds'] for item in items)
    load_path = work / 'dev-preflight-uptime.log'
    if load_path.exists():
        lines += [f'启动前 uptime 为 {load_path.read_text().strip()}。', '']
    if (work / 'dev-resume-uptime.log').exists():
        lines += [
            '第 10 首前提高串行启动负载上限至 8，停在等待阶段后复用已完成检查点和模型缓存。'
            '恢复后每首保存完整 uptime，此前保存了各首的一分钟负载。', '',
        ]
    lines += [
        f'22 首有效阶段累计 **{shared / 3600:.2f} 小时**，包含 5 首已缓存的实测阶段。'
        f'本轮新增评测实际工作墙钟 **{active / 3600:.2f} 小时**（含缓存读取、裁片和计分），'
        f'等待负载下降 **{waiting / 60:.1f} 分钟**。本轮按阶段串行。',
        '', '## 5. 待确认的团体方案', '',
        f'- **S5** 由钢琴 {labels["piano"]}、贝斯 {labels["bass"]}、鼓 {labels["drums"]} 组成。'
        '按需共用 SW、YourMT3 或 MuScriptor 的中间结果，各轨保持试跑的模型配置。',
        *(f'  - {route} 使用 {ROUTES[route]}。' for route in labels.values()),
        '- **S6** 沿用 S5，各轨发布前补一层仅依赖音频与候选输出的乐器存在判断。'
        '仅在调参侧校准门槛和不确定时的保留策略，分别记录空轨误报与误删，再与组件一同冻结。'
        '存在判断与组合分别提交冻结后进入团体赛。',
        '', f'结果 JSON SHA-256 **{digest(result_path)}**。冻结曲目、偏移曲线、每首阶段计时及打分均保存在本机 {work}。', '',
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
