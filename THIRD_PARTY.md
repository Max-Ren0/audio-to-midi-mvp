# Third-party provenance

## Used for inference

- MT3-Infer: https://github.com/openmirlab/mt3-infer , fixed commit `d8cbd287470291dee335f84315c5a9b9ff6e6c8a`; wrapper MIT, includes components with their own terms. We call only the YourMT3 backend. No third-party model source is copied into this repository.
- YourMT3: https://huggingface.co/spaces/mimbres/YourMT3 , revision `5e66c1ea173a8186e0d20432b841d3180cc015b5`. The upstream model card declares Apache-2.0; the vendored YourMT3 LICENSE credits 2024 The YourMT3 Authors. Provenance metadata in MT3-Infer includes older inconsistent descriptions; use original model card and actual component license, not a blanket license assumption.
- The selected weight is the upstream `mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/checkpoints/last.ckpt`, SHA256 `ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25`. Downloaded locally and verified before load. No separate weight-specific license document was found during this experiment; do not treat this local prototype as a completed commercial licensing audit.
- The raw decoding protocol follows the upstream YourMT3 event interface. `selected.py` calls upstream task detokenization and implements project-specific pairing rather than upstream 10ms repairs. Model authors and license provenance are retained here and in its module docstring.

## Other runtime dependencies

FFmpeg/FFprobe are invoked as separately installed tools. PyTorch, NumPy, SciPy, mido and psutil are installed dependencies; their versions are in uv.lock and their upstream notices remain in installed distributions. No audio, weights or external research source snapshots are committed.

User-supplied music is used only locally with user approval; no ownership or redistribution rights are asserted.
