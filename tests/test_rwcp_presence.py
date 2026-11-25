from pathlib import Path

import pytest


@pytest.fixture
def presence(monkeypatch):
    pytest.importorskip('pretty_midi')
    pytest.importorskip('soundfile')
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'outputs/rwcp-eval'))
    import presence
    return presence


def test_presence_needs_negative_examples_and_prefers_smallest_equal_threshold(presence):
    observations = [(0, 1), (0, 0), (0, 1), (1, 5), (1, 9)]
    assert presence.choose_threshold(observations[:2] + observations[3:])['threshold'] == 0
    outcome = presence.choose_threshold(observations)
    assert outcome['threshold'] == 2
    assert outcome['saved_false_notes'] == 2


def test_presence_preserves_quiet_positive_examples(presence):
    outcome = presence.choose_threshold([(0, 1), (0, 1), (0, 1), (1, 1)])
    assert outcome['threshold'] == 0
    assert outcome['saved_false_notes'] == 0
