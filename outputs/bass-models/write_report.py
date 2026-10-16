from pathlib import Path
from dataclasses import replace
from collections import Counter
import csv,json
from audio_midi.quality import load_reference_tracks,read_notes
root=Path('outputs/bass-models');stages=[json.loads((root/f'phase{i}-scores.json').read_text()) for i in [1,2,3]]
rows={r['id']:r for s in stages for r in s['rows']};base=rows['S1-pyin-0'];final=rows[stages[-1]['selected']]
refs=[replace(n,onset=(n.onset-.14)/.9995) for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if n.category=='bass' and .14<=n.onset<.14+.9995*60.0304375]
changes=[]
for i,n in enumerate(refs):
 old=i in base['matched_reference_indices'];new=i in final['matched_reference_indices'];status='保留命中' if old and new else '新增命中' if new else '丢失原命中' if old else '仍漏报'
 changes.append({'reference_index':i,'pitch':n.pitch,'audio_onset':n.onset,'old_matched':old,'new_matched':new,'change':status})
newpairs={j for i,j in final['matched_pairs']};newnotes=read_notes(Path(final['path']))
fp=[{'prediction_index':j,'pitch':n.pitch,'onset':n.onset,'offset':n.offset} for j,n in enumerate(newnotes) if j not in newpairs]
(root/'逐音变化.json').write_text(json.dumps({'reference_changes':changes,'selected_false_positives':fp},ensure_ascii=False,indent=2)+'\n')
with (root/'逐音变化.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['标准索引','音频起音秒','音高','上版53.33命中','新版62.34命中','变化'])
 for x in changes:w.writerow([x['reference_index'],x['audio_onset'],x['pitch'],x['old_matched'],x['new_matched'],x['change']])
lines=['# 贝斯音高模型、起音边界、分离器逐步对比','',
'**新版贝斯F1为62.34%，上版53.33%，提高9.00个百分点。最终保留原Demucs6s+pYIN，改为64ms短窗/4ms步长的音频起音检测，并禁止投票跨过下一起音。** 分离和pYIN基础估计没有升级为新模型；本轮没有训练或调用付费API。',
'', '## 按约定顺序比较','',
'所有正式评分固定：同音高、起音50ms、最大一对一，标准时间=预测时间×0.9995+0.14秒，标准窗口[0.14,60.14042228125)。不为任何候选重新拟合偏移，不按标准改音符。0–60是反复开发片段，标准为改编MIDI。',
'', '### 1：固定原贝斯音频，更换音高估计器','',
'保留同一O2后处理与音频起音；神经输出原生10ms/零起点，最近帧采到16ms，不跨空白插值。置信度门槛按登记分别测试，不能把不同模型的置信度当同一量纲。','',
'| 方案 | 匹配/预测/标准 | 误报 | 漏报 | F1 |','|---|---:|---:|---:|---:|']
for id in ['S1-pyin-0','S1-crepe-0','S1-crepe-1','S1-penn-0','S1-penn-1']:
 r=rows[id];lines.append(f"| {id} | {r['matched']}/{r['predicted']}/{r['reference']} | {r['extra']} | {r['missed']} | {r['f1']*100:.2f}% |")
lines+=['',
'这组条件下pYIN胜出，继续下一阶段。CREPE full与PENN均真实跑完60秒，不是假调用、没有用旧缓存冒充新模型。较低成绩不证明模型普遍差：这里只试了登记的置信度组合和同一后处理，没有为各模型做完整专项适配。',
'', '### 2：固定胜出的pYIN和置信度，改起音与投票边界','',
'| 方案 | 匹配/预测/标准 | 误报 | 漏报 | F1 |','|---|---:|---:|---:|---:|']
for label,id in [('原53.33控制','S1-pyin-0'),('旧起音+硬边界','S2-legacy-0'),('旧起音+32ms边界余量','S2-legacy-0.032'),('短窗起音+硬边界','S2-short-0'),('短窗起音+32ms边界余量','S2-short-0.032')]:
 r=rows[id];lines.append(f"| {label} | {r['matched']}/{r['predicted']}/{r['reference']} | {r['extra']} | {r['missed']} | {r['f1']*100:.2f}% |")
lines+=['',
'胜出的是短窗起音+硬边界：在原Demucs贝斯8k单声道上，以512采样点窗（64ms）、32采样点步长（4ms）、64mel/30–2000Hz计算起音强度；音频包络局部谷值回溯最多32ms。起音间隔最短80ms。音高投票窗口取随后320ms与下一起音中的较早者，至少80ms累计支持，避免邻音抢占。',
'',
'原高门槛0.2种子、低门槛0.05、同音高/voiced/能量与128ms扩展约束不变。新步骤对投票帧实行硬边界，不是整段前移；4ms是特征步长，不保证物理起音精度为4ms。音符结束取既有规则并截到下一起音/片尾，不宣称延音已验收。',
'', '### 3：固定选定转写，再比较分离结果','',
'| 分离源 | 匹配/预测/标准 | 误报 | 漏报 | F1 |','|---|---:|---:|---:|---:|']
for label,id in [('原Demucs6s','S2-short-0'),('htdemucs_ft bass专用checkpoint','S3-ft'),('已有SW BS-RoFormer','S3-sw')]:
 r=rows[id];lines.append(f"| {label} | {r['matched']}/{r['predicted']}/{r['reference']} | {r['extra']} | {r['missed']} | {r['f1']*100:.2f}% |")
lines+=['',
'ft使用官方htdemucs_ft bag中bass权重为1的d12395a8专用模型，实际跑新分离；没有运行其他三个专用模型。归一化和恢复沿用官方，seed0随机shift不保证与完整bag字节等价。SW复用已核验来源的bass.wav，两者均重新跑pYIN并采用完全相同的选定转写配置。此表是转写F1，不是分离SDR；没有录音室贝斯真值，不计算SDR。',
'', '## 逐音得失','',
'相对53.33版：保留17个旧命中，新增7个、丢失3个，净增4个。预测39→41、正确20→24、误报19→17、漏报16→12。不是只靠删音提高F1，也不是每个位置都改善。',
'', '| 变化 | 标准索引 | 音频秒 | 音高 |','|---|---:|---:|---:|']
for x in changes:
 if x['change'] in ['新增命中','丢失原命中']:lines.append(f"| {x['change']} | {x['reference_index']} | {x['audio_onset']:.3f} | {x['pitch']} |")
lines+=['',
'完整36音对照和剩余17误报见逐音变化.json/CSV。索引配对依赖固定最大匹配算法，邻近和改编差异使其不等于确定的原录音错误因果。',
'', '## 交付与当前路径','',
'当前研究路径：原MP3 → 原Demucs6s bass → pYIN32–261Hz/16ms步长 → 局部置信度扩展 → 短窗音频起音 → 不跨下一起音的音高投票 → 贝斯MIDI（指弹音色、力度80）。',
'',
'只替换贝斯六轨：389匹配/535预测/494标准，F1 **75.61%**（上版74.98%）。其他五轨和conductor的消息/tick完全相同，鼓继续85.56%、钢琴B保持不变。原版文件未覆盖。',
'',
'outputs/runs/bass-models/交付/有7种贝斯MID/WAV和仅换贝斯六轨MID/WAV，试听全部从MIDI合成，没有混原曲或在用户电脑播放。config/bass-models.lock.json固定本轮选择；旧config/bass-research.lock.json保留53.33历史基线。',
'', '## 运行与可复现范围','',
f"本轮11个候选、{len(set(r['sha256'] for r in rows.values()))}种不同MID（各阶段重复控制不重复计算为新方案）。9次模型进程尝试：2初始控制+2整段解码控制+2正式神经音高+1新ft分离+2源pYIN，全部一次成功，未触发模型重试。全部限CPU2/6GiB/1800s；import兼容错误和一次生成公式错误另见依赖与兼容记录.md，不当作质量失败。",
'',
'CREPE full正式约168.83秒、PENN约56.57秒，ft分离约34.48秒，ft/SW pYIN各约4.65秒；不是端到端整曲耗时总和。所有新增库/权重在项目ignored隔离目录，没有升级系统或原环境，没有外传音频。官方前处理脉冲核对零时间起点，原生帧和公共帧索引均可检查。',
'',
'生成脚本不读标准MIDI，只在阶段选择后使用完整配方标识进入下一阶段。解码、候选、参数、来源和SHA保存供审计。生成入口依赖已有原生音高/分离缓存，不是任意新歌一键入口；旧默认runner未切换。完整环境来源/权重与上游代码哈希见模型与依赖来源.json，商用许可仍需核实。',
'', '## 局限与验证','',
'仍有17误报/12漏报，贝斯尚未达到可靠复刻。0–60已反复选择，不能当独立泛化；本轮未看60–120或新歌曲。顺序筛选未穷尽所有模型×边界×分离组合，不能宣称全球最佳；神经模型只测了登记配置。F1仅检验音高/起音，未验力度/音符结束、未人工试听。',
'',
'先测试新增边界/时间格与Hz→MIDI回归，再实现；完成后冻结提交，由独立只读子agent核验实际缓存/候选、评分、规则、保护轨、打包和事实。结论另记。本轮保持最高结果，不对失败模型编造提升。','']
(root/'逐步对比报告.md').write_text('\n'.join(lines))
