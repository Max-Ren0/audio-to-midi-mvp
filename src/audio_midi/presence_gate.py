"""Suppress whole instrument tracks using features from the published route."""
from collections import defaultdict
from math import isfinite

import mido


TRACKS = ('piano', 'bass', 'drums')
# Selected on the 15 frozen tuning clips. Equality retains the track.
RULES = {
    'piano': {'notes_per_minute': 150},
    'bass': {'notes_per_minute': 80},
    'drums': {'notes_per_minute': 100},
}


def track_features(midi, duration):
    if not isfinite(duration) or duration <= 0:
        raise ValueError('存在判断需要有效的音频长度')
    pitches = defaultdict(list)
    for track in midi.tracks:
        if track.name in TRACKS:
            pitches[track.name].extend(
                msg.note for msg in track if msg.type == 'note_on' and msg.velocity > 0
            )
    return {
        name: {
            'note_count': len(pitches[name]),
            'notes_per_minute': 60 * len(pitches[name]) / duration,
            'distinct_pitches': len(set(pitches[name])),
        }
        for name in TRACKS
    }


def removes_track(features, thresholds):
    return (bool(features['note_count']) and bool(thresholds)
            and all(features[key] < limit for key, limit in thresholds.items()))


def gate_midi(source, target, duration, rules=None):
    """Return the selected MIDI path and receipt data; preserve kept tracks verbatim."""
    if rules is None:
        rules = RULES
    midi = mido.MidiFile(source)
    features = track_features(midi, duration)
    decisions = {}
    for name, values in features.items():
        thresholds = rules[name]
        removed = removes_track(values, thresholds)
        decisions[name] = {
            'features': values, 'thresholds': dict(thresholds), 'suppressed': removed,
            'predicted_present': bool(values['note_count']) and not removed,
            'reason': ('判定为不存在，未输出' if removed else
                       '模型未输出音符' if not values['note_count'] else '判定为存在，保留'),
        }
    if not any(decision['suppressed'] for decision in decisions.values()):
        return source, decisions
    midi.tracks[:] = [track for track in midi.tracks
                      if not decisions.get(track.name, {}).get('suppressed', False)]
    midi.save(target)
    return target, decisions
