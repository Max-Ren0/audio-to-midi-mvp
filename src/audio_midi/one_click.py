"""Compose the fixed local transcription routes from audio alone."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from threading import Event, Thread, current_thread, main_thread
import time

import mido
import psutil

from .audio import decode_mp3
from .beat_align import BeatEstimate, QUANTIZE, TempoMap, write_aligned_midi
from .piano_lock import digest
from .pipeline import publish
from .worker import process_tree_rss


ROOT = Path(__file__).resolve().parents[2]
MVP_TRACKS = ('piano', 'bass', 'drums')
STAGE_NAMES = ('baseline', 'piano_b', 'muscriptor')
YOURMT3_WEIGHTS = 'work/models/yourmt3.ckpt'
MUSCRIPTOR_ENGINE = 'work/muscriptor-comparison-engine/build/bench/muscriptor_bench'
MUSCRIPTOR_WEIGHTS = 'Library/NeuralNote/models/muscriptor-medium-f16.gguf'


def _read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _save_receipt(path, receipt):
    # Write the checkpoint beside the destination so readers see a complete JSON
    # file, even if the process is interrupted while writing the next update.
    with tempfile.TemporaryDirectory(prefix='.checkpoint-', dir=path.parent) as scratch:
        staged = Path(scratch) / path.name
        _write_json(staged, receipt)
        staged.replace(path)


def _git_output(*args):
    return subprocess.check_output(
        ['git', '-C', str(ROOT), *args], text=True, stderr=subprocess.PIPE,
    ).strip()


def _missing_assets(resources, weights):
    lock = _read_json(ROOT / 'config/piano-b.lock.json')
    piano_assets = [
        (resources if asset['path'].startswith('work/') else ROOT) / asset['path']
        for asset in lock['model_assets'].values()
    ]
    specialist = resources / 'work/sep-env/bin/python'
    engine = resources / MUSCRIPTOR_ENGINE
    msst = resources / 'work/two-methods/msst'
    required = [
        resources / YOURMT3_WEIGHTS, resources / 'work/models/GeneralUser-GS.sf2',
        msst / 'models/bs_roformer/__init__.py', msst / 'utils/model_utils.py',
        ROOT / 'scripts/transcribe_specialist.py', specialist, engine, weights, *piano_assets,
    ]
    if not (msst / '.git').is_file():
        required.append(msst / '.git/HEAD')
    missing = [str(path) for path in required if not path.is_file()]
    for executable in (specialist, engine):
        if executable.is_file() and not os.access(executable, os.X_OK):
            missing.append(f'{executable}（不可执行）')
    return missing


def _run(args, stage_dir, threads, *, isolated=False):
    log = stage_dir / 'command.log'
    env = {
        **os.environ,
        'PYTHONPATH': str(ROOT / 'src'),
        'PYTHONDONTWRITEBYTECODE': '1',
        'GIT_OPTIONAL_LOCKS': '0',
        'OMP_NUM_THREADS': str(threads),
        'OPENBLAS_NUM_THREADS': str(threads),
        'MKL_NUM_THREADS': str(threads),
        'VECLIB_MAXIMUM_THREADS': str(threads),
        'TMPDIR': str(stage_dir),
    }
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(
            [sys.executable, *map(str, args)], cwd=stage_dir, env=env,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=isolated,
        )
    if result.returncode:
        contents = log.read_text(encoding='utf-8', errors='replace').strip()
        lines = contents.splitlines()
        try:
            detail = json.loads(contents)['error']
        except (ValueError, KeyError, TypeError):
            detail = lines[-1] if lines else '没有诊断输出'
        raise RuntimeError(f'退出码 {result.returncode}：{detail}（详见 {log}）')


def _note_count(track):
    return sum(msg.type == 'note_on' and msg.velocity > 0 for msg in track)


def _prepare_baseline(source, target, duration):
    midi = mido.MidiFile(source)
    midi.tracks[:] = [track for track in midi.tracks if track.name != 'vocal']
    if not any(_note_count(track) for track in midi.tracks):
        raise ValueError('基线没有有效器乐音符')
    # The baseline ends at the last note. MuScriptor requires the full input
    # timeline, including any trailing silence.
    conductor = midi.tracks[0]
    last_tick = sum(msg.time for msg in conductor if msg.type != 'end_of_track')
    end_tick = round(mido.second2tick(duration, midi.ticks_per_beat, 500000))
    conductor[:] = [msg for msg in conductor if msg.type != 'end_of_track']
    conductor.append(mido.MetaMessage('end_of_track', time=max(0, end_tick - last_tick)))
    midi.save(target)
    return any(track.name == 'piano' and _note_count(track) for track in midi.tracks)


def _link_readonly(source, destination):
    destination.symlink_to(source, target_is_directory=source.is_dir())


def _piano_workspace(stage_dir, resources):
    # The existing script resolves its own checkout root and writes work/piano-b
    # there. Give it a private checkout layout inside this stage.
    scripts = stage_dir / 'scripts'
    scripts.mkdir()
    entry = scripts / 'run_piano_b.py'
    shutil.copyfile(ROOT / 'scripts' / entry.name, entry)
    _link_readonly(ROOT / 'scripts/transcribe_specialist.py', scripts / 'transcribe_specialist.py')
    for relative in ('config', 'outputs', 'work/models', 'work/two-methods', 'work/sep-env'):
        destination = stage_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        origin = resources if relative.startswith('work/') else ROOT
        _link_readonly(origin / relative, destination)
    return entry


def _replace_piano(source, specialist, target):
    original = mido.MidiFile(source)
    piano = mido.MidiFile(specialist)
    if piano.type != original.type or piano.ticks_per_beat != original.ticks_per_beat:
        raise ValueError('钢琴 B 与基线 MIDI 的格式不一致')
    tracks = [track for track in piano.tracks if track.name == 'piano' and _note_count(track)]
    if len(tracks) != 1:
        raise ValueError('钢琴 B 未生成唯一的有效钢琴轨')
    index = next(i for i, track in enumerate(original.tracks) if track.name == 'piano')
    channel = next(msg.channel for msg in original.tracks[index] if msg.type == 'program_change')
    for msg in tracks[0]:
        if hasattr(msg, 'channel'):
            msg.channel = channel
    original.tracks[index] = tracks[0]
    original.save(target)


def _summarize_tracks(path, piano_replaced, target_states):
    tracks = []
    for track in mido.MidiFile(path).tracks:
        count = _note_count(track)
        if not count:
            continue
        channels = {msg.channel for msg in track if msg.type == 'note_on' and msg.velocity > 0}
        if len(channels) != 1:
            raise ValueError(f'轨道 {track.name} 使用多个 MIDI 通道')
        source = 'baseline'
        if track.name == 'piano' and piano_replaced:
            source = 'piano_b'
        elif target_states.get(track.name) in ('replaced', 'added'):
            source = 'muscriptor'
        tracks.append({
            'instrument': track.name, 'channel': next(iter(channels)) + 1,
            'note_count': count, 'source': source,
        })
    if not tracks:
        raise ValueError('最终 MIDI 没有有效音符')
    return tracks


def _outputs(stage_dir, output_dir):
    if not stage_dir.is_dir():
        return []
    return sorted(
        path.relative_to(output_dir).as_posix()
        for path in stage_dir.rglob('*') if not path.is_symlink() and path.is_file()
    )


def _timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


@contextmanager
def _defer_parallel_signals():
    """Keep parent signals from interrupting the executor's worker joins."""
    interruptions = []
    previous_handlers = {}

    def remember(signum, _frame):
        if not interruptions:
            interruptions.append(signal.Signals(signum).name)

    try:
        if current_thread() is main_thread():
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, remember)
        yield interruptions
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _stage(name, directory, output_dir, action=None, *, reason=None):
    stage = {
        'name': name, 'status': 'skipped', 'seconds': 0, 'outputs': [],
        'started_at': None, 'finished_at': None,
    }
    if action is None:
        stage['reason'] = reason
        return stage, None
    stage['started_at'] = _timestamp()
    start = time.monotonic()
    result = None
    try:
        if directory is not None:
            directory.mkdir(parents=True)
        result = action()
        stage['status'] = 'ok'
    except (Exception, KeyboardInterrupt) as error:
        stage.update(status='failed', error=str(error) or type(error).__name__)
    stage['finished_at'] = _timestamp()
    stage['seconds'] = round(time.monotonic() - start, 3)
    if directory is not None:
        stage['outputs'] = _outputs(directory, output_dir)
    return stage, result


def run_noto(input_path, output_dir, resources, threads=2, device='cpu', *, command=None,
             parallel=False, piano_threads=2, muscriptor_threads=2,
             beat_align=False, quantize=None):
    input_path = Path(input_path).absolute()
    output_dir = Path(output_dir).absolute()
    resources = Path(os.path.abspath(resources))
    if input_path.suffix.lower() != '.mp3' or not input_path.is_file():
        print('仅支持存在的本地 MP3 文件', file=sys.stderr)
        return 2
    if threads != 2 or device != 'cpu':
        print('固定路线仅支持 CPU 和 2 个计算线程', file=sys.stderr)
        return 2
    if piano_threads not in (1, 2) or muscriptor_threads not in (1, 2):
        print('钢琴 B 和 MuScriptor 各支持 1 或 2 个计算线程', file=sys.stderr)
        return 2
    if quantize is not None and quantize not in QUANTIZE:
        print('量化网格须为 1/4、1/8 或 1/16', file=sys.stderr)
        return 2
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(f'无法创建新输出目录，未覆盖既有内容：{error}', file=sys.stderr)
        return 2

    start = time.monotonic()
    stages_dir = output_dir / 'stages'
    receipt_path = output_dir / 'receipt.json'
    receipt = {
        'status': 'running', 'input_filename': input_path.name, 'input_sha256': None,
        'duration_seconds': None, 'git_commit': None, 'git_dirty': None,
        'parallel_used': False,
        'command': command if command is not None else [
            sys.executable, str(ROOT / 'scripts/run_noto.py'), str(input_path),
            '--output-dir', str(output_dir), '--resources', str(resources),
            '--threads', str(threads), '--device', device,
            '--parallel' if parallel else '--no-parallel',
            '--piano-threads', str(piano_threads), '--muscriptor-threads', str(muscriptor_threads),
            '--beat-align' if beat_align else '--no-beat-align',
            *(['--quantize', quantize] if quantize else []),
        ],
        'parameters': {
            'input': str(input_path), 'output_dir': str(output_dir),
            'resources': str(resources), 'threads': threads, 'device': device,
            'parallel': parallel, 'piano_threads': piano_threads,
            'muscriptor_threads': muscriptor_threads,
            'beat_align': beat_align, 'quantize': quantize,
        },
        'stages': [], 'tracks': [],
        'beat_alignment': None,
        'muscriptor': None, 'model_hashes': {}, 'mvp_tracks': list(MVP_TRACKS),
        'research_tracks': [], 'research_tracks_note': '不计入 MVP 验收',
    }
    models = receipt['model_hashes']
    baseline_dir = stages_dir / 'baseline'
    piano_dir = stages_dir / 'piano_b'
    muscriptor_dir = stages_dir / 'muscriptor'
    routed = baseline_dir / 'routed.mid'
    delivery = muscriptor_dir / 'delivery'
    final = delivery / 'Noto-MuScriptor贝斯鼓.mid'
    target = output_dir / 'noto.mid'
    weights = Path.home() / MUSCRIPTOR_WEIGHTS
    audio = None
    peak_memory_bytes = 0
    stop_sampling = Event()
    process = psutil.Process()

    def sample_memory():
        nonlocal peak_memory_bytes
        while True:
            peak_memory_bytes = max(peak_memory_bytes, process_tree_rss(process))
            if stop_sampling.wait(0.1):
                break

    sampler = Thread(target=sample_memory, daemon=True)

    def update_totals():
        receipt['total_seconds'] = round(time.monotonic() - start, 3)
        receipt['peak_memory_bytes'] = peak_memory_bytes

    def checkpoint():
        update_totals()
        _save_receipt(receipt_path, receipt)

    def finish_failure(code):
        receipt['status'] = 'failed'
        receipt.pop('output_sha256', None)
        try:
            checkpoint()
        except (OSError, KeyboardInterrupt) as error:
            print(f'无法更新运行回执：{error or type(error).__name__}', file=sys.stderr)
        failure = next(stage for stage in receipt['stages'] if stage['status'] == 'failed')
        print(f'{failure["name"]} 失败：{failure["error"]}', file=sys.stderr)
        return code

    def baseline():
        nonlocal audio
        decoded = decode_mp3(input_path)
        if beat_align:
            audio = decoded
        receipt['duration_seconds'] = decoded.duration_seconds
        if decoded.duration_seconds > 180:
            raise ValueError('实际解码长度超过 180 秒；已拒绝，不自动截断')
        output = baseline_dir / 'result.mid'
        _run([
            '-m', 'audio_midi.cli', 'transcribe', input_path, '--output', output,
            '--checkpoint', resources / YOURMT3_WEIGHTS, '--device', device,
        ], baseline_dir, threads)
        report = _read_json(output.with_suffix('.report.json'))
        if report['input_sha256'] != receipt['input_sha256']:
            raise ValueError('基线回执的音频 SHA256 不一致')
        models['baseline'] = {'yourmt3_weights_sha256': report['model']['weight_sha256']}
        return _prepare_baseline(output, routed, decoded.duration_seconds)

    def piano_b():
        entry = _piano_workspace(piano_dir, resources)
        piano_output = piano_dir / 'delivery'
        _run([entry, input_path, '--output-dir', piano_output, '--threads', piano_threads],
             piano_dir, piano_threads, isolated=receipt['parallel_used'])
        report = _read_json(piano_output / '运行报告.json')
        if report['input_sha256'] != receipt['input_sha256']:
            raise ValueError('钢琴 B 回执的音频 SHA256 不一致')
        models['piano_b'] = {
            name: asset['sha256'] for name, asset in report['lock']['model_assets'].items()
        }
        models['piano_b']['lock_sha256'] = report['lock_sha256']
        models['piano_b']['soundfont_sha256'] = report['soundfont_sha256']
        _replace_piano(routed, piano_output / '钢琴-B.mid', piano_dir / 'routed.mid')

    def muscriptor(source):
        _run([
            ROOT / 'scripts/run_muscriptor_bass_drums.py', '--audio', input_path,
            '--baseline', source, '--baseline-audio-sha256', receipt['input_sha256'],
            '--engine', resources / MUSCRIPTOR_ENGINE, '--weights', weights,
            '--output-dir', delivery, '--threads', muscriptor_threads,
        ], muscriptor_dir, muscriptor_threads, isolated=receipt['parallel_used'])
        report = _read_json(delivery / '运行报告.json')
        receipt['muscriptor'] = {key: report[key] for key in ('tracks', 'track_note_counts')}
        models['muscriptor'] = {key: report[key] for key in ('engine_sha256', 'weights_sha256')}
        return report

    def summarize(path, piano_present, report):
        receipt['tracks'] = _summarize_tracks(path, piano_present, report['tracks'])
        receipt['research_tracks'] = [
            track['instrument'] for track in receipt['tracks'] if track['instrument'] not in MVP_TRACKS
        ]

    def record(stage):
        receipt['stages'].append(stage)
        if stage['status'] == 'failed':
            receipt.setdefault('failed_stage', stage['name'])
        checkpoint()

    sampler.start()
    phase = 'preflight'
    phase_started_at = _timestamp()
    try:
        # Capture the starting tree before creating any files inside the output directory.
        receipt['git_commit'] = _git_output('rev-parse', 'HEAD')
        receipt['git_dirty'] = bool(_git_output('status', '--porcelain'))
        checkpoint()
        receipt['input_sha256'] = digest(input_path)
        missing = _missing_assets(resources, weights)
        if missing:
            receipt['failed_stage'] = phase
            receipt['stages'].append({
                'name': phase, 'status': 'failed', 'seconds': round(time.monotonic() - start, 3),
                'started_at': phase_started_at, 'finished_at': _timestamp(),
                'error': '缺少或无法使用资源：' + '、'.join(missing), 'outputs': [],
            })
            return finish_failure(2)
        phase = 'receipt'
        checkpoint()

        base_stage, piano_present = _stage('baseline', baseline_dir, output_dir, baseline)
        record(base_stage)
        if parallel and piano_present:
            receipt['parallel_used'] = True
            checkpoint()
            phase = 'parallel'
            phase_started_at = _timestamp()
            # The route subprocesses run in separate sessions, so terminal
            # signals are handled here while their normal cleanup runs.
            with _defer_parallel_signals() as interruptions:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    piano_job = executor.submit(_stage, 'piano_b', piano_dir, output_dir, piano_b)
                    muscriptor_job = executor.submit(
                        _stage, 'muscriptor', muscriptor_dir, output_dir, lambda: muscriptor(routed),
                    )
                piano_stage, _ = piano_job.result()
                muscriptor_stage, report = muscriptor_job.result()
                record(piano_stage)
                record(muscriptor_stage)
            if interruptions:
                receipt['interrupted_by'] = interruptions[0]
                raise RuntimeError(f'收到 {interruptions[0]}，两路已结束')
        else:
            reason = ('前一阶段失败' if 'failed_stage' in receipt else '基线没有识别到钢琴轨')
            piano_stage, _ = _stage(
                'piano_b', piano_dir, output_dir, piano_b if piano_present else None, reason=reason,
            )
            record(piano_stage)

            def serial_muscriptor():
                report = muscriptor(piano_dir / 'routed.mid' if piano_present else routed)
                summarize(final, piano_present, report)

            muscriptor_stage, _ = _stage(
                'muscriptor', muscriptor_dir, output_dir,
                serial_muscriptor if 'failed_stage' not in receipt else None, reason='前一阶段失败',
            )
            record(muscriptor_stage)
        if 'failed_stage' in receipt:
            return finish_failure(1)

        if receipt['parallel_used']:
            def merge():
                merged = stages_dir / 'merge' / 'noto.mid'
                _replace_piano(final, piano_dir / 'routed.mid', merged)
                summarize(merged, piano_present, report)
                return merged

            merge_stage, final = _stage('merge', stages_dir / 'merge', output_dir, merge)
            record(merge_stage)
            if 'failed_stage' in receipt:
                return finish_failure(1)

        if beat_align or quantize:
            alignment_dir = stages_dir / 'beat_align'

            def align():
                if beat_align:
                    estimate, tempo_map = TempoMap.from_audio(audio.samples, audio.sample_rate)
                else:
                    estimate = BeatEstimate()
                    tempo_map = TempoMap(estimate)
                output = final
                moved = 0
                if estimate.beats or quantize:
                    output = alignment_dir / 'noto.mid'
                    moved = write_aligned_midi(final, output, tempo_map, quantize)
                receipt['beat_alignment'] = tempo_map.receipt(estimate, beat_align, quantize, moved)
                return output

            alignment_stage, final = _stage('beat_align', alignment_dir, output_dir, align)
            record(alignment_stage)
            if 'failed_stage' in receipt:
                return finish_failure(1)
        else:
            estimate = BeatEstimate()
            receipt['beat_alignment'] = TempoMap(estimate).receipt(estimate, False, None)

        phase = 'publish'
        phase_started_at = _timestamp()
        receipt['status'] = 'ok'
        receipt['output_sha256'] = digest(final)
        # The directory belongs to this run. Replace its progress receipt and
        # publish an independent MIDI copy in one rollback-capable operation.
        if os.path.lexists(target):
            raise FileExistsError(f'已有同名输出，未覆盖：{target}')
        with tempfile.TemporaryDirectory(prefix='.publish-', dir=output_dir) as scratch:
            staged_receipt = Path(scratch) / receipt_path.name
            staged_midi = Path(scratch) / target.name
            shutil.copyfile(final, staged_midi)
            update_totals()
            _write_json(staged_receipt, receipt)
            publish([(staged_midi, target), (staged_receipt, receipt_path)], overwrite=True)
    except (Exception, KeyboardInterrupt) as error:
        receipt.setdefault('failed_stage', phase)
        receipt['stages'].append({
            'name': phase, 'status': 'failed', 'seconds': 0,
            'started_at': phase_started_at, 'finished_at': _timestamp(),
            'error': str(error) or type(error).__name__, 'outputs': [],
        })
        return finish_failure(1)
    finally:
        stop_sampling.set()
        sampler.join()

    print(f'已生成 {target}')
    return 0
