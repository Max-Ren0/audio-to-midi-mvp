import pytest
from audio_midi.events import NoteEvent
from audio_midi.muscriptor_routing import parse_note_lines, replace_bass_drums

def note(category,pitch,onset,offset,program=None):
    return NoteEvent(category,pitch,onset,offset,80,program)

def test_replace_only_requested_tracks_and_limit_window():
    old=[note('piano',60,.2,.5,0),note('bass',40,.5,.8,33),note('drums',36,1,1.1,0),note('strings',70,1.5,2,48)]
    src=[note('bass',43,.3,.8,33),note('drums',42,1,1.1,0),note('bass',45,9.9,10.5,33),note('bass',46,10.1,10.2,33),note('piano',61,.2,.4,0)]
    out=replace_bass_drums(old,src,10)
    assert [(n.category,n.pitch,n.onset,n.offset) for n in out]==[('piano',60,.2,.5),('bass',43,.3,.8),('drums',42,1,1.1),('strings',70,1.5,2),('bass',45,9.9,10)]

def test_note_replacement_keeps_target_with_no_source_notes_in_window():
    old = [note('bass', 40, 0, 1, 33), note('drums', 36, 1, 1.1, 0)]
    source = [note('bass', 43, 0, 1, 33), note('drums', 42, 2, 2.1, 0)]
    assert replace_bass_drums(old, source, 2) == [source[0], old[1]]

def test_raw_parse_ignores_other_instruments_and_rejects_malformed():
    result=parse_note_lines('NOTE,0.100000,0.300000,40,33,0\nNOTE,0.200000,0.210000,42,128,1\nNOTE,0.300000,0.400000,65,0,0\n')
    assert [(x.category,x.pitch) for x in result]==[('bass',40),('drums',42)]
    with pytest.raises(ValueError):parse_note_lines('NOTE,0.1,nan,40,33,0\n')

def test_replacement_preserves_non_target_midi_tracks(tmp_path):
    import mido
    from audio_midi.midi import write_midi
    from audio_midi.muscriptor_routing import replace_midi_tracks
    baseline=tmp_path/'baseline.mid';output=tmp_path/'output.mid'
    write_midi([note('piano',60,.2,.5,0),note('bass',40,.5,.8,33),note('drums',36,1,1.1,0),note('strings',70,1.5,2,48)],baseline)
    original=mido.MidiFile(baseline)
    tracks = replace_midi_tracks(baseline,[note('bass',43,.3,.8,33),note('drums',42,1,1.1,0)],output,2)
    assert tracks == {'bass': 'replaced', 'drums': 'replaced'}
    result=mido.MidiFile(output)
    bass = next(t for t in result.tracks if t.name == 'bass')
    assert {m.channel for m in bass if m.type == 'program_change'} == {1}
    for name in ('Conductor','piano','strings'):
        assert list(next(t for t in original.tracks if t.name==name))==list(next(t for t in result.tracks if t.name==name))
    with pytest.raises(FileExistsError):replace_midi_tracks(baseline,[note('bass',43,.3,.8,33),note('drums',42,1,1.1,0)],output,2)


@pytest.mark.parametrize(
    'baseline_targets, source_targets, expected_states, expected_notes',
    [
        (('drums',), ('bass', 'drums'), ('added', 'replaced'), {'bass': (43, 3), 'drums': (42, 9)}),
        (('bass',), ('bass', 'drums'), ('replaced', 'added'), {'bass': (43, 1), 'drums': (42, 9)}),
        ((), ('bass', 'drums'), ('added', 'added'), {'bass': (43, 3), 'drums': (42, 9)}),
        (('bass', 'drums'), ('bass',), ('replaced', 'kept_baseline'), {'bass': (43, 1), 'drums': (36, 9)}),
        (('bass', 'drums'), ('drums',), ('kept_baseline', 'replaced'), {'bass': (40, 1), 'drums': (42, 9)}),
        (('bass',), ('bass',), ('replaced', 'absent'), {'bass': (43, 1)}),
        (('bass', 'drums'), (), ('kept_baseline', 'kept_baseline'), {'bass': (40, 1), 'drums': (36, 9)}),
        ((), (), ('absent', 'absent'), {}),
    ],
    ids=['add-bass', 'add-drums', 'add-both', 'keep-drums', 'keep-bass', 'absent-drums', 'keep-both', 'absent-both'],
)
def test_route_missing_midi_tracks(tmp_path, baseline_targets, source_targets, expected_states, expected_notes):
    import mido
    from audio_midi.midi import write_midi
    from audio_midi.muscriptor_routing import replace_midi_tracks

    baseline = tmp_path / 'baseline.mid'
    output = tmp_path / 'output.mid'
    baseline_notes = {'bass': note('bass', 40, .5, .8, 33), 'drums': note('drums', 36, 1, 1.1, 0)}
    predictions = {'bass': note('bass', 43, .3, .8, 35), 'drums': note('drums', 42, 1, 1.1, 0)}
    write_midi([note('piano', 60, .2, .5, 0), *(baseline_notes[name] for name in baseline_targets)], baseline)
    original = {track.name: list(track) for track in mido.MidiFile(baseline).tracks}

    states = replace_midi_tracks(baseline, [predictions[name] for name in source_targets], output, 2)

    assert states == dict(zip(('bass', 'drums'), expected_states))
    result = {track.name: list(track) for track in mido.MidiFile(output).tracks}
    assert set(result) == {'Conductor', 'piano', *expected_notes}
    assert result['Conductor'] == original['Conductor']
    assert result['piano'] == original['piano']
    for name, (pitch, channel) in expected_notes.items():
        assert [(m.note, m.channel) for m in result[name] if m.type == 'note_on'] == [(pitch, channel)]
        if name == 'bass':
            assert [m.program for m in result[name] if m.type == 'program_change'] == [33]
        if states[name] == 'kept_baseline':
            assert result[name] == original[name]


def test_added_bass_uses_free_channel_when_baseline_uses_channel_three(tmp_path):
    import mido
    from audio_midi.midi import write_midi
    from audio_midi.muscriptor_routing import replace_midi_tracks

    baseline = tmp_path / 'baseline.mid'
    output = tmp_path / 'output.mid'
    write_midi([
        note('piano', 60, 0, 1, 0),
        note('acoustic_guitar', 61, 0, 1, 25),
        note('electric_guitar', 62, 0, 1, 27),
        note('strings', 63, 0, 1, 48),
    ], baseline)
    original = list(mido.MidiFile(baseline).tracks)

    states = replace_midi_tracks(baseline, [note('bass', 40, 0, 1, 33)], output, 2)

    result = mido.MidiFile(output)
    assert states == {'bass': 'added', 'drums': 'absent'}
    assert result.tracks[:-1] == original
    assert {m.channel for m in result.tracks[-1] if hasattr(m, 'channel')} == {4}


@pytest.mark.parametrize(
    'channel, baseline_target, source_target, conflict',
    [
        (9, 'drums', 'drums', True),
        (9, None, 'drums', True),
        (1, 'bass', 'bass', True),
        (9, None, None, False),
        (9, 'drums', None, False),
    ],
    ids=['replace-drums', 'add-drums', 'shared-bass', 'absent-drums', 'keep-drums'],
)
def test_target_channel_conflicts(tmp_path, channel, baseline_target, source_target, conflict):
    import mido
    from audio_midi.midi import write_midi
    from audio_midi.muscriptor_routing import replace_midi_tracks

    baseline = tmp_path / 'baseline.mid'
    output = tmp_path / 'output.mid'
    targets = {'bass': note('bass', 40, 0, 1, 33), 'drums': note('drums', 36, 0, 1, 0)}
    notes = [note('piano', 60, 0, 1, 0)]
    if baseline_target:
        notes.append(targets[baseline_target])
    write_midi(notes, baseline)
    original = mido.MidiFile(baseline)
    for msg in original.tracks[1]:
        if hasattr(msg, 'channel'):
            msg.channel = channel
    original.save(baseline)
    predictions = [targets[source_target]] if source_target else []

    if conflict:
        with pytest.raises(ValueError, match='Target channel shared with another track'):
            replace_midi_tracks(baseline, predictions, output, 1)
        assert not output.exists()
    else:
        states = replace_midi_tracks(baseline, predictions, output, 1)
        assert states['drums'] == ('kept_baseline' if baseline_target else 'absent')
        assert mido.MidiFile(output).tracks == mido.MidiFile(baseline).tracks


@pytest.mark.parametrize(
    'engine_log, expected_tracks, expected_counts',
    [
        ('notes 0\n', None, None),
        (
            'NOTE,0.0,0.4,60,0,0\nnotes 1\n',
            {'bass': 'kept_baseline', 'drums': 'absent'},
            {'bass': 2, 'drums': 0},
        ),
        (
            'NOTE,0.1,0.2,43,33,0\nNOTE,0.1,0.2,42,128,1\nNOTE,1.0,1.2,44,33,0\nnotes 3\n',
            {'bass': 'replaced', 'drums': 'added'},
            {'bass': 1, 'drums': 1},
        ),
    ],
    ids=['no-notes', 'non-target-only', 'count-merged-output'],
)
def test_cli_engine_log_and_receipt(tmp_path, monkeypatch, capsys, engine_log, expected_tracks, expected_counts):
    import importlib.util
    import json
    from pathlib import Path
    import subprocess
    import sys
    import wave
    from audio_midi.midi import write_midi

    script = Path(__file__).resolve().parents[1] / 'scripts' / 'run_muscriptor_bass_drums.py'
    spec = importlib.util.spec_from_file_location('muscriptor_cli_under_test', script)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    audio = tmp_path / 'audio.mp3'
    engine = tmp_path / 'engine'
    weights = tmp_path / 'weights'
    for fixture_file in (audio, engine, weights):
        fixture_file.write_text(fixture_file.name)
    monkeypatch.setattr(cli, 'ENGINE_SHA', cli.sha(engine))
    monkeypatch.setattr(cli, 'MODEL_SHA', cli.sha(weights))
    baseline = tmp_path / 'baseline.mid'
    write_midi([note('bass', 40, 0, .4, 33), note('bass', 41, .5, 1, 33)], baseline)
    output = tmp_path / 'output'
    monkeypatch.setattr(sys, 'argv', [
        str(script), '--audio', str(audio), '--baseline', str(baseline),
        '--baseline-audio-sha256', cli.sha(audio), '--engine', str(engine),
        '--weights', str(weights), '--output-dir', str(output),
    ])

    def run_process(args, **kwargs):
        if args[0] == 'ffmpeg':
            with wave.open(args[-1], 'wb') as wav:
                wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                wav.writeframes(bytes(32000))
        else:
            assert args[0] == str(engine.resolve())
            kwargs['stdout'].write(engine_log)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(cli.subprocess, 'run', run_process)
    receipt = output / '运行报告.json'
    midi = output / 'Noto-MuScriptor贝斯鼓.mid'
    if expected_tracks is None:
        with pytest.raises(ValueError, match='MuScriptor log contains no NOTE records'):
            cli.main()
        assert not midi.exists()
        assert not receipt.exists()
        assert capsys.readouterr().out == ''
    else:
        cli.main()
        assert midi.exists()
        saved = json.loads(receipt.read_text())
        assert saved['tracks'] == expected_tracks
        assert saved['track_note_counts'] == expected_counts
        assert json.loads(capsys.readouterr().out) == saved
    assert (output / 'muscriptor.log').read_text() == engine_log
