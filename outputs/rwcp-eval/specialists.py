"""Audio-only pilot stages for routes without a standalone project entry point."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_midi.bass_evidence import harmonic_score
from audio_midi.muscriptor_routing import parse_note_lines
from audio_midi.quality import read_notes


def pitch_hz(pitch):
    return 440 * 2 ** ((pitch - 69) / 12)


def octave_correct(notes, audio, sr):
    """Only edit an octave when both the fundamental and harmonic score support it."""
    corrected = []
    for note in notes:
        if note.category != 'bass':
            continue
        if note.offset is None:
            corrected.append(note)
            continue
        start = round((note.onset + .025) * sr)
        stop = round(min(note.offset, note.onset + .30) * sr)
        segment = audio[max(0, start):stop]
        changed = note
        if len(segment) >= .12 * sr and np.max(np.abs(segment)) >= 1e-4:
            nfft = 2 ** int(np.ceil(np.log2(sr / 2)))
            spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment)), nfft))
            freq = np.fft.rfftfreq(nfft, 1 / sr)

            def fundamental(pitch):
                hz = pitch_hz(pitch)
                return float(spectrum[np.abs(freq - hz) <= max(3, hz * .025)].max())

            options = [pitch for pitch in (note.pitch, note.pitch - 12, note.pitch + 12)
                       if 24 <= pitch <= 67]
            if options:
                evidence = {p: harmonic_score(segment, sr, p) for p in options}
                best = max(options, key=evidence.get)
                if (best != note.pitch and evidence[best] > 1.45 * harmonic_score(segment, sr, note.pitch)
                        and fundamental(best) > 1.5 * fundamental(note.pitch)):
                    changed = replace(note, pitch=best)
        corrected.append(changed)
    return corrected


def stretched_piano_votes(notes, audio, sr):
    """Prototype P5 timbre proxy using the string partials' inharmonicity."""
    eligible = sorted((n for n in notes if n.category == 'piano' and 60 <= n.pitch <= 84
                       and n.offset is not None and n.offset - n.onset >= .20),
                      key=lambda n: n.onset)
    votes = []
    harmonic = np.arange(1, 9)
    for note in eligible[:120]:
        segment = audio[round((note.onset + .03) * sr):round(min(note.offset, note.onset + .35) * sr)]
        if len(segment) < .15 * sr or np.max(np.abs(segment)) < 1e-4:
            continue
        nfft = 2 ** int(np.ceil(np.log2(sr * 2)))
        spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment)), nfft))
        hz = pitch_hz(note.pitch)
        bin_hz = sr / nfft
        peaks = []
        for multiple in harmonic:
            low = round(hz * multiple * .985 / bin_hz)
            high = round(hz * multiple * 1.065 / bin_hz)
            index = low + int(spectrum[low:high].argmax())
            peaks.append((index * bin_hz, spectrum[index]))
        if sum(level > .035 * max(level for _, level in peaks) for _, level in peaks[3:]) < 3:
            continue
        freq = np.asarray([peak for peak, _ in peaks])
        relative = (freq / harmonic) / freq[0] - 1
        slope = np.dot(harmonic[2:] ** 2 - 1, relative[2:]) / np.sum((harmonic[2:] ** 2 - 1) ** 2)
        residual = np.median(np.abs(relative[2:] - slope * (harmonic[2:] ** 2 - 1)))
        votes.append(.00012 <= slope <= .0015 and residual <= .003)
    return len(votes), int(sum(votes))


def choose_piano(notes, audio, sr):
    usable, positive = stretched_piano_votes(notes, audio, sr)
    return {'usable_notes': usable, 'stretched_notes': positive,
            'route': 'P2' if usable >= 8 and positive / usable >= .60 else 'P1'}


def adtof(audio, weights, output):
    import torch
    from adtof_pytorch.model import (calculate_n_bins, create_frame_rnn_model,
                                    load_pytorch_weights, load_audio_for_model)
    from adtof_pytorch.post_processing import (PeakPicker, FRAME_RNN_THRESHOLDS, LABELS_5,
                                              activations_to_pretty_midi)

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    model = load_pytorch_weights(create_frame_rnn_model(calculate_n_bins()), str(weights), strict=True)
    model.eval()
    with torch.inference_mode():
        activations = model(load_audio_for_model(str(audio))).cpu().numpy()
    if activations.ndim != 3 or activations.shape[-1] != 5 or not np.isfinite(activations).all():
        raise ValueError('Invalid ADTOF activations')
    picker = PeakPicker(thresholds=[x * .75 for x in FRAME_RNN_THRESHOLDS], fps=100)
    peaks = picker.pick(activations, labels=LABELS_5)[0]
    activations_to_pretty_midi(peaks, velocity=100, note_duration=.1, program=1,
                              is_drum=True).write(str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('piano-gate', 'bass-octave', 'adtof'))
    parser.add_argument('audio', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.stage == 'adtof':
        adtof(args.audio, args.source, args.output)
        return
    audio, sr = sf.read(args.audio, dtype='float32', always_2d=True)
    mono = audio.mean(axis=1)
    if args.stage == 'piano-gate':
        value = choose_piano(read_notes(args.source), mono, sr)
    else:
        notes = parse_note_lines(args.source.read_text())
        value = {'notes': [asdict(note) for note in octave_correct(notes, mono, sr)]}
    args.output.write_text(json.dumps(value, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
