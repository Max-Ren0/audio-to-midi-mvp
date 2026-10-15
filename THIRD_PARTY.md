# Third-party provenance

## Used for inference

- MT3-Infer: https://github.com/openmirlab/mt3-infer , fixed commit `d8cbd287470291dee335f84315c5a9b9ff6e6c8a`; wrapper MIT, includes components with their own terms. We call only the YourMT3 backend. No third-party model source is copied into this repository.
- YourMT3: https://huggingface.co/spaces/mimbres/YourMT3 , revision `5e66c1ea173a8186e0d20432b841d3180cc015b5`. The upstream model card declares Apache-2.0; the vendored YourMT3 LICENSE credits 2024 The YourMT3 Authors. Provenance metadata in MT3-Infer includes older inconsistent descriptions; use original model card and actual component license, not a blanket license assumption.
- The selected weight is the upstream `mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/checkpoints/last.ckpt`, SHA256 `ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25`. Downloaded locally and verified before load. No separate weight-specific license document was found during this experiment; do not treat this local prototype as a completed commercial licensing audit.
- The raw decoding protocol follows the upstream YourMT3 event interface. `selected.py` calls upstream task detokenization and implements project-specific pairing rather than upstream 10ms repairs. Model authors and license provenance are retained here and in its module docstring.

## Other runtime dependencies

FFmpeg/FFprobe are invoked as separately installed tools. PyTorch, NumPy, SciPy, mido and psutil are installed dependencies; their versions are in uv.lock and their upstream notices remain in installed distributions. No audio, weights or external research source snapshots are committed.

User-supplied music is used only locally with user approval; no ownership or redistribution rights are asserted.

## Quality-first experiment additions

- Demucs4.0.1 (MIT): https://github.com/facebookresearch/demucs ; htdemucs_6s weight 5c90dfd2-34c22ccb.th from dl.fbaipublicfiles.com. SHA256 34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd. Isolated torch2.5.1/torchaudio2.5.1 runtime. Piano separation is explicitly experimental with known bleed.
- Spotify Basic Pitch0.4.0 (Apache2.0): https://github.com/spotify/basic-pitch ; only ONNX model is used. Default CoreML/TensorFlow dependencies are omitted in this local ONNX configuration.
- librosa0.11 pYIN: https://librosa.org/doc/0.11.0/generated/librosa.pyin.html ; used on separated vocal and bass stems with onset boundaries, not a trained multi-instrument classifier.
- TinySoundFont Python bindings0.3.7 (MIT): https://github.com/nwhitehead/tinysoundfont-pybind ; offline synthesis only, PyAudio is not required for the code path used here and is omitted.
- GeneralUser GS2.0.3 by S. Christian Collins: https://github.com/mrbumpy409/GeneralUser-GS , commit684543d5e5efaef08d02be50dcda8d552478fa60. SF2 SHA256 9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe. The upstream LICENSE v2.0 permits music creation and records qualifications about historical sample provenance. The library and its license remain local; no SoundFont is redistributed in this repository. WAV previews are rendered from MIDI using this sample bank, with no original-song audio blended in.

## v0.1免费实验增补（2026-10-15）

- Transkun 2.0.1，官方 https://github.com/Yujia-Yan/Transkun ，由PyPI同名2.0.1分发包安装，代码声明MIT。使用随包pretrained/2.0.pt（V2默认无踏板延长口径）与2.0.conf；权重与配置不上传。权重SHA256 `50a80010effc2a59ffcd068a95cd2b29bd7f23a27a3515bc3ccd209c89a3d44c`（56,408,978字节）；配置SHA256 `d3d989214eb148230ee5df476d994dcde6af595904d3f968f1221d2e3bea5ac6`。代码许可不自动替代单独权重商用审计，本轮为用户本地研究验证。
- ADTOF-PyTorch 0.1.0，官方原作者仓库链接的移植 https://github.com/xavriley/ADTOF-pytorch ，固定Git提交 `85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9`。随包权重SHA256 `1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320`（3,617,805字节）。原始ADTOF https://github.com/MZehren/ADTOF 内容采用CC BY-NC-SA 4.0；移植不能消除原权重非商业约束。仅作研究对照，未进入v0.1锁定交付路线，也不默认用于商用发行。
- 新组件使用项目work/sep-env隔离环境（torch/torchaudio2.5.1、numpy1.26.4）；完整当前环境固定于requirements-v01-specialists.txt。基线YourMT3仍使用项目.venv及原固定权重，不改全局环境。
- 两套方案列出的MVSEP、Klangio、RipX、Logic、Aria-AMT等未在本轮调用或安装。公开能力与本曲成绩分开，不声称未测工具达到任何准确率。
