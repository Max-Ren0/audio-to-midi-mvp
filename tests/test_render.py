from pathlib import Path
import pytest
import mido


def test_render_uses_soundfont_and_preserves_timing(tmp_path):
    pytest.importorskip('tinysoundfont')
    sf=Path('work/models/GeneralUser-GS.sf2')
    if not sf.exists():pytest.skip('local soundfont required')
    from audio_midi.render import render_midi
    from audio_midi.events import NoteEvent
    from audio_midi.midi import write_midi
    import soundfile as soundfile
    import numpy as np
    midi=tmp_path/'test.mid';out=tmp_path/'test.wav'
    write_midi([NoteEvent('piano',60,.1,.5)],midi)
    render_midi(midi,sf,out,tail_seconds=.1)
    y,sr=soundfile.read(out)
    assert sr==44100 and y.shape[1]==2
    assert len(y)/sr==pytest.approx(.6,abs=.002)
    assert .5<np.max(np.abs(y))<.99
    assert np.max(np.abs(y[:int(.09*sr)]))<.0001


def test_neutral_pitchwheel_does_not_detune_samples(tmp_path):
    pytest.importorskip('tinysoundfont')
    sf=Path('work/models/GeneralUser-GS.sf2')
    if not sf.exists():pytest.skip('local soundfont required')
    from audio_midi.render import render_midi
    from audio_midi.events import NoteEvent
    from audio_midi.midi import write_midi
    import soundfile as soundfile
    import numpy as np
    a=tmp_path/'a.mid';b=tmp_path/'b.mid'
    write_midi([NoteEvent('piano',60,0,.5)],a)
    m=mido.MidiFile(a);m.tracks[1].insert(0,mido.Message('pitchwheel',channel=0,pitch=0));m.save(b)
    render_midi(a,sf,tmp_path/'a.wav',tail_seconds=.1);render_midi(b,sf,tmp_path/'b.wav',tail_seconds=.1)
    x,_=soundfile.read(tmp_path/'a.wav');y,_=soundfile.read(tmp_path/'b.wav')
    assert np.max(np.abs(x-y))<.001
