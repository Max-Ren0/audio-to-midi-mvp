"""Fail-closed provenance checks for the single approved piano-B route."""
from pathlib import Path
import hashlib,json


def digest(path: Path) -> str:
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_assets(root: Path, lock: dict) -> None:
    for name,entry in lock['model_assets'].items():
        path=root/entry['path']
        if not path.is_file() or digest(path)!=entry['sha256']:
            raise ValueError(f'Locked piano asset mismatch: {name}; no automatic fallback')


def verify_piano_cache(root: Path, input_sha256: str, lock: dict) -> Path:
    receipt=json.loads((root/'separation-receipt.json').read_text())
    if receipt['input_sha256']!=input_sha256:raise ValueError('Piano cache input mismatch')
    upstream_path=root/'receipt.json'
    if receipt.get('configuration',{}).get('upstream_receipt_sha256')!=digest(upstream_path):
        raise ValueError('Piano cache upstream receipt mismatch')
    upstream=json.loads(upstream_path.read_text())
    configuration=receipt['configuration']
    decoded_sha=configuration.get('source_wav_sha256')
    if not isinstance(decoded_sha,str) or not decoded_sha or configuration.get('original_input_sha256')!=input_sha256 or decoded_sha!=upstream.get('input_sha256'):
        raise ValueError('Piano cache decoded/original input chain mismatch')
    if upstream.get('amp') is not lock['amp'] or upstream.get('cpu_threads')!=lock['cpu_threads']:
        raise ValueError('Piano cache execution settings mismatch')
    expected=(lock['model_assets']['sw_weights']['sha256'],lock['model_assets']['sw_config']['sha256'],lock['msst_commit'])
    actual=(upstream.get('weight_sha256'),upstream.get('config_sha256'),upstream.get('code_commit'))
    if actual!=expected:raise ValueError('Piano cache is not the locked SW model')
    piano=root/'piano.wav';sha=digest(piano)
    if sha!=receipt['stem_sha256']['piano'] or sha!=upstream['files']['Piano']['sha256']:
        raise ValueError('Piano stem hash mismatch')
    return piano
