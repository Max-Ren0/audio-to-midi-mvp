"""Compose the fixed local transcription routes from audio alone."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import mido

from .audio import decode_mp3
from .piano_lock import digest
from .pipeline import publish


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


def _run(args, stage_dir, threads):
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
            stdout=stream, stderr=subprocess.STDOUT,
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


def run_noto(input_path, output_dir, resources, threads=2, device='cpu', *, command=None):
    input_path = Path(input_path).absolute()
    output_dir = Path(output_dir).absolute()
    resources = Path(os.path.abspath(resources))
    if input_path.suffix.lower() != '.mp3' or not input_path.is_file():
        print('仅支持存在的本地 MP3 文件', file=sys.stderr)
        return 2
    if threads != 2 or device != 'cpu':
        print('固定路线仅支持 CPU 和 2 个计算线程', file=sys.stderr)
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
        'command': command if command is not None else [
            sys.executable, str(ROOT / 'scripts/run_noto.py'), str(input_path),
            '--output-dir', str(output_dir), '--resources', str(resources),
            '--threads', str(threads), '--device', device,
        ],
        'parameters': {
            'input': str(input_path), 'output_dir': str(output_dir),
            'resources': str(resources), 'threads': threads, 'device': device,
        },
        'stages': [], 'tracks': [],
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

    def checkpoint():
        receipt['total_seconds'] = round(time.monotonic() - start, 3)
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
        audio = decode_mp3(input_path)
        receipt['duration_seconds'] = audio.duration_seconds
        if audio.duration_seconds > 180:
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
        return _prepare_baseline(output, routed, audio.duration_seconds)

    def piano_b():
        entry = _piano_workspace(piano_dir, resources)
        piano_output = piano_dir / 'delivery'
        _run([entry, input_path, '--output-dir', piano_output], piano_dir, threads)
        report = _read_json(piano_output / '运行报告.json')
        if report['input_sha256'] != receipt['input_sha256']:
            raise ValueError('钢琴 B 回执的音频 SHA256 不一致')
        models['piano_b'] = {
            name: asset['sha256'] for name, asset in report['lock']['model_assets'].items()
        }
        models['piano_b']['lock_sha256'] = report['lock_sha256']
        models['piano_b']['soundfont_sha256'] = report['soundfont_sha256']
        _replace_piano(routed, piano_output / '钢琴-B.mid', piano_dir / 'routed.mid')

    def muscriptor(piano_present):
        source = piano_dir / 'routed.mid' if piano_present else routed
        _run([
            ROOT / 'scripts/run_muscriptor_bass_drums.py', '--audio', input_path,
            '--baseline', source, '--baseline-audio-sha256', receipt['input_sha256'],
            '--engine', resources / MUSCRIPTOR_ENGINE, '--weights', weights,
            '--output-dir', delivery,
        ], muscriptor_dir, threads)
        report = _read_json(delivery / '运行报告.json')
        receipt['muscriptor'] = {key: report[key] for key in ('tracks', 'track_note_counts')}
        models['muscriptor'] = {key: report[key] for key in ('engine_sha256', 'weights_sha256')}
        receipt['tracks'] = _summarize_tracks(final, piano_present, report['tracks'])
        receipt['research_tracks'] = [
            track['instrument'] for track in receipt['tracks'] if track['instrument'] not in MVP_TRACKS
        ]

    phase = 'preflight'
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
                'error': '缺少或无法使用资源：' + '、'.join(missing), 'outputs': [],
            })
            return finish_failure(2)
        phase = 'receipt'
        checkpoint()

        piano_present = False
        failed = False
        for name, directory in zip(STAGE_NAMES, (baseline_dir, piano_dir, muscriptor_dir)):
            stage = {'name': name, 'status': 'skipped', 'seconds': 0, 'outputs': []}
            receipt['stages'].append(stage)
            stage_start = time.monotonic()
            try:
                if failed:
                    stage['reason'] = '前一阶段失败'
                elif name == 'piano_b' and not piano_present:
                    stage['reason'] = '基线没有识别到钢琴轨'
                else:
                    directory.mkdir(parents=True)
                    if name == 'baseline':
                        piano_present = baseline()
                    elif name == 'piano_b':
                        piano_b()
                    else:
                        muscriptor(piano_present)
                    stage['status'] = 'ok'
            except (Exception, KeyboardInterrupt) as error:
                stage.update(status='failed', error=str(error) or type(error).__name__)
                receipt['failed_stage'] = name
                failed = True
            stage['seconds'] = round(time.monotonic() - stage_start, 3)
            stage['outputs'] = _outputs(directory, output_dir)
            checkpoint()
        if failed:
            return finish_failure(1)

        phase = 'publish'
        receipt['status'] = 'ok'
        receipt['output_sha256'] = digest(final)
        receipt['total_seconds'] = round(time.monotonic() - start, 3)
        # The directory belongs to this run. Replace its progress receipt and
        # publish an independent MIDI copy in one rollback-capable operation.
        if os.path.lexists(target):
            raise FileExistsError(f'已有同名输出，未覆盖：{target}')
        with tempfile.TemporaryDirectory(prefix='.publish-', dir=output_dir) as scratch:
            staged_receipt = Path(scratch) / receipt_path.name
            staged_midi = Path(scratch) / target.name
            _write_json(staged_receipt, receipt)
            shutil.copyfile(final, staged_midi)
            publish([(staged_midi, target), (staged_receipt, receipt_path)], overwrite=True)
    except (Exception, KeyboardInterrupt) as error:
        receipt.setdefault('failed_stage', phase)
        receipt['stages'].append({
            'name': phase, 'status': 'failed', 'seconds': 0,
            'error': str(error) or type(error).__name__, 'outputs': [],
        })
        return finish_failure(1)

    print(f'已生成 {target}')
    return 0
