"""Replace bass and drums from MuScriptor output; never infer from references."""
from dataclasses import replace
from math import isfinite
from .events import NoteEvent, category_for

TARGETS = {'bass', 'drums'}

def parse_note_lines(text: str) -> list[NoteEvent]:
    notes = []
    for line in text.splitlines():
        if not line.startswith('NOTE,'):
            continue
        parts = line.split(',')
        if len(parts) != 6:
            raise ValueError('Malformed NOTE line')
        try:
            onset, offset = float(parts[1]), float(parts[2])
            pitch, program, drum = map(int, parts[3:])
        except ValueError as e:
            raise ValueError('Malformed NOTE values') from e
        if not isfinite(onset) or not isfinite(offset) or onset < 0 or offset <= onset or not 0 <= pitch <= 127 or not 0 <= program <= 128 or drum not in (0, 1):
            raise ValueError('Invalid NOTE values')
        category = category_for(program, bool(drum))
        if category in TARGETS:
            notes.append(NoteEvent(category, pitch, onset, offset, 80, program))
    return notes

def _source_notes_in_window(source: list[NoteEvent], duration: float) -> list[NoteEvent]:
    if not isfinite(duration) or duration <= 0:
        raise ValueError('Invalid duration')
    selected = []
    for n in source:
        if n.category not in TARGETS:
            continue
        if n.offset is None or not all(isfinite(x) for x in (n.onset, n.offset)) or n.onset < 0 or n.offset <= n.onset:
            raise ValueError('Invalid source note')
        if n.onset < duration:
            end = min(n.offset, duration)
            if end > n.onset:
                selected.append(replace(n, offset=end))
    return selected

def replace_bass_drums(baseline: list[NoteEvent], source: list[NoteEvent], duration: float) -> list[NoteEvent]:
    selected = _source_notes_in_window(source, duration)
    replaced_categories = {n.category for n in selected}
    kept = [n for n in baseline if n.category not in replaced_categories]
    return sorted(kept + selected, key=lambda n: (n.onset, n.category, n.pitch))

def replace_midi_tracks(baseline_path, source: list[NoteEvent], output_path, duration: float) -> dict[str, str]:
    """Merge predicted bass/drums into Noto MIDI and report the action per track."""
    import tempfile
    from pathlib import Path
    import mido
    from .midi import write_midi
    from .quality import read_notes
    baseline_path, output_path = Path(baseline_path), Path(output_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    original = mido.MidiFile(baseline_path)
    if original.type != 1 or original.ticks_per_beat != 480:
        raise ValueError('Unsupported baseline MIDI format')
    tempos = [m.tempo for t in original.tracks for m in t if m.type == 'set_tempo']
    if tempos != [500000]:
        raise ValueError('Baseline requires a single 120 BPM tempo')
    target_tracks = {name: [t for t in original.tracks if t.name == name] for name in TARGETS}
    if any(len(tracks) > 1 for tracks in target_tracks.values()):
        raise ValueError('Baseline allows at most one track each for bass and drums')
    other_channels = {
        msg.channel for track in original.tracks if track.name not in TARGETS
        for msg in track if hasattr(msg, 'channel')
    }
    bass_channel = None
    if target_tracks['bass']:
        bass_channels = {m.channel for m in target_tracks['bass'][0] if hasattr(m, 'channel')}
        if len(bass_channels) != 1 or 9 in bass_channels:
            raise ValueError('Invalid baseline bass channel')
        bass_channel = next(iter(bass_channels))
    target_notes = _source_notes_in_window(source, duration)
    writing_drums = any(note.category == 'drums' for note in target_notes)
    if bass_channel in other_channels or (writing_drums and 9 in other_channels):
        raise ValueError('Target channel shared with another track')

    read_notes(baseline_path)  # Preserve validation of baseline MIDI note pairs.
    replacements = {}
    if target_notes:
        target_notes.sort(key=lambda n: (n.onset, n.category, n.pitch))
        with tempfile.TemporaryDirectory(prefix='noto-midi-') as td:
            temp = Path(td) / 'replacement.mid'
            write_midi(target_notes, temp)
            generated = mido.MidiFile(temp)
        replacements = {track.name: track for track in generated.tracks if track.name in TARGETS}
    if 'bass' in replacements:
        if bass_channel is None:
            used_channels = {
                msg.channel for track in original.tracks for msg in track if hasattr(msg, 'channel')
            }
            # Prefer the full Noto mix's bass channel without changing any existing track.
            bass_channel = next((ch for ch in (3, *range(16)) if ch != 9 and ch not in used_channels), None)
            if bass_channel is None:
                raise ValueError('No free MIDI channel for added bass track')
        for msg in replacements['bass']:
            if hasattr(msg, 'channel'):
                msg.channel = bass_channel

    track_states = {}
    for target, tracks in sorted(target_tracks.items()):
        if target in replacements:
            track_states[target] = 'replaced' if tracks else 'added'
        else:
            track_states[target] = 'kept_baseline' if tracks else 'absent'
    result = mido.MidiFile(type=original.type, ticks_per_beat=original.ticks_per_beat)
    for track in original.tracks:
        replacement = replacements.pop(track.name, None)
        result.tracks.append(track.copy() if replacement is None else replacement)
    result.tracks.extend(replacements.values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('xb') as f:
        result.save(file=f)
    return track_states
