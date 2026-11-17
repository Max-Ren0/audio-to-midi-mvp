"""Score baseline vs current-best routes per track across all prepared items.

Primary metric (same as the rest of the project): one-to-one matching, same category and
pitch (drums: same GM key), onset within 50 ms. Supplementary drum metric maps GM keys to
kit pieces (kick / snare / hi-hat / tom / cymbal) before matching.

Usage (repo root):
    PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/score.py outputs/runs/multi-song-eval/items outputs/multi-song-eval/results.json
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

from audio_midi.evaluate import evaluate
from audio_midi.events import NoteEvent
from audio_midi.muscriptor_routing import parse_note_lines
from audio_midi.quality import read_notes

TRACKS = ('piano', 'bass', 'drums', 'acoustic_guitar', 'electric_guitar', 'strings')
KIT = {35: 36, 36: 36, 37: 38, 38: 38, 39: 38, 40: 38, 42: 42, 44: 42, 46: 42,
       41: 45, 43: 45, 45: 45, 47: 45, 48: 45, 50: 45,
       49: 49, 51: 49, 52: 49, 53: 49, 55: 49, 57: 49, 59: 49}


# Slakh bass MIDI is written one octave above the sounding pitch (checked with pYIN on the
# bass stems: audio median ~43 vs MIDI median ~55). Both routes output sounding pitch, so
# Slakh bass references are scored one octave down. See README for the evidence.
SLAKH_BASS_SHIFT = -12


SPLICE_REFUSED = 'Baseline requires exactly one bass and one drums track'


def raw_fallback_ok(item_dir):
    """True only when MuScriptor inference finished (engine summary line 'notes <n>' at the end of
    its log) and the entry script then refused to splice because the baseline lacks a bass or drums
    track. Interrupted runs with partial NOTE lines do not qualify."""
    engine_log = item_dir / 'muscriptor/muscriptor.log'
    runner_log = item_dir / 'muscriptor.log'
    if not (engine_log.exists() and runner_log.exists()):
        return False
    tail = engine_log.read_text().splitlines()[-5:]
    finished = any(line.split()[:1] == ['notes'] and line.split()[1:2] and line.split()[1].isdigit() for line in tail)
    return finished and SPLICE_REFUSED in runner_log.read_text()


def ref_notes(path, source):
    out = []
    for n in json.loads(Path(path).read_text())['notes']:
        pitch = n['pitch'] + (SLAKH_BASS_SHIFT if source.startswith('BabySlakh') and n['category'] == 'bass' else 0)
        out.append(NoteEvent(n['category'], pitch, n['onset'], n['offset']))
    return out


def modal_offset(ref, pred, cat):
    """Most common pitch difference between each reference note and its nearest-onset prediction."""
    from collections import Counter
    c = Counter()
    preds = [p for p in pred if p.category == cat]
    for r in (x for x in ref if x.category == cat):
        near = [p.pitch - r.pitch for p in preds if abs(p.onset - r.onset) <= .05]
        if near:
            c[min(near, key=abs)] += 1
    return c.most_common(1)[0] if c else None


def clip(notes, duration):
    return [n for n in notes if 0 <= n.onset < duration]


def kit(notes, kit_only=False):
    return [replace(n, pitch=KIT.get(n.pitch, n.pitch)) for n in notes
            if n.category == 'drums' and (not kit_only or n.pitch in KIT)]


def add(acc, key, m):
    a = acc.setdefault(key, {'tp': 0, 'fp': 0, 'fn': 0, 'songs': 0, 'song_f1': []})
    a['tp'] += m['tp']; a['fp'] += m['fp']; a['fn'] += m['fn']; a['songs'] += 1
    if m['f1'] is not None: a['song_f1'].append(m['f1'])


def finish(acc):
    out = {}
    for k, a in acc.items():
        d = 2 * a['tp'] + a['fp'] + a['fn']
        out[k] = {'songs': a['songs'], 'tp': a['tp'], 'fp': a['fp'], 'fn': a['fn'],
                  'micro_f1': round(2 * a['tp'] / d, 4) if d else None,
                  'precision': round(a['tp'] / (a['tp'] + a['fp']), 4) if a['tp'] + a['fp'] else None,
                  'recall': round(a['tp'] / (a['tp'] + a['fn']), 4) if a['tp'] + a['fn'] else None,
                  'mean_song_f1': round(sum(a['song_f1']) / len(a['song_f1']), 4) if a['song_f1'] else None}
    return out


def main(items, dest):
    manifest = json.loads((items / 'manifest.json').read_text())
    per_item = []; agg = {'baseline': {}, 'best': {}}; agg_src = {}; missing = []; raw_fallback = []
    for m in manifest:
        d = items / m['id']; dur = m['window_seconds'][1] - m['window_seconds'][0]
        ref = ref_notes(d / 'reference.json', m['source'])
        if not (d / 'baseline/result.mid').exists():
            missing.append({'id': m['id'], 'route': 'baseline'}); continue
        base = clip(read_notes(d / 'baseline/result.mid'), dur)
        best = list(base)
        pb = d / 'piano-b/钢琴-B.mid'
        if 'piano' in m['contains']:
            if pb.exists():
                best = [n for n in best if n.category != 'piano'] + [n for n in clip(read_notes(pb), dur) if n.category == 'piano']
            else:
                missing.append({'id': m['id'], 'route': 'piano-b'})
        mu = d / 'muscriptor/Noto-MuScriptor贝斯鼓.mid'
        if {'bass', 'drums'} & set(m['contains']):
            raw_log = d / 'muscriptor/muscriptor.log'
            mu_notes = None
            if mu.exists():
                mu_notes = clip(read_notes(mu), dur)
            elif raw_fallback_ok(d):
                # The entry script refuses to splice when the baseline lacks a bass or drums
                # track; MuScriptor itself finished, so score its raw notes directly.
                mu_notes = clip(parse_note_lines(raw_log.read_text()), dur)
                raw_fallback.append(m['id'])
            if mu_notes is not None:
                best = [n for n in best if n.category not in ('bass', 'drums')] + [n for n in mu_notes if n.category in ('bass', 'drums')]
            else:
                missing.append({'id': m['id'], 'route': 'muscriptor'})
        if any(x['id'] == m['id'] for x in missing):
            continue  # keep the comparison paired: score an item only when every route it needs finished
        row = {'id': m['id'], 'source': m['source'], 'contains': m['contains'], 'tracks': {}}
        for route, pred in (('baseline', base), ('best', best)):
            r = evaluate(ref, pred)
            for t in TRACKS:
                if t in m['contains']:
                    add(agg[route], t, r[t]); add(agg_src.setdefault((route, m['source'].split(' ')[0]), {}), t, r[t])
                    row['tracks'].setdefault(t, {})[route] = {k: r[t][k] for k in ('tp', 'fp', 'fn', 'f1')}
                    row['tracks'][t][route]['modal_pitch_offset'] = modal_offset(ref, pred, t) if t != 'drums' else None
                else:
                    extra = sum(n.category == t for n in pred)
                    if extra:
                        row.setdefault('absent_category_extra_notes', {}).setdefault(route, {})[t] = extra
            if 'drums' in m['contains']:
                k = evaluate(kit(ref), kit(pred))['drums']
                add(agg[route], 'drums_kit_piece', k)
                row['tracks']['drums'][route + '_kit_piece_f1'] = k['f1']
                # Slakh drum stems also hold auxiliary percussion (tambourine, cabasa, ...);
                # kit-only drops keys outside the drum kit from both sides.
                ko = evaluate(kit(ref, True), kit(pred, True))['drums']
                add(agg[route], 'drums_kit_only', ko)
                row['tracks']['drums'][route + '_kit_only_f1'] = ko['f1']
        per_item.append(row)
    absent = {}
    for row in per_item:
        for route, cats in row.get('absent_category_extra_notes', {}).items():
            for t, n in cats.items():
                absent.setdefault(route, {}).setdefault(t, 0)
                absent[route][t] += n
    result = {'reference_corrections': {'BabySlakh bass': SLAKH_BASS_SHIFT},
              'conditioning': 'routes are chosen and F1 is accumulated using the reference category list of each item; '
                              'notes predicted for categories absent from the reference are not in any F1 and are totalled in absent_category_extra_notes_total',
              'absent_category_extra_notes_total': absent,
              'metric': 'one-to-one, same category and pitch (drums: GM key), onset <= 50 ms; drums_kit_piece maps GM keys to kick/snare/hi-hat/tom/cymbal; drums_kit_only additionally drops non-kit percussion keys from reference and prediction',
              'routes': {'baseline': 'YourMT3 yptf_moe_nops whole mix',
                         'best': 'piano: piano-B (BS-RoFormer SW -> Transkun 2.0); bass+drums: MuScriptor Medium; other tracks: baseline'},
              'aggregate': {r: finish(a) for r, a in agg.items()},
              'by_source': {f'{r}/{s}': finish(a) for (r, s), a in agg_src.items()},
              'missing_outputs': missing, 'muscriptor_scored_from_raw_log': raw_fallback, 'items': per_item}
    Path(dest).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    for r in ('baseline', 'best'):
        print(r, {t: (v['songs'], v['micro_f1']) for t, v in result['aggregate'][r].items()})
    print('missing:', missing)
    print('absent-category extra notes:', absent)


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2])
