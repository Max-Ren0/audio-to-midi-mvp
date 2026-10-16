"""Create stepwise and per-reference change reports from fixed scores."""
from pathlib import Path
from dataclasses import replace
import csv,json
from audio_midi.quality import load_reference_tracks,read_notes

root=Path('outputs/bass-refinement');d=json.loads((root/'逐步评分.json').read_text());rows={x['id']:x for x in d['rows']}
base=rows['baseline'];selected=rows[d['selected']]
refs=[replace(n,onset=(n.onset-.14)/.9995,offset=(n.offset-.14)/.9995) for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json'))
      if n.category=='bass' and .14<=n.onset<.14+.9995*60.0304375]
predictions={key:read_notes(Path(row['path'])) for key,row in rows.items()}
changes=[]
for i,n in enumerate(refs):
 item={'reference_index':i,'pitch':n.pitch,'audio_onset':n.onset,'audio_offset':n.offset,'stages':{}}
 for key in ['baseline',d['stage_best']['confidence_only_best'],d['stage_best']['onset_only_best'],d['selected']]:
  pair=next((p for p in rows[key]['matched_pairs'] if p['reference_index']==i),None)
  item['stages'][key]={'matched':pair is not None,'prediction_index':pair['prediction_index'] if pair else None,
                       'prediction_onset':predictions[key][pair['prediction_index']].onset if pair else None,
                       'delta_ms':pair['delta_ms'] if pair else None}
 old=item['stages']['baseline']['matched'];new=item['stages'][d['selected']]['matched']
 item['change']='保留命中' if old and new else '新增命中' if new else '丢失原命中' if old else '仍漏报'
 changes.append(item)
newhits={p['prediction_index'] for p in selected['matched_pairs']}
newfp=[{'prediction_index':i,'pitch':n.pitch,'onset':n.onset,'offset':n.offset} for i,n in enumerate(predictions[d['selected']]) if i not in newhits]
(root/'逐音变化.json').write_text(json.dumps({'reference_changes':changes,'selected_false_positives':newfp},ensure_ascii=False,indent=2)+'\n')
with (root/'逐音变化.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['标准索引','音频起音秒','音高','变化','原版命中','仅置信度命中','仅起音命中','组合命中','组合起音误差ms'])
 for x in changes:w.writerow([x['reference_index'],x['audio_onset'],x['pitch'],x['change'],*[s['matched'] for s in x['stages'].values()],x['stages'][d['selected']]['delta_ms']])
lines=['# 贝斯逐步优化与评估','',
'**本轮最优组合F1从41.38%提高到53.33%（+11.95个百分点）。这是当前已见0–60秒开发片段的改编MIDI一致度，不代表新歌曲或原录音真值准确率。** 没有改变正式50ms规则、时间映射或标准；没有新分离、模型推理、训练、API或付费。',
'', '## 分步结果','',
'先登记全部12候选，再无参考生成，最后统一评分。这里的“逐步”指拆开每项改动作对照，不是在看每次答案后继续扩展参数。','',
'| 改动 | 匹配/预测/标准 | 误报 | 漏报 | F1 |','|---|---:|---:|---:|---:|']
for label,key in [('原版','baseline'),('只改置信度：最佳C1',d['stage_best']['confidence_only_best']),('只改起音：O2',d['stage_best']['onset_only_best']),('组合：C3-O2',d['selected'])]:
 x=rows[key];lines.append(f"| {label} | {x['matched']}/{x['predicted']}/{x['reference']} | {x['extra']} | {x['missed']} | {x['f1']*100:.2f}% |")
lines+=['',
'置信度处理单独使用均退步：C1/C2为39.56%，C3为38.30%，不能单独替换基线。起音重建O1为44.44%，加包络谷值回溯的O2为49.32%。C1/C2+O2为51.35%，C3+O2为53.33%。没有因负结果追加新参数。',
'', '## 实际修改了什么','',
'原MP3 → 原Demucs贝斯 → 原pYIN缓存3752帧 → 局部置信度扩展 → 音频起音引导音符 → 清理 → 指弹电贝斯MIDI。',
'',
'1. **局部双门槛**：原0.2高门槛仍用作种子；同一四舍五入音高、仍voiced且过能量门槛的连续片段内，允许概率≥0.05的帧在距离高门槛种子最多128ms范围被保留。原始音高没有修改，没有凭空生成音高；没有高置信度支持的低置信度片段不补。',
'2. **起音与音高解耦**：仍使用原音频检测到的起音；允许回到其之前最多96ms的包络局部谷值，不做整段固定减时或按标准吸附。最短起音间隔80ms，近邻保留较早者。',
'3. **按起音重新建音符**：开始时间取上述音频起音；在随后320ms内按置信度加权投票选音高，至少有80ms累计帧支持。结束不超过下一起音及片尾。整段没有检测到任何起音时退回原切分；保留文件开头已在响的音。',
'',
'这里的支持帧是累计80ms，不要求连续80ms；320ms投票窗可能跨越下一起音，会有邻音竞争的风险。离线方法需要向后看320ms，不是零延迟实时转写。音符结束与力度不在本次F1验收内，力度仍80，不宣称还原了延音或演奏表情。',
'', '## 得分提高是否掩盖退步','',
'新组合保留原版18个命中中的12个，新增命中8个，同时丢失原有命中6个，净增加2个。预测总数51降到39，误报数33降到19，是本轮F1提升的重要来源；并不是所有位置都更好。',
'',
'| 变化 | 标准索引 | 音频起音秒 | 音高 |','|---|---:|---:|---:|']
for x in changes:
 if x['change'] in ['新增命中','丢失原命中']:lines.append(f"| {x['change']} | {x['reference_index']} | {x['audio_onset']:.3f} | {x['pitch']} |")
lines+=['',
'完整36个标准音的逐步命中状态和组合剩余19误报见逐音变化.json/CSV。匹配是最大一对一；存在多个合法配对时，具体索引集合可能随匹配路径而变，不能把索引变化全部当作同一次真实演奏被修复或破坏。',
'', '## 六轨与交付','',
'只替换贝斯的六轨：385匹配/533预测/494标准，整体F1 **74.98%**（原73.72%）。钢琴B、鼓85.56版和木吉他/电吉他/弦乐以及conductor的原消息与ticks完全不变；原文件保留，新文件另存。',
'',
'交付目录outputs/runs/bass-refinement/交付/含原版、置信度单改、起音单改、组合最优四份贝斯MID和WAV，以及仅换贝斯的六轨MID/WAV。试听为GeneralUser GS从MIDI渲染，不含原曲；没有在用户电脑播放或人工听辨。全部12候选MID、帧掩码和生成证据留在candidates目录。',
'', '## 固定与复现','',
'config/bass-research.lock.json绑定本轮选择C3-O2、来源与产物SHA256。原默认transcribe_monophonic没有改动；新研究模块src/audio_midi/bass_refinement.py执行本轮方法。generate.py用当前输入SHA及已验证pYIN帧重建全部12候选，不接收标准；score.py独立评分。生成CLI支持--ledger写临时收据，避免临时复验覆盖项目文件。',
'',
'本轮真实临时目录重建12候选MID和生成证据JSON逐字节一致。该入口依赖现有帧缓存，不是任意新歌的完整一键推理入口，也没有把新规则静默加入旧生产默认。无参考构造、没有GM改键或八度修正。',
'', '## 仍然存在的问题','',
'最优仍有19误报/16漏报，召回55.56%，尚不能称贝斯转写已达标。标准是改编，当前片段已反复用于选择，存在过拟合风险；放宽容差不参与选择。本次仅优化已固定分离结果上的后处理，不能据此证明分离质量改善。',
'',
'下一步应先核听新增/丢失位置，并考虑更可靠的起音/跨音符投票边界；是否继续改动由用户决定。本轮不再扩展候选、不读60–120，六轨都确定后再按约定冻结整版回归。',
'', '## 验证安排','',
'新增边界测试先观察未实现失败，再实现；涵盖高置信度种子、同音高/能量约束、扩展上限、起音/音高解耦、重复音、短音、空结果/无起音回退、片首片尾。完整测试后冻结提交，再由独立只读子agent检查实际候选、评分、保护轨、包和规则；结论另记。','']
(root/'逐步优化报告.md').write_text('\n'.join(lines))
