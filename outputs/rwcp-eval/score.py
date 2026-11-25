"""Score chronological RWC-P onsets using the same matching as e2e."""
from collections import Counter
from dataclasses import replace

from audio_midi.evaluate import evaluate


KIT = {35: 36, 36: 36, 38: 38, 40: 38}
COUNTS = ('tp', 'fp', 'fn')


def score(reference, prediction, category, center, input_start, delay):
    """Both lists are filtered by onset in the same half-open audio interval."""
    start, end = center

    def crop(notes, shift):
        return [replace(note, onset=note.onset + shift - start,
                        offset=None if note.offset is None else note.offset + shift - start)
                for note in notes if note.category == category and start <= note.onset + shift < end]

    ref = crop(reference, delay)
    pred = crop(prediction, input_start)
    result = {}
    if category == 'drums':
        def other(notes):
            return dict(Counter(str(note.pitch) for note in notes if note.pitch not in KIT))

        result['other_drum_notes'] = {'reference': other(ref), 'prediction': other(pred)}
        ref = [replace(note, pitch=KIT[note.pitch]) for note in ref if note.pitch in KIT]
        pred = [replace(note, pitch=KIT[note.pitch]) for note in pred if note.pitch in KIT]
    result['reference_notes'] = len(ref)
    result['prediction_notes'] = len(pred)
    result['absent_category_false_positives'] = len(pred) if not ref else None
    result['exact'] = evaluate(ref, pred)[category]
    if category == 'bass':
        ref_pc, pred_pc = ([replace(note, pitch=note.pitch % 12) for note in notes]
                           for notes in (ref, pred))
        result['octave_free'] = evaluate(ref_pc, pred_pc)[category]
    return result


def pool(scores, metric):
    """Include empty-reference false positives in micro F1, like e2e."""
    tp, fp, fn = (sum(score[metric][key] for score in scores) for key in COUNTS)
    total = 2 * tp + fp + fn
    return {'tp': tp, 'fp': fp, 'fn': fn, 'f1': 2 * tp / total if total else None,
            'absent_category_false_positives': sum(
                score['absent_category_false_positives'] or 0 for score in scores
            )}
