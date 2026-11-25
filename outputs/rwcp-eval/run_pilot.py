"""Run only the five frozen tuning clips, serially, using local model assets."""
import argparse
from collections import defaultdict
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import pretty_midi
import psutil
import soundfile as sf

from audio_midi.backends.selected import MODEL_REVISION, WEIGHT_SHA256
from audio_midi.events import NoteEvent
from audio_midi.muscriptor_routing import parse_note_lines
from audio_midi.piano_lock import verify_assets
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes

from prepare import digest, reference_notes
from score import pool, score


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINE_HASH = '6a9c98a1fc5d98b276bdc9e2f1fed986080057dbb5ace0566aab92c681355b00'
MU_HASH = '3850cc9e5b436b17a09bd25b8f2615cb3366ab96a71e7b50f73a793a917fdf03'
ADTOF_HASH = '1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320'
FIXED_ROUTES = {
    'P1': ('piano', 'mt3-mix'), 'P2': ('piano', 'transkun-piano'),
    'P3': ('piano', 'transkun-mix'), 'P5': ('piano', 'piano-gate'),
    'B1': ('bass', 'mt3-mix'), 'B2': ('bass', 'mu-mix'),
    'B5': ('bass', 'mt3-bass'), 'B7': ('bass', 'bass-octave'),
    'D1': ('drums', 'mt3-mix'), 'D2': ('drums', 'mu-mix'),
    'D3': ('drums', 'mt3-drums'), 'D4': ('drums', 'adtof-drums'),
}
STAGE_LOCKS = [threading.Lock() for _ in range(128)]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def verify_hash(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Asset changed: {path}')


def assets(resources):
    lock_path = ROOT / 'config/piano-b.lock.json'
    lock = read_json(lock_path)
    verify_assets(resources, lock)
    verify_hash(ROOT / lock['model_assets']['sw_wrapper']['path'],
                lock['model_assets']['sw_wrapper']['sha256'])
    msst = resources / 'work/two-methods/msst'
    commit = subprocess.check_output(['git', '-C', msst, 'rev-parse', 'HEAD'], text=True).strip()
    if commit != lock['msst_commit'] or subprocess.run(['git', '-C', msst, 'diff', '--quiet', 'HEAD']).returncode:
        raise ValueError('Locked SW code mismatch')
    specialist = resources / 'work/sep-env/bin/python'
    versions = subprocess.check_output([
        specialist, '-c', 'from importlib.metadata import version;'
        'print(version("transkun"), version("adtof-pytorch"), version("torch"))',
    ], text=True).split()
    if versions[:2] != [lock['transkun_package_version'], '0.1.0']:
        raise ValueError('Locked specialist versions mismatch')
    site = resources / 'work/sep-env/lib/python3.11/site-packages'
    paths = {
        'mt3': resources / 'work/models/yourmt3.ckpt',
        'mu': Path.home() / 'Library/NeuralNote/models/muscriptor-medium-f16.gguf',
        'engine': resources / 'work/muscriptor-comparison-engine/build/bench/muscriptor_bench',
        'adtof': site / 'adtof_pytorch/data/adtof_frame_rnn_pytorch_weights.pth',
        'sw': ROOT / lock['model_assets']['sw_wrapper']['path'],
        'specialist': specialist,
    }
    for name, checksum in [('mt3', WEIGHT_SHA256), ('mu', MU_HASH),
                           ('engine', ENGINE_HASH), ('adtof', ADTOF_HASH)]:
        verify_hash(paths[name], checksum)
    versions = {
        'mt3': ['yptf_moe_nops', MODEL_REVISION, WEIGHT_SHA256,
                importlib.metadata.version('mt3-infer'), importlib.metadata.version('torch'),
                digest(ROOT / 'src/audio_midi/backends/selected.py')],
        'sw': ['BS-RoFormer SW', digest(lock_path), versions[2]],
        'transkun': ['Transkun 2.0', digest(lock_path), versions[2],
                     digest(ROOT / 'scripts/transcribe_specialist.py')],
        'mu': ['MuScriptor Medium F16', ENGINE_HASH, MU_HASH],
        'adtof': ['ADTOF Frame RNN x0.75', ADTOF_HASH, versions[1], versions[2],
                  digest(HERE / 'specialists.py')],
        'proxy': ['audio-only heuristics', digest(HERE / 'specialists.py'),
                  digest(ROOT / 'src/audio_midi/bass_evidence.py')],
        'decode': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
    }
    return paths, versions


def measure(command, log_path, timeout=1800, limit=6 * 1024**3):
    """Measure one stage and only signal its process group while its PID is reserved."""
    env = {**os.environ, 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
           'NUMBA_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'PYTHONUNBUFFERED': '1',
           'TOKENIZERS_PARALLELISM': 'false', 'AUDIO_MIDI_BATCH_SIZE': '2',
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    start = time.monotonic()
    peak = 0
    reason = None
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            while True:
                pid, status, usage = os.wait4(process.pid, os.WNOHANG)
                if pid:
                    process.returncode = os.waitstatus_to_exitcode(status)
                    unit = 1 if sys.platform == 'darwin' else 1024
                    peak = max(peak, usage.ru_maxrss * unit)
                    break
                try:
                    leader = psutil.Process(process.pid)
                    rss = 0
                    for member in [leader, *leader.children(recursive=True)]:
                        try:
                            rss += member.memory_info().rss
                        except (psutil.Error, OSError):
                            continue
                    peak = max(peak, rss)
                except (psutil.Error, OSError):
                    pass
                if peak > limit or time.monotonic() - start > timeout:
                    reason = 'RSS limit exceeded' if peak > limit else 'Stage timed out'
                    break
                time.sleep(.03)
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
    return {'elapsed_seconds': time.monotonic() - start, 'peak_memory_bytes': peak,
            'attempts': 1, 'exit_code': process.returncode, 'error': reason}


def scheduled_stage(cache, stage, input_hash, signature, outputs, command):
    """Cache only a successful invocation with hash-checked outputs."""
    version_hash = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    target = cache / f'{stage}-{input_hash}-{version_hash}'
    with STAGE_LOCKS[hash(target) % len(STAGE_LOCKS)]:
        return stage_under_lock(cache, target, stage, input_hash, signature, outputs, command)


def stage_under_lock(cache, target, stage, input_hash, signature, outputs, command):
    if target.exists():
        record = read_json(target / 'stage.json')
        if (record['identity'] == [stage, input_hash, signature]
                and all(digest(target / name) == record['outputs'][name] for name in outputs)):
            return target, record
        raise ValueError(f'Cache integrity mismatch: {target}')
    work = Path(tempfile.mkdtemp(prefix=f'{stage}-', dir=cache))
    print(f'{stage}: start', flush=True)
    details = {}
    try:
        details = measure([str(x) for x in command(work)], work / 'stage.log')
        if details['exit_code'] or details['error']:
            raise ValueError(details['error'] or f"Stage exited with {details['exit_code']}")
        record = {'identity': [stage, input_hash, signature], **details,
                  'outputs': {name: digest(work / name) for name in outputs}, 'status': 'ok'}
        write_json(work / 'stage.json', record)
        work.rename(target)
        print(f'{stage}: {details["elapsed_seconds"]:.2f}s', flush=True)
        return target, record
    except (OSError, ValueError) as error:
        record = {**details, 'status': 'failed', 'error': str(error), 'log': str(work / 'stage.log')}
        write_json(work / 'stage.json', record)
        print(f'{stage}: failed ({work / "stage.log"})', flush=True)
        return None, record


def decode(source, output, codec):
    return ['ffmpeg', '-v', 'error', '-nostdin', '-threads', '2', '-i', source,
            '-vn', '-ac', '1', '-ar', '16000', '-c:a', codec, output]


def run_clip(mix, duration, cache, paths, versions, *, needed=None):
    stages = {}

    def want(name):
        return needed is None or name in needed

    def run(name, source, version, outputs, command, extra=()):
        directory, record = scheduled_stage(cache, name, digest(source),
                                            [versions[version], *extra], outputs, command)
        stages[name] = record
        return directory

    def mt3(name, source):
        # One invocation per signal, using the same backend and cleanup as Noto.
        if not want(name):
            return None
        output = run('decode-' + name, source, 'decode', ['input.f32'],
                     lambda work: decode(source, work / 'input.f32', 'pcm_f32le')[:-1]
                     + ['-f', 'f32le', work / 'input.f32'])
        if output is None:
            return None
        raw = output / 'input.f32'
        npy = output / 'input.npy'
        if not npy.exists():
            # Identical stems can share the decoded cache in the parallel batch.
            with tempfile.NamedTemporaryFile(dir=output, suffix='.npy', delete=False) as temp:
                try:
                    np.save(temp, np.fromfile(raw, dtype='<f4'))
                    temp.flush()
                    Path(temp.name).replace(npy)
                finally:
                    Path(temp.name).unlink(missing_ok=True)
        return run(name, npy, 'mt3', ['notes.json'],
                   lambda work: [sys.executable, '-m', 'audio_midi.backends.selected',
                                 npy, paths['mt3'], work / 'notes.json', '--device', 'cpu'])

    def transkun(name, source):
        if not want(name):
            return None
        return run(name, source, 'transkun', ['notes.mid'],
                   lambda work: [paths['specialist'], ROOT / 'scripts/transcribe_specialist.py',
                                 'transkun', source, work / 'notes.mid'])

    sw = run('sw', mix, 'sw', ['stems/' + name for name in
             ('piano.wav', 'bass.wav', 'drums.wav', 'receipt.json')],
             lambda work: [paths['specialist'], paths['sw'], mix, work / 'stems', duration]) if want('sw') else None
    mixed_mt3 = mt3('mt3-mix', mix)
    mixed_transkun = transkun('transkun-mix', mix)
    pcm = run('decode-mu', mix, 'decode', ['input.wav'],
              lambda work: decode(mix, work / 'input.wav', 'pcm_f32le')) if want('mu-mix') else None
    mu = None
    if pcm:
        wav = pcm / 'input.wav'
        mu = run('mu-mix', wav, 'mu', ['stage.log'],
                 lambda work: [paths['engine'], '--transcribe', '--weights', paths['mu'],
                               '--audio', wav, '--device', 'cpu', '--threads', '2'])
    products = {'mt3-mix': mixed_mt3, 'transkun-mix': mixed_transkun, 'mu-mix': mu}
    if sw:
        stems = sw / 'stems'
        piano = stems / 'piano.wav'
        bass = stems / 'bass.wav'
        drums = stems / 'drums.wav'
        p2 = transkun('transkun-piano', piano)
        products.update({
            'transkun-piano': p2,
            'mt3-bass': mt3('mt3-bass', bass),
            'mt3-drums': mt3('mt3-drums', drums),
            'adtof-drums': run('adtof-drums', drums, 'adtof', ['notes.mid'],
                               lambda work: [paths['specialist'], HERE / 'specialists.py',
                                             'adtof', drums, paths['adtof'], work / 'notes.mid'])
            if want('adtof-drums') else None,
        })
        if mu and want('bass-octave'):
            raw = mu / 'stage.log'
            products['bass-octave'] = run(
                'bass-octave', bass, 'proxy', ['notes.json'],
                lambda work: [sys.executable, HERE / 'specialists.py', 'bass-octave',
                              bass, raw, work / 'notes.json'], (digest(raw),),
            )
        if p2 and want('piano-gate'):
            midi = p2 / 'notes.mid'
            products['piano-gate'] = run(
                'piano-gate', piano, 'proxy', ['gate.json'],
                lambda work: [sys.executable, HERE / 'specialists.py', 'piano-gate',
                              piano, midi, work / 'gate.json'], (digest(midi),),
            )
    return products, stages


def predictions(product, stage, duration):
    if stage == 'mu-mix':
        log = (product / 'stage.log').read_text()
        if not any(line.startswith('notes ') and line[6:].strip().isdigit()
                   for line in log.splitlines()):
            raise ValueError('MuScriptor completion summary is missing')
        return parse_note_lines(log)
    if stage.startswith('mt3') or stage == 'bass-octave':
        raw = [NoteEvent(**note) for note in read_json(product / 'notes.json')['notes']]
        return clean_notes(raw, duration) if stage.startswith('mt3') else raw
    notes = read_notes(product / 'notes.mid')
    return clean_notes(notes, duration) if stage.startswith('transkun') else notes


def prepare_clip(song, dataset, clips):
    source = dataset / song['audio']
    verify_hash(source, song['audio_sha256'])
    start, end = song['input_frames']
    name = f'{song["audio_sha256"]}-{start}-{end}.wav'
    mix = clips / name
    if not mix.exists():
        samples, rate = sf.read(source, start=start, stop=end, always_2d=True, dtype='int16')
        if rate != song['sample_rate'] or len(samples) != end - start:
            raise ValueError(f'Frozen source metadata changed: {song["id"]}')
        scratch = mix.with_suffix('.tmp.wav')
        sf.write(scratch, samples, rate, subtype='PCM_16')
        scratch.replace(mix)
    return mix, (end - start) / song['sample_rate']


def score_clip(song, dataset, products, duration):
    midi_path = dataset / song['midi']
    verify_hash(midi_path, song['midi_sha256'])
    reference = list(reference_notes(pretty_midi.PrettyMIDI(str(midi_path)), set(song['vocal_names'])))
    center = song['center_seconds']
    start = song['input_frames'][0] / song['sample_rate']
    gate = (read_json(products['piano-gate'] / 'gate.json')
            if products.get('piano-gate') else None)
    parsed = {}
    results = {}
    for route, (category, stage) in FIXED_ROUTES.items():
        if route == 'P5' and gate:
            stage = FIXED_ROUTES[gate['route']][1]
        if not products.get(stage):
            results[route] = {'status': 'unavailable', 'stage': stage}
            continue
        try:
            if stage not in parsed:
                parsed[stage] = predictions(products[stage], stage, duration)
        except (OSError, ValueError, KeyError) as error:
            results[route] = {'status': 'failed', 'stage': stage, 'error': str(error)}
            continue
        results[route] = {'status': 'ok', 'stage': stage,
                          'uncorrected': score(reference, parsed[stage], category, center, start, 0),
                          'corrected': score(reference, parsed[stage], category, center,
                                             start, song['offset']['seconds'])}
    return results, gate


def pilot_songs(manifest):
    songs = {song['id']: song for song in manifest['songs']}
    pilot = manifest['pilot_ids']
    if len(songs) != 72 or len(pilot) != 5 or len(set(pilot)) != 5 or any(
            song not in songs or songs[song]['split'] != 'tuning' for song in pilot):
        raise ValueError('Pilot requires exactly five distinct frozen tuning songs')
    return [songs[song] for song in pilot]


def report_summary(items):
    groups = defaultdict(list)
    for item in items:
        for route, result in item['routes'].items():
            if result['status'] == 'ok':
                groups[route].append(result)
    return {route: {'songs': len(group), **{
        variant: {metric: pool([entry[variant] for entry in group], metric)
                  for metric in ('exact', 'octave_free') if metric in group[0][variant]}
        for variant in ('uncorrected', 'corrected')
    }} for route, group in sorted(groups.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    resources, work = args.resources.resolve(), args.work.resolve()
    dataset = resources / 'work/datasets/rwc-p'
    if not work.is_relative_to(resources / 'work') or work.is_relative_to(dataset):
        raise ValueError('Work must be under the main checkout work/ and outside the dataset')
    manifest = work / 'manifest.json'
    verify_hash(manifest, args.manifest_sha256)
    selections = pilot_songs(read_json(manifest))
    for name in ('cache', 'clips'):
        (work / name).mkdir(exist_ok=True)
    with (work / '.pilot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.chdir(resources)
        os.environ['GIT_OPTIONAL_LOCKS'] = '0'
        paths, versions = assets(resources)
        result = {'manifest_sha256': args.manifest_sha256, 'machine': platform.platform(),
                  'model_versions': versions, 'items': []}
        for song in selections:
            sample_start = time.monotonic()
            load = os.getloadavg()[0]
            print(f'{song["id"]}: 1-minute load={load:.2f}', flush=True)
            mix, duration = prepare_clip(song, dataset, work / 'clips')
            products, stages = run_clip(mix, duration, work / 'cache', paths, versions)
            routes, gate = score_clip(song, dataset, products, duration)
            result['items'].append({'id': song['id'], 'input_sha256': digest(mix), 'center_seconds': song['center_seconds'],
                                    'offset': song['offset'], 'one_minute_load': load, 'p5': gate,
                                    'wall_seconds_including_cache': time.monotonic() - sample_start,
                                    'stages': stages, 'routes': routes})
            result['summary'] = report_summary(result['items'])
            write_json(work / 'pilot-results.json', result)
            print(f'{song["id"]}: completed', flush=True)
    return int(any(len([r for r in item['routes'].values() if r['status'] == 'ok']) != len(FIXED_ROUTES)
                   for item in result['items']))


if __name__ == '__main__':
    raise SystemExit(main())
