"""Audio-only beat inference and MIDI grid export for the one-click route."""
from bisect import bisect_right
from dataclasses import dataclass
from itertools import accumulate

import mido
import numpy as np


METHOD = 'librosa.beat_track + spectral flux and chroma accents'
DEFAULT_TEMPO = 500_000
EXPORT_PPQ = 30_720
QUANTIZE = {'1/4': 1, '1/8': 2, '1/16': 4}


@dataclass(frozen=True)
class BeatEstimate:
    beats: tuple[float, ...] = ()
    confidence: float | None = None
    meter: int = 4
    downbeat_index: int = 0
    meter_confidence: float | None = None
    meter_fallback: bool = True
    fallback_reason: str | None = None


def _infer_meter(accents):
    """Compare recurring accents in three- and four-beat groups."""
    scale = max(float(np.std(accents)), 1e-6)
    profiles = {
        meter: np.array([np.mean(accents[phase::meter]) for phase in range(meter)])
        for meter in (3, 4)
    }
    scores = {meter: float(np.ptp(profile) / scale) for meter, profile in profiles.items()}
    best = max(scores, key=scores.get)
    confidence = min(1., abs(scores[4] - scores[3]))
    fallback = scores[best] < .35 or confidence < .18 or len(accents) < 12
    meter = 4 if fallback else best
    return meter, int(np.argmax(profiles[meter])), confidence, fallback


def _chord_changes(librosa, samples, sample_rate, hop, frames):
    chroma = librosa.feature.chroma_stft(
        y=samples, sr=sample_rate, hop_length=hop, n_fft=4096, norm=2,
    )
    # Average immediately before and after each beat. Ignore the frames
    # closest to the attack, where the centered FFT blends both chords.
    offsets = np.arange(9, 22)
    before = np.mean(chroma[:, np.clip(frames[:, None] - offsets, 0, chroma.shape[1] - 1)], axis=2)
    after = np.mean(chroma[:, np.clip(frames[:, None] + offsets, 0, chroma.shape[1] - 1)], axis=2)
    novelty = np.linalg.norm(after - before, axis=0)
    return np.clip(novelty / max(float(np.percentile(novelty, 90)), 1e-6), 0, 2)


def detect_beats(samples, sample_rate):
    """Estimate beats and a single meter, with heuristic confidence in [0, 1]."""
    try:
        import librosa

        hop = max(1, round(sample_rate / 100))
        n_fft = 1024
        mel = librosa.feature.melspectrogram(
            y=samples, sr=sample_rate, n_fft=n_fft, hop_length=hop, n_mels=64,
        )
        log_mel = librosa.power_to_db(mel)
        flux = librosa.onset.onset_strength_multi(
            S=log_mel, sr=sample_rate, hop_length=hop, n_fft=n_fft,
            channels=[0, 8, 24, 64],
        )
        envelope = np.mean(flux, axis=0)
        _, frames = librosa.beat.beat_track(
            onset_envelope=envelope, sr=sample_rate, hop_length=hop, trim=True,
        )
    except (ImportError, ValueError, RuntimeError) as error:
        return BeatEstimate(fallback_reason=f'{type(error).__name__}: {error}')
    frames = frames[frames * hop < len(samples)]
    if len(frames) < 8:
        return BeatEstimate(fallback_reason='insufficient_beats')

    beats = frames * hop / sample_rate
    periods = np.diff(beats)
    period = float(np.median(periods))
    regularity = float(np.mean(np.abs(periods / period - 1) <= .25))
    if not .2 <= period <= 1.5 or regularity < .65:
        return BeatEstimate(confidence=regularity, fallback_reason='unstable_beat_intervals')

    neighborhood = np.clip(frames[:, None] + np.arange(-5, 6), 0, len(envelope) - 1)
    band_accents = np.max(flux[:, neighborhood], axis=2)
    band_accents /= np.maximum(np.percentile(band_accents, 90, axis=1)[:, None], 1e-6)
    attacks = np.array([.5, .35, .15]) @ np.clip(band_accents, 0, 2)
    try:
        changes = _chord_changes(librosa, samples, sample_rate, hop, frames)
    except (ValueError, RuntimeError) as error:
        return BeatEstimate(confidence=regularity, fallback_reason=f'{type(error).__name__}: {error}')
    accents = .4 * attacks + .6 * changes
    meter, phase, confidence, fallback = _infer_meter(accents)
    return BeatEstimate(tuple(float(beat) for beat in beats), regularity, meter, phase,
                        confidence, fallback)


class TempoMap:
    """A MIDI tempo map with the actual times implied by integer tempo values."""

    def __init__(self, estimate):
        self.meter = estimate.meter
        self.ticks = [0]
        self.tempos = [DEFAULT_TEMPO]
        if estimate.beats:
            self._fit(estimate.beats, estimate.downbeat_index)
        self.seconds = [0., *accumulate(
            mido.tick2second(end - start, EXPORT_PPQ, tempo)
            for start, end, tempo in zip(self.ticks, self.ticks[1:], self.tempos)
        )]

    def _fit(self, beats, phase):
        period = float(np.median(np.diff(beats)))
        # The DAW starts bar 1 at tick 0. Fit the pickup to the nearest
        # phase-correct grid point with a plausible lead-in tempo.
        for anchor, beat in enumerate(beats):
            residue = (anchor - phase) % self.meter
            if beat == 0 and residue == 0:
                first_beat = 0
                break
            first_beat = residue + self.meter * max(0, round((beat / period - residue) / self.meter))
            first_beat = first_beat or self.meter
            if .65 * period <= beat / first_beat <= 1.5 * period:
                break

        seconds = 0.
        tick = 0
        tempos = []
        ticks = []
        for index, beat in enumerate(beats[anchor:]):
            quarter = first_beat + index
            if index not in (0, len(beats) - anchor - 1) and quarter % self.meter:
                continue
            target = quarter * EXPORT_PPQ
            if target == tick:
                continue
            tempo = round((beat - seconds) * 1e6 * EXPORT_PPQ / (target - tick))
            if not 1 <= tempo <= 0xFFFFFF:
                raise ValueError('Detected beat interval exceeds MIDI tempo limits')
            if not tempos or tempo != tempos[-1]:
                ticks.append(tick)
                tempos.append(tempo)
            seconds += mido.tick2second(target - tick, EXPORT_PPQ, tempo)
            tick = target
        self.ticks, self.tempos = ticks, tempos

    def to_ticks(self, seconds):
        index = bisect_right(self.seconds, seconds) - 1
        residual = seconds - self.seconds[index]
        return self.ticks[index] + round(mido.second2tick(
            residual, EXPORT_PPQ, self.tempos[index],
        ))

    def receipt(self, estimate, enabled, quantize, moved=0):
        periods = np.diff(estimate.beats)
        return {
            'enabled': enabled,
            'method': METHOD if enabled else 'fixed',
            'bpm': round(60 / float(np.median(periods)), 3) if len(periods) else 120,
            'time_signature': f'{self.meter}/4',
            'beat_count': len(estimate.beats),
            'first_detected_downbeat_seconds': (
                estimate.beats[estimate.downbeat_index] if estimate.beats else None
            ),
            'tempo_changes': len(self.tempos) - 1,
            'confidence': estimate.confidence,
            'meter_confidence': estimate.meter_confidence,
            'meter_fallback': enabled and estimate.meter_fallback,
            'fallback': enabled and not estimate.beats,
            'fallback_reason': estimate.fallback_reason,
            'quantize_grid': quantize,
            'quantized': moved > 0,
            'quantized_onsets': moved,
        }


def _quantize_onsets(events, subdivision):
    # A repeated pitch must keep its original on/off ordering. Skip a snap
    # if the new onset would pass another event of the same pitch.
    step = EXPORT_PPQ // subdivision
    groups = {}
    for index, (_, message) in enumerate(events):
        if message.type in ('note_on', 'note_off'):
            groups.setdefault((message.channel, message.note), []).append(index)
    moved = 0
    for group in groups.values():
        for position, index in enumerate(group):
            tick, message = events[index]
            if message.type != 'note_on' or message.velocity == 0:
                continue
            snapped = ((tick + step // 2) // step) * step
            lower = events[group[position - 1]][0] if position else 0
            upper = events[group[position + 1]][0] if position + 1 < len(group) else float('inf')
            if snapped != tick and lower <= snapped < upper:
                events[index] = snapped, message
                moved += 1
    return moved


def write_aligned_midi(source, target, tempo_map, quantize=None):
    """Retick the fixed-120 MIDI without changing its event times within tick precision."""
    midi = mido.MidiFile(source)
    if midi.type != 1 or any(
        message.tempo != DEFAULT_TEMPO or tick != 0
        for track in midi.tracks
        for tick, message in zip(accumulate(msg.time for msg in track), track)
        if message.type == 'set_tempo'
    ):
        raise ValueError('Beat alignment requires a fixed-120 BPM type-1 MIDI')
    output = mido.MidiFile(type=1, ticks_per_beat=EXPORT_PPQ, charset=midi.charset)
    moved = 0
    for index, track in enumerate(midi.tracks):
        events = []
        if index == 0:
            events.append((0, mido.MetaMessage(
                'time_signature', numerator=tempo_map.meter, denominator=4,
            )))
            events.extend((tick, mido.MetaMessage('set_tempo', tempo=tempo))
                          for tick, tempo in zip(tempo_map.ticks, tempo_map.tempos))
        for tick, message in zip(accumulate(msg.time for msg in track), track):
            if message.type in ('set_tempo', 'time_signature') or (
                message.type == 'text'
                and message.text == 'Tempo and time signature are defaults, not detected.'
            ):
                continue
            seconds = mido.tick2second(tick, midi.ticks_per_beat, DEFAULT_TEMPO)
            events.append((tempo_map.to_ticks(seconds), message))
        if quantize:
            moved += _quantize_onsets(events, QUANTIZE[quantize])
        prior = 0
        target_track = mido.MidiTrack()
        for tick, message in sorted(events, key=lambda event: event[0]):
            target_track.append(message.copy(time=tick - prior))
            prior = tick
        output.tracks.append(target_track)
    output.save(target)
    return moved
