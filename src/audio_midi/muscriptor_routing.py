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

def replace_bass_drums(baseline: list[NoteEvent], source: list[NoteEvent], duration: float) -> list[NoteEvent]:
    if not isfinite(duration) or duration <= 0:
        raise ValueError('Invalid duration')
    selected=[]
    for n in source:
        if n.category not in TARGETS:
            continue
        if n.offset is None or not all(isfinite(x) for x in (n.onset,n.offset)) or n.onset < 0 or n.offset <= n.onset:
            raise ValueError('Invalid source note')
        if n.onset < duration:
            end = min(n.offset, duration)
            if end > n.onset:
                selected.append(replace(n, offset=end))
    for target in sorted(TARGETS):
        if not any(n.category == target for n in selected):
            raise ValueError(f'Missing {target} notes; refusing silent replacement')
    return sorted([n for n in baseline if n.category not in TARGETS]+selected, key=lambda n:(n.onset,n.category,n.pitch))

def replace_midi_tracks(baseline_path, source: list[NoteEvent], output_path, duration: float):
    """Keep original tracks verbatim, replace only bass/drums; fixed Noto MIDI format."""
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
    if any(len(v) != 1 for v in target_tracks.values()):
        raise ValueError('Baseline requires exactly one bass and one drums track')
    bass_channels = {m.channel for m in target_tracks['bass'][0] if hasattr(m, 'channel')}
    if len(bass_channels) != 1 or 9 in bass_channels:
        raise ValueError('Invalid baseline bass channel')
    bass_channel = next(iter(bass_channels))
    for track in original.tracks:
        if track.name not in TARGETS and any(getattr(m,'channel',None) in (bass_channel,9) for m in track):
            raise ValueError('Target channel shared with another track')
    chosen = replace_bass_drums(read_notes(baseline_path), source, duration)
    target_notes = [n for n in chosen if n.category in TARGETS]
    with tempfile.TemporaryDirectory(prefix='noto-midi-') as td:
        temp = Path(td) / 'replacement.mid'
        write_midi(target_notes, temp)
        generated = mido.MidiFile(temp)
    replacements = {t.name:t for t in generated.tracks if t.name in TARGETS}
    for msg in replacements['bass']:
        if hasattr(msg,'channel'):
            msg.channel = bass_channel
    result = mido.MidiFile(type=original.type, ticks_per_beat=original.ticks_per_beat)
    for track in original.tracks:
        result.tracks.append(replacements[track.name] if track.name in TARGETS else track.copy())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('xb') as f:
        result.save(file=f)
