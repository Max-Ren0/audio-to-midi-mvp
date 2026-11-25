import json
import runpy
import signal
import sys
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import mido
import pytest

from audio_midi import one_click
from audio_midi.events import NoteEvent
from audio_midi.midi import write_midi
from audio_midi.muscriptor_routing import replace_midi_tracks
from audio_midi.worker import WorkerResult


def note(instrument, pitch):
    return NoteEvent(instrument, pitch, 0.25, 1.0)


def pitches(track):
    return [msg.note for msg in track if msg.type == 'note_on' and msg.velocity]


@pytest.fixture
def job(tmp_path, monkeypatch):
    audio = tmp_path / 'input.mp3'
    audio.write_bytes(b'fake audio')
    output = tmp_path / 'result'
    resources = tmp_path / 'assets'
    home = tmp_path / 'home'
    monkeypatch.setattr(Path, 'home', lambda: home)
    for asset in (
        resources / 'work/models/yourmt3.ckpt',
        resources / 'work/models/BS-Rofo-SW-Fixed.ckpt',
        resources / 'work/models/GeneralUser-GS.sf2',
        resources / 'work/two-methods/BS-Rofo-SW-Fixed.yaml',
        resources / 'work/two-methods/msst/.git/HEAD',
        resources / 'work/two-methods/msst/models/bs_roformer/__init__.py',
        resources / 'work/two-methods/msst/utils/model_utils.py',
        resources / 'work/sep-env/bin/python',
        resources / 'work/sep-env/lib/python3.11/site-packages/transkun/pretrained/2.0.pt',
        resources / 'work/sep-env/lib/python3.11/site-packages/transkun/pretrained/2.0.conf',
        resources / 'work/muscriptor-comparison-engine/build/bench/muscriptor_bench',
        home / 'Library/NeuralNote/models/muscriptor-medium-f16.gguf',
    ):
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.touch(mode=0o700)
    options = SimpleNamespace(
        audio=audio, output=output, resources=resources, calls=[], fail=None, duration=3.0,
        interrupt=None, checkpoints=[], barrier=None, finished=[], threads={}, run_subprocess=one_click._run,
        baseline=[
            note('piano', 60), note('acoustic_guitar', 63), note('electric_guitar', 64),
            note('bass', 36), note('drums', 38), note('strings', 68), note('vocal', 69),
        ],
        muscriptor=[note('bass', 40), note('drums', 41)],
    )
    original_digest = one_click.digest(audio)
    monkeypatch.setattr(one_click, 'decode_mp3', lambda _: SimpleNamespace(
        duration_seconds=options.duration, samples=[.1], sample_rate=16000,
    ))

    def read_arg(args, name):
        return Path(args[args.index(name) + 1])

    def fake_run(args, stage, threads, *, isolated=False):
        options.calls.append(stage.name)
        receipt_path = output / 'receipt.json'
        options.checkpoints.append(json.loads(receipt_path.read_text()) if receipt_path.exists() else None)
        if stage.name == options.interrupt:
            raise KeyboardInterrupt
        options.threads[stage.name] = threads
        if stage.name != 'baseline':
            assert int(args[args.index('--threads') + 1]) == threads
            if options.barrier is not None:
                options.barrier.wait(timeout=5)
        (stage / 'command.log').write_text('test subprocess')
        if stage.name == options.fail:
            raise RuntimeError(f'{stage.name} model failed')
        if stage.name == 'baseline':
            assert args[:3] == ['-m', 'audio_midi.cli', 'transcribe']
            assert args[3] == audio
            assert read_arg(args, '--checkpoint') == resources / 'work/models/yourmt3.ckpt'
            result = read_arg(args, '--output')
            write_midi(options.baseline, result)
            one_click._write_json(result.with_suffix('.report.json'), {
                'input_sha256': original_digest, 'model': {'weight_sha256': 'yourmt3'},
            })
        elif stage.name == 'piano_b':
            assert args[1] == audio
            assert (stage / 'work/models').readlink() == resources / 'work/models'
            result = read_arg(args, '--output-dir')
            result.mkdir()
            write_midi([note('piano', 71)], result / '钢琴-B.mid')
            one_click._write_json(result / '运行报告.json', {
                'input_sha256': original_digest, 'lock_sha256': 'lock',
                'lock': {'model_assets': {'sw_weights': {'sha256': 'sw'}}},
                'soundfont_sha256': 'soundfont',
            })
        else:
            assert read_arg(args, '--audio') == audio
            assert read_arg(args, '--engine') == (
                resources / 'work/muscriptor-comparison-engine/build/bench/muscriptor_bench'
            )
            assert args[args.index('--baseline-audio-sha256') + 1] == original_digest
            result = read_arg(args, '--output-dir')
            result.mkdir()
            baseline = read_arg(args, '--baseline')
            assert mido.MidiFile(baseline).length == pytest.approx(options.duration)
            final = result / 'Noto-MuScriptor贝斯鼓.mid'
            states = replace_midi_tracks(baseline, options.muscriptor, final, options.duration)
            counts = dict.fromkeys(states, 0)
            for track in mido.MidiFile(final).tracks:
                if track.name in counts:
                    counts[track.name] = len(pitches(track))
            one_click._write_json(result / '运行报告.json', {
                'tracks': states, 'track_note_counts': counts,
                'engine_sha256': 'engine', 'weights_sha256': 'gguf',
            })
        options.finished.append(stage.name)

    monkeypatch.setattr(one_click, '_run', fake_run)
    options.run = lambda: one_click.run_noto(audio, output, resources)
    options.receipt = lambda: json.loads((output / 'receipt.json').read_text())
    return options


def test_success_preserves_baseline_tracks_and_reports_provenance(job):
    assert job.run() == 0
    receipt = job.receipt()
    assert receipt['status'] == 'ok'
    assert receipt['input_filename'] == 'input.mp3'
    assert receipt['input_sha256'] == one_click.digest(job.audio)
    assert receipt['duration_seconds'] == 3.0
    assert len(receipt['git_commit']) == 40
    assert receipt['total_seconds'] >= 0
    assert receipt['peak_memory_bytes'] > 0
    assert not receipt['parallel_used']
    assert receipt['beat_alignment']['method'] == 'fixed'
    assert job.threads == dict.fromkeys(one_click.STAGE_NAMES, 2)
    assert receipt['model_hashes'] == {
        'baseline': {'yourmt3_weights_sha256': 'yourmt3'},
        'piano_b': {'sw_weights': 'sw', 'lock_sha256': 'lock', 'soundfont_sha256': 'soundfont'},
        'muscriptor': {'engine_sha256': 'engine', 'weights_sha256': 'gguf'},
    }
    assert receipt['mvp_tracks'] == ['piano', 'bass', 'drums']
    assert receipt['research_tracks'] == ['acoustic_guitar', 'electric_guitar', 'strings']
    assert receipt['research_tracks_note'] == '不计入 MVP 验收'
    assert receipt['muscriptor'] == {
        'tracks': {'bass': 'replaced', 'drums': 'replaced'},
        'track_note_counts': {'bass': 1, 'drums': 1},
    }
    assert job.calls == ['baseline', 'piano_b', 'muscriptor']
    for stage in receipt['stages']:
        assert stage['status'] == 'ok'
        assert stage['seconds'] >= 0
        assert stage['started_at'] <= stage['finished_at']
        assert f"stages/{stage['name']}/command.log" in stage['outputs']
        assert all((job.output / item).is_file() for item in stage['outputs'])
    path = job.output / 'noto.mid'
    assert not path.samefile(job.output / 'stages/muscriptor/delivery/Noto-MuScriptor贝斯鼓.mid')
    assert receipt['output_sha256'] == one_click.digest(path)
    final = {track.name: track for track in mido.MidiFile(path).tracks}
    baseline = {
        track.name: track
        for track in mido.MidiFile(job.output / 'stages/baseline/result.mid').tracks
    }
    assert 'vocal' not in final
    for name in receipt['research_tracks']:
        assert final[name] == baseline[name]
    assert [pitches(final[name]) for name in ('piano', 'bass', 'drums')] == [[71], [40], [41]]
    assert receipt['tracks'] == [
        {'instrument': 'piano', 'channel': 1, 'note_count': 1, 'source': 'piano_b'},
        {'instrument': 'acoustic_guitar', 'channel': 2, 'note_count': 1, 'source': 'baseline'},
        {'instrument': 'electric_guitar', 'channel': 3, 'note_count': 1, 'source': 'baseline'},
        {'instrument': 'bass', 'channel': 4, 'note_count': 1, 'source': 'muscriptor'},
        {'instrument': 'drums', 'channel': 10, 'note_count': 1, 'source': 'muscriptor'},
        {'instrument': 'strings', 'channel': 5, 'note_count': 1, 'source': 'baseline'},
    ]


@pytest.mark.parametrize('parallel', [False, True])
def test_skips_piano_when_baseline_has_none(job, parallel):
    job.baseline = [event for event in job.baseline if event.category != 'piano']
    assert one_click.run_noto(job.audio, job.output, job.resources, parallel=parallel) == 0
    assert job.calls == ['baseline', 'muscriptor']
    assert job.receipt()['parameters']['parallel'] is parallel
    assert not job.receipt()['parallel_used']
    stage = job.receipt()['stages'][1]
    assert stage['status'] == 'skipped'
    assert stage['started_at'] is stage['finished_at'] is None
    assert '基线没有识别到钢琴轨' in stage['reason']
    assert 'piano' not in {track['instrument'] for track in job.receipt()['tracks']}


def test_muscriptor_missing_tracks_and_sources(job):
    job.baseline = [event for event in job.baseline if event.category != 'drums']
    job.muscriptor = []
    assert job.run() == 0
    receipt = job.receipt()
    assert receipt['muscriptor'] == {
        'tracks': {'bass': 'kept_baseline', 'drums': 'absent'},
        'track_note_counts': {'bass': 1, 'drums': 0},
    }
    sources = {track['instrument']: track['source'] for track in receipt['tracks']}
    assert sources['bass'] == 'baseline'
    assert 'drums' not in sources


def test_muscriptor_adds_missing_baseline_track(job):
    job.baseline = [event for event in job.baseline if event.category != 'bass']
    assert job.run() == 0
    receipt = job.receipt()
    assert receipt['muscriptor']['tracks']['bass'] == 'added'
    bass = next(track for track in receipt['tracks'] if track['instrument'] == 'bass')
    assert bass['source'] == 'muscriptor'


@pytest.mark.parametrize('missing_baseline', [None, 'bass', 'drums'])
def test_parallel_routes_overlap_and_match_serial_midi(job, missing_baseline):
    job.baseline = [event for event in job.baseline if event.category != missing_baseline]
    assert one_click.run_noto(
        job.audio, job.output, job.resources, piano_threads=1, muscriptor_threads=1,
    ) == 0
    serial = job.receipt()
    parallel_dir = job.output.with_name('parallel')
    job.barrier = Barrier(2)
    job.calls.clear()
    assert one_click.run_noto(
        job.audio, parallel_dir, job.resources, parallel=True, piano_threads=1, muscriptor_threads=1,
    ) == 0

    receipt = one_click._read_json(parallel_dir / 'receipt.json')
    assert receipt['parameters']['parallel'] and receipt['parallel_used']
    assert receipt['peak_memory_bytes'] > 0
    assert job.calls[0] == 'baseline'
    assert job.threads == {'baseline': 2, 'piano_b': 1, 'muscriptor': 1}
    baseline, piano, muscriptor, merge = receipt['stages']
    assert baseline['finished_at'] <= min(piano['started_at'], muscriptor['started_at'])
    assert max(piano['started_at'], muscriptor['started_at']) < min(piano['finished_at'], muscriptor['finished_at'])
    assert max(piano['finished_at'], muscriptor['finished_at']) <= merge['started_at']
    assert receipt['tracks'] == serial['tracks']
    assert receipt['muscriptor'] == serial['muscriptor']
    assert receipt['output_sha256'] == serial['output_sha256']
    assert mido.MidiFile(parallel_dir / 'noto.mid').tracks == mido.MidiFile(job.output / 'noto.mid').tracks


def test_piano_b_reports_effective_threads_without_changing_lock(tmp_path, monkeypatch):
    main = runpy.run_path(str(one_click.ROOT / 'scripts/run_piano_b.py'))['main']
    script = main.__globals__
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(script, '__file__', str(tmp_path / 'scripts/run_piano_b.py'))
    lock_file = tmp_path / 'config/piano-b.lock.json'
    lock_file.parent.mkdir()
    lock = one_click._read_json(one_click.ROOT / 'config/piano-b.lock.json')
    one_click._write_json(lock_file, lock)
    audio = tmp_path / 'input.mp3'
    audio.touch()
    stems = tmp_path / 'stems'
    stems.mkdir()
    piano = stems / 'piano.wav'
    piano.touch()
    (stems / 'separation-receipt.json').touch()
    soundfont = tmp_path / 'work/models/GeneralUser-GS.sf2'
    soundfont.parent.mkdir(parents=True)
    soundfont.touch()
    output = tmp_path / 'delivery'
    monkeypatch.setattr(sys, 'argv', [
        'run_piano_b.py', str(audio), '--output-dir', str(output), '--stems', str(stems), '--threads', '1',
    ])
    monkeypatch.setitem(sys.modules, 'soundfile', SimpleNamespace(
        info=lambda _: SimpleNamespace(samplerate=44100, channels=2, duration=3.0),
    ))
    monkeypatch.setitem(script, 'verify_assets', lambda *_: None)
    monkeypatch.setitem(script, 'decode_mp3', lambda *_: SimpleNamespace(duration_seconds=3.0))
    monkeypatch.setitem(script, 'render_midi', lambda *_: {})
    monkeypatch.setitem(script, 'subprocess', SimpleNamespace(
        check_output=lambda args, **_: lock['msst_commit'] if args[0] == 'git' else lock['transkun_package_version'],
        run=lambda *_, **__: SimpleNamespace(returncode=0),
    ))

    def verify_cache(path, input_hash, effective_lock):
        assert path == stems and effective_lock['cpu_threads'] == 1
        return piano

    def transcribe(command, *_, threads):
        assert command[-2:] == ['--threads', '1'] and threads == 1
        write_midi([note('piano', 71)], Path(command[-3]))
        return WorkerResult(0, 1, 0.0)

    monkeypatch.setitem(script, 'verify_piano_cache', verify_cache)
    monkeypatch.setitem(script, 'run_command', transcribe)
    main()
    report = one_click._read_json(output / '运行报告.json')
    assert report['cpu_threads'] == 1
    assert report['lock'] == lock
    assert report['lock_sha256'] == one_click.digest(lock_file)


@pytest.mark.parametrize('failure, peer', [('piano_b', 'muscriptor'), ('muscriptor', 'piano_b')])
def test_parallel_failure_waits_for_peer_and_does_not_publish(job, failure, peer):
    job.barrier = Barrier(2)
    job.fail = failure
    assert one_click.run_noto(job.audio, job.output, job.resources, parallel=True) == 1
    receipt = job.receipt()
    assert receipt['status'] == 'failed'
    assert receipt['failed_stage'] == failure
    assert peer in job.finished
    assert {stage['name']: stage['status'] for stage in receipt['stages']} == {
        'baseline': 'ok', failure: 'failed', peer: 'ok',
    }
    assert not (job.output / 'noto.mid').exists()


@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM])
def test_parent_signal_waits_for_parallel_routes(job, monkeypatch, signum):
    run_model = one_click._run
    save_receipt = one_click._save_receipt
    failed_snapshots = []
    child = '''
import os, sys, time
from pathlib import Path
own, peer = map(Path, sys.argv[1:3])
own.touch()
deadline = time.monotonic() + 5
while not peer.exists():
    if time.monotonic() > deadline:
        raise TimeoutError("peer subprocess did not start")
    time.sleep(0.01)
if own.name == 'piano_b':
    os.kill(os.getppid(), int(sys.argv[3]))
else:
    time.sleep(0.2)
'''

    def interrupt(*_):
        raise KeyboardInterrupt

    def run(args, stage, threads, *, isolated=False):
        if stage.name != 'baseline':
            assert isolated
            peer = 'muscriptor' if stage.name == 'piano_b' else 'piano_b'
            job.run_subprocess(
                ['-c', child, job.audio.parent / stage.name, job.audio.parent / peer, signum.value],
                stage, threads, isolated=isolated,
            )
        run_model(args, stage, threads)

    def save(path, receipt):
        if receipt['status'] == 'failed':
            failed_snapshots.append(set(job.finished))
        save_receipt(path, receipt)

    monkeypatch.setattr(one_click, '_run', run)
    monkeypatch.setattr(one_click, '_save_receipt', save)
    previous = signal.signal(signum, interrupt)
    try:
        assert one_click.run_noto(job.audio, job.output, job.resources, parallel=True) == 1
        assert signal.getsignal(signum) is interrupt
    finally:
        signal.signal(signum, previous)

    receipt = job.receipt()
    assert failed_snapshots == [{'baseline', 'piano_b', 'muscriptor'}]
    assert receipt['failed_stage'] == 'parallel'
    assert receipt['interrupted_by'] == signum.name
    assert [stage['status'] for stage in receipt['stages']] == ['ok', 'ok', 'ok', 'failed']
    assert not (job.output / 'noto.mid').exists()


@pytest.mark.parametrize('failed_stage', ['baseline', 'merge', 'both_routes'])
def test_parallel_boundary_failures(job, monkeypatch, failed_stage):
    if failed_stage == 'baseline':
        job.fail = 'baseline'
        expected = 'baseline'
    elif failed_stage == 'merge':
        replace_piano = one_click._replace_piano

        def fail_merge(source, specialist, target):
            if target.parent.name == 'merge':
                raise ValueError('merge failed')
            replace_piano(source, specialist, target)

        monkeypatch.setattr(one_click, '_replace_piano', fail_merge)
        expected = 'merge'
    else:
        run_model = one_click._run

        def fail_routes(args, stage, threads, **kwargs):
            if stage.name != 'baseline':
                raise RuntimeError(f'{stage.name} failed')
            run_model(args, stage, threads)

        monkeypatch.setattr(one_click, '_run', fail_routes)
        expected = 'piano_b'

    assert one_click.run_noto(job.audio, job.output, job.resources, parallel=True) == 1
    receipt = job.receipt()
    assert receipt['failed_stage'] == expected
    assert {stage['name'] for stage in receipt['stages'] if stage['status'] == 'failed'} == (
        {'piano_b', 'muscriptor'} if failed_stage == 'both_routes' else {expected}
    )
    assert receipt['parallel_used'] is (failed_stage != 'baseline')
    assert not (job.output / 'noto.mid').exists()


@pytest.mark.parametrize('stage', ['baseline', 'piano_b', 'muscriptor'])
def test_stage_failure_leaves_receipt_without_final_midi(job, stage, capsys):
    job.fail = stage
    assert job.run() == 1
    receipt = job.receipt()
    assert receipt['status'] == 'failed'
    assert receipt['failed_stage'] == stage
    index = one_click.STAGE_NAMES.index(stage)
    assert receipt['stages'][index]['status'] == 'failed'
    assert receipt['stages'][index]['error'] == f'{stage} model failed'
    assert all(item['status'] == 'skipped' for item in receipt['stages'][index + 1:])
    assert not (job.output / 'noto.mid').exists()
    assert 'Traceback' not in capsys.readouterr().err


def test_existing_output_is_preserved(job):
    job.output.mkdir()
    sentinel = job.output / 'original'
    sentinel.write_text('preserve')
    assert job.run() == 2
    assert list(job.output.iterdir()) == [sentinel]
    assert sentinel.read_text() == 'preserve'
    assert job.calls == []


def test_duration_over_180_rejected_before_inference(job):
    job.duration = 180.0000625
    assert job.run() == 1
    receipt = job.receipt()
    assert receipt['status'] == 'failed'
    assert receipt['failed_stage'] == 'baseline'
    assert '超过 180 秒' in receipt['stages'][0]['error']
    assert job.calls == []
    assert not (job.output / 'noto.mid').exists()


@pytest.mark.parametrize('porcelain, dirty', [('', False), ('?? scripts/run_noto.py\n', True)])
def test_records_git_tree_status(job, monkeypatch, porcelain, dirty):
    check_output = one_click.subprocess.check_output

    def git_output(args, **kwargs):
        if args[3:] == ['status', '--porcelain']:
            return porcelain
        return check_output(args, **kwargs)

    monkeypatch.setattr(one_click.subprocess, 'check_output', git_output)
    assert job.run() == 0
    assert job.receipt()['git_dirty'] is dirty
    assert len(job.receipt()['git_commit']) == 40


@pytest.mark.parametrize('relative', [
    'work/models/yourmt3.ckpt',
    'work/sep-env/bin/python',
    'work/sep-env/lib/python3.11/site-packages/transkun/pretrained/2.0.pt',
    'work/two-methods/msst/.git/HEAD',
    'work/muscriptor-comparison-engine/build/bench/muscriptor_bench',
    'Library/NeuralNote/models/muscriptor-medium-f16.gguf',
])
def test_missing_resources_stop_before_models(job, monkeypatch, relative, capsys):
    root = job.resources if relative.startswith('work/') else Path.home()
    missing = root / relative
    is_file = Path.is_file
    monkeypatch.setattr(Path, 'is_file', lambda path: path != missing and is_file(path))

    assert job.run() == 2
    receipt = job.receipt()
    assert receipt['status'] == 'failed'
    assert receipt['failed_stage'] == 'preflight'
    assert str(missing) in receipt['stages'][0]['error']
    assert str(missing) in capsys.readouterr().err
    assert job.calls == []
    assert not (job.output / 'noto.mid').exists()


def test_checkpoints_show_completed_stages_during_model_run(job):
    assert job.run() == 0
    for count, snapshot in enumerate(job.checkpoints):
        assert snapshot['status'] == 'running'
        assert [stage['status'] for stage in snapshot['stages']] == ['ok'] * count


def test_model_interrupt_leaves_partial_receipt(job, capsys):
    job.interrupt = 'piano_b'
    assert job.run() == 1
    receipt = job.receipt()
    assert receipt['status'] == 'failed'
    assert receipt['failed_stage'] == 'piano_b'
    assert [stage['status'] for stage in receipt['stages']] == ['ok', 'failed', 'skipped']
    assert 'KeyboardInterrupt' in receipt['stages'][1]['error']
    assert not (job.output / 'noto.mid').exists()
    assert 'Traceback' not in capsys.readouterr().err


def test_final_failure_receipt_interrupt_keeps_last_checkpoint(job, monkeypatch, capsys):
    job.fail = 'muscriptor'
    write_json = one_click._write_json

    def interrupt_final_write(path, data):
        if data.get('status') == 'failed' and data.get('failed_stage') == 'muscriptor':
            path.write_text('{')
            raise KeyboardInterrupt
        write_json(path, data)

    monkeypatch.setattr(one_click, '_write_json', interrupt_final_write)
    assert job.run() == 1
    receipt = job.receipt()
    assert receipt['status'] == 'running'
    assert [stage['status'] for stage in receipt['stages'][:2]] == ['ok', 'ok']
    assert not (job.output / 'noto.mid').exists()
    assert 'Traceback' not in capsys.readouterr().err


def test_success_receipt_interrupt_does_not_publish_midi(job, monkeypatch, capsys):
    write_json = one_click._write_json

    def interrupt_publish(path, data):
        if data.get('status') == 'ok':
            raise KeyboardInterrupt
        write_json(path, data)

    monkeypatch.setattr(one_click, '_write_json', interrupt_publish)
    assert job.run() == 1
    receipt = job.receipt()
    assert receipt['status'] == 'failed'
    assert receipt['failed_stage'] == 'publish'
    assert all(stage['status'] == 'ok' for stage in receipt['stages'][:3])
    assert 'KeyboardInterrupt' in receipt['stages'][-1]['error']
    assert not (job.output / 'noto.mid').exists()
    assert 'Traceback' not in capsys.readouterr().err


@pytest.mark.parametrize('parallel_flag,beat_flag', [
    ('--parallel', '--beat-align'), ('--no-parallel', '--no-beat-align'),
])
def test_cli_records_invocation_and_resolved_parameters(job, monkeypatch, parallel_flag, beat_flag):
    entry = one_click.ROOT / 'scripts/run_noto.py'
    monkeypatch.chdir(job.audio.parent)
    monkeypatch.setenv('NOTO_TEST_SECRET', 'secret-env-value')
    args = [
        'input.mp3', '--threads', '2', '--resources', 'assets', '--output-dir', 'result',
        parallel_flag, '--piano-threads', '1', '--muscriptor-threads', '2', beat_flag,
    ]
    monkeypatch.setattr(one_click, 'detect_beats', lambda *_: one_click.BeatEstimate(
        fallback_reason='insufficient_beats',
    ))
    monkeypatch.setattr(sys, 'argv', [str(entry), *args])
    main = runpy.run_path(str(entry))['main']
    assert main() == 0
    receipt = job.receipt()
    assert receipt['command'] == [sys.executable, str(entry), *args]
    assert receipt['parameters'] == {
        'input': str(job.audio), 'output_dir': str(job.output),
        'resources': str(job.resources), 'threads': 2, 'device': 'cpu',
        'parallel': parallel_flag == '--parallel', 'piano_threads': 1, 'muscriptor_threads': 2,
        'beat_align': beat_flag == '--beat-align', 'quantize': None,
    }
    assert receipt['beat_alignment']['fallback'] is (beat_flag == '--beat-align')
    assert receipt['beat_alignment']['time_signature'] == '4/4'
    assert 'secret-env-value' not in json.dumps(receipt)


@pytest.mark.parametrize('parallel', [False, True])
def test_beat_alignment_retimes_final_mix_without_quantizing(job, monkeypatch, parallel):
    from audio_midi.quality import read_notes

    assert job.run() == 0
    events = read_notes(job.output / 'noto.mid')
    aligned = job.output.with_name('aligned')

    def fake_detect(samples, rate):
        assert samples == [.1] and rate == 16000
        return one_click.BeatEstimate((.27, .71, 1.23, 1.68, 2.17, 2.61), .99, 3, 2, .9, False)

    monkeypatch.setattr(one_click, 'detect_beats', fake_detect)
    assert one_click.run_noto(job.audio, aligned, job.resources,
                              parallel=parallel, beat_align=True) == 0
    output = aligned / 'noto.mid'
    actual = read_notes(output)
    assert len(actual) == len(events) == 6
    for before, after in zip(events, actual):
        assert (after.category, after.pitch, after.velocity, after.program) == (
            before.category, before.pitch, before.velocity, before.program,
        )
        assert (after.onset, after.offset) == pytest.approx((before.onset, before.offset), abs=25e-6)
    receipt = one_click._read_json(aligned / 'receipt.json')
    assert receipt['tracks'] == job.receipt()['tracks']
    assert receipt['beat_alignment']['time_signature'] == '3/4'
    assert receipt['beat_alignment']['tempo_changes'] > 1
    assert not receipt['beat_alignment']['quantized']
    assert receipt['output_sha256'] == one_click.digest(output)


def test_beat_fallback_keeps_original_bytes_and_explicit_quantization_changes_onsets(job, monkeypatch):
    assert job.run() == 0
    original = job.output / 'noto.mid'
    fallback = job.output.with_name('fallback')
    monkeypatch.setattr(one_click, 'detect_beats', lambda *_: one_click.BeatEstimate(
        fallback_reason='insufficient_beats',
    ))
    assert one_click.run_noto(job.audio, fallback, job.resources, beat_align=True) == 0
    assert (fallback / original.name).read_bytes() == original.read_bytes()
    report = one_click._read_json(fallback / 'receipt.json')['beat_alignment']
    assert report['fallback'] and report['fallback_reason'] == 'insufficient_beats'

    quantized = job.output.with_name('quantized')
    assert one_click.run_noto(job.audio, quantized, job.resources, quantize='1/4') == 0
    report = one_click._read_json(quantized / 'receipt.json')['beat_alignment']
    assert report['quantize_grid'] == '1/4'
    assert report['quantized'] and report['quantized_onsets'] == 6
    from audio_midi.quality import read_notes
    assert [(note.onset, note.offset) for note in read_notes(quantized / original.name)] == [(0.5, 1.)] * 6


def test_documentation_matches_one_click_entry():
    readme = (one_click.ROOT / 'README.md').read_text()
    guide = (one_click.ROOT / 'outputs/muscriptor-route/使用说明.md').read_text()
    assert '统一的一键流程、模型商用许可还没完成' not in readme
    assert '一键三轨入口已提供' in readme
    assert '../../scripts/run_noto.py' in guide
