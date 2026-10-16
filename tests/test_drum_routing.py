import pytest
from audio_midi.events import NoteEvent

def note(p,t=1):return NoteEvent('drums',p,t,t+.1,80,0)

def test_whole_key_routing_preserves_source_events_without_relabeling():
    from audio_midi.drums import route_drum_keys
    a=[note(36),note(51)];b=[note(51,2),note(49,3)]
    result=route_drum_keys({'a':a,'b':b},'a',{51:'b'},10)
    assert [(n.pitch,n.onset) for n in result]==[(36,1),(51,2)]

def test_routing_rejects_unknown_source_and_invalid_key():
    from audio_midi.drums import route_drum_keys
    with pytest.raises(ValueError):route_drum_keys({'a':[]},'a',{51:'absent'},10)
    with pytest.raises(ValueError):route_drum_keys({'a':[]},'a',{200:'a'},10)

def test_consensus_uses_support_once_and_keeps_anchor_event():
    from audio_midi.drums import consensus_drums
    anchor=[note(51,1),note(51,1.08)];support=[note(51,1.035)]
    assert consensus_drums(anchor,support,.05)==[anchor[0]]

def test_consensus_requires_same_key_and_never_creates_new_notes():
    from audio_midi.drums import consensus_drums
    anchor=[note(51,1)];support=[note(49,1)]
    assert consensus_drums(anchor,support,.05)==[]


def test_explicit_coarse_cymbal_support_keeps_original_ride_key():
    from audio_midi.drums import consensus_drums
    anchor=[note(51,1),note(48,2)];support=[note(49,1.01),note(49,2.01)]
    assert consensus_drums(anchor,support,.05,families=({49,51,53,55,57,59},))==[anchor[0]]


def test_short_final_spectrogram_patch_maps_to_its_true_timeline():
    from audio_midi.drums import detection_region
    assert detection_region((.5,.5,.2,.5),924,512,120)==(1128,1231,30,90)


def test_detection_geometry_rejects_invalid_dimensions():
    from audio_midi.drums import detection_region
    with pytest.raises(ValueError):detection_region((.5,.5,.2,.5),0,0,120)


def test_supported_augmentation_preserves_existing_attacks_and_only_adds_new_hits():
    from audio_midi.drums import augment_supported_drums
    base=[note(42,1)]
    weak=[note(42,.98),note(42,1.2),note(42,1.5)]
    support=[note(42,1),note(42,1.21)]
    result=augment_supported_drums(base,weak,support,.05,10)
    assert [(n.pitch,n.onset) for n in result]==[(42,1),(42,1.2)]

@pytest.mark.parametrize('tolerance',[-1,float('nan')])
def test_consensus_rejects_invalid_tolerance(tolerance):
    from audio_midi.drums import consensus_drums
    with pytest.raises(ValueError):consensus_drums([],[],tolerance)
