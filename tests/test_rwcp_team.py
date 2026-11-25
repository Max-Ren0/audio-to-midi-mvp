from pathlib import Path

import pytest


@pytest.fixture
def team(monkeypatch):
    pytest.importorskip('pretty_midi')
    pytest.importorskip('soundfile')
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'outputs/rwcp-eval'))
    import run_team
    return run_team


def test_shared_stages_only_include_selected_routes(team):
    mix = team.needed_stages({'S1': ['P1', 'B1', 'D1'], 'S5': ['P2', 'B2', 'D4']})
    assert mix == {'sw', 'mt3-mix', 'decode-mt3-mix', 'transkun-piano', 'decode-mu',
                   'mu-mix', 'adtof-drums'}


def test_bootstrap_is_paired_at_song_level(team):
    perfect = {'tp': 100, 'fp': 0, 'fn': 0}
    miss = {'tp': 0, 'fp': 0, 'fn': 1}
    outcome = team.bootstrap({'S1': [miss, perfect], 'S3': [miss, perfect],
                              'S5': [miss, perfect], 'S6': [miss, perfect]})
    assert outcome['deltas']['S5-S1'] == [0., 0.]
    assert outcome['deltas']['S6-S3'] == [0., 0.]
    assert outcome['absolute']['S5'] == [0., 1.]


def test_presence_uses_all_gm_drum_onsets_in_center_context(team):
    from audio_midi.events import NoteEvent
    prediction = [NoteEvent('drums', 42, 2, 2.1), NoteEvent('drums', 45, 3, 3.1),
                  NoteEvent('drums', 36, 4, 4.1), NoteEvent('drums', 38, .2, .3)]
    assert team.should_suppress(prediction, 3, (10, 14), 9) is False
    assert team.should_suppress(prediction, 4, (10, 14), 9) is True
    assert team.should_suppress(prediction, 3, (10, 13), 9) is True
    assert team.should_suppress(prediction, 0, (10, 13), 9) is False


def test_parallel_batch_respects_new_load_and_memory_limits(team):
    assert team.batch_jobs(2, {'load': 7, 'swap_free_gib': 1.5, 'pressure_free_pct': 25}) == 2
    assert team.batch_jobs(2, {'load': 7.1, 'swap_free_gib': 2, 'pressure_free_pct': 45}) == 1
    assert team.batch_jobs(2, {'load': 6, 'swap_free_gib': 1.49, 'pressure_free_pct': 45}) == 1
    assert team.batch_jobs(2, {'load': 6, 'swap_free_gib': 2, 'pressure_free_pct': 24}) == 1
    assert team.batch_jobs(2, {'load': 6, 'swap_free_gib': None, 'pressure_free_pct': 45}) == 1


def test_swapusage_parser_uses_reported_free_space(team):
    assert team.swap_free_gib('vm.swapusage: total = 7168.00M used = 5632.00M free = 1536.00M') == 1.5
    assert team.swap_free_gib('free = 0.95G (encrypted)') == .95
    assert team.swap_free_gib('unknown') is None
