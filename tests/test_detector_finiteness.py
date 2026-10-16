import numpy as np
import pytest

def test_detector_nonfinite_geometry_or_objectness_must_not_become_silent_zero_detection():
    from audio_midi.drums import require_finite_detector_outputs
    for column in [0,4,5]:
        x=np.zeros((1,16),dtype=np.float32);x[0,column]=np.nan
        with pytest.raises(ValueError,match='Nonfinite'):require_finite_detector_outputs([x])

def test_detector_finite_empty_output_is_distinct_from_numeric_failure():
    from audio_midi.drums import require_finite_detector_outputs
    require_finite_detector_outputs([np.empty((0,16)),np.zeros((1,16))])
