import hashlib,json
from pathlib import Path
import pytest


def cache(tmp_path):
    root=tmp_path/'stems';root.mkdir()
    piano=root/'piano.wav';piano.write_bytes(b'piano')
    sha=hashlib.sha256(piano.read_bytes()).hexdigest()
    upstream={'input_sha256':'decoded','amp':False,'cpu_threads':2,'weight_sha256':'weight','config_sha256':'config','code_commit':'commit','files':{'Piano':{'sha256':sha}}}
    (root/'receipt.json').write_text(json.dumps(upstream))
    receipt={'input_sha256':'input','stem_sha256':{'piano':sha},'configuration':{'original_input_sha256':'input','source_wav_sha256':'decoded','upstream_receipt_sha256':hashlib.sha256((root/'receipt.json').read_bytes()).hexdigest()}}
    (root/'separation-receipt.json').write_text(json.dumps(receipt))
    lock={'cpu_threads':2,'amp':False,'msst_commit':'commit','model_assets':{'sw_weights':{'sha256':'weight'},'sw_config':{'sha256':'config'}}}
    return root,lock


def test_accepts_exact_sw_cache(tmp_path):
    from audio_midi.piano_lock import verify_piano_cache
    root,lock=cache(tmp_path)
    assert verify_piano_cache(root,'input',lock)==root/'piano.wav'


@pytest.mark.parametrize('change',['input','weights','piano','receipt_binding'])
def test_rejects_wrong_source_or_tampered_cache(tmp_path,change):
    from audio_midi.piano_lock import verify_piano_cache
    root,lock=cache(tmp_path)
    if change=='weights':lock['model_assets']['sw_weights']['sha256']='demucs'
    elif change=='piano':(root/'piano.wav').write_bytes(b'altered')
    elif change=='receipt_binding':(root/'receipt.json').write_text('{}')
    with pytest.raises(ValueError):verify_piano_cache(root,'other' if change=='input' else 'input',lock)


def test_assets_fail_closed_without_fallback(tmp_path):
    from audio_midi.piano_lock import verify_assets
    p=tmp_path/'weights';p.write_bytes(b'wrong')
    lock={'model_assets':{'transkun_weights':{'path':'weights','sha256':'expected'}}}
    with pytest.raises(ValueError,match='transkun_weights'):verify_assets(tmp_path,lock)


@pytest.mark.parametrize('change',['original_input','decoded_input','amp','cpu_threads'])
def test_rejects_internally_inconsistent_receipt_chain(tmp_path,change):
    from audio_midi.piano_lock import verify_piano_cache
    root,lock=cache(tmp_path)
    upstream=json.loads((root/'receipt.json').read_text())
    receipt=json.loads((root/'separation-receipt.json').read_text())
    if change=='original_input':receipt['configuration']['original_input_sha256']='other'
    elif change=='decoded_input':upstream['input_sha256']='other'
    elif change=='amp':upstream['amp']=True
    else:upstream['cpu_threads']=8
    (root/'receipt.json').write_text(json.dumps(upstream))
    receipt['configuration']['upstream_receipt_sha256']=hashlib.sha256((root/'receipt.json').read_bytes()).hexdigest()
    (root/'separation-receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError):verify_piano_cache(root,'input',lock)
