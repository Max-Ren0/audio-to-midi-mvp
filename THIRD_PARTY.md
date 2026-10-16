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


## BS-Roformer-SW本地对照（2026-10-15）

- 推理源码：[ZFTurbo/MSST](https://github.com/ZFTurbo/Music-Source-Separation-Training)，固定6fdad13686bb7e84d029ec66f9dbe76e65c93ebf。架构BSRoformer；仅本地CPU推理，torch.load(weights_only=True)，1939个state键strict加载通过。
- 原jarredou模型地址401，使用[Blakus重托管](https://huggingface.co/Blakus/bs_roformer_sw_6stem/tree/dd755f5f5eaa1b01deb970fb296a55f6fec458a6)，权重699412152字节，SHA256 24e7d35ee9c64415673d3fd33e06a67cac2c103c5df6267ba1576459c775916e，与LFS元数据一致。上传者称恢复原模型；没有验证其与MVSEP服务当前checkpoint字节相同。
- 重托管模型卡写MIT，但[另一转换提供者的来源说明](https://huggingface.co/elicwhite/bs-roformer-sw-6stem-onnx)明确原权重无独立许可和训练来源信息，因此本实验不构成商用授权审计。代码许可与模型权重许可分开。未用ONNX转换权重。
- config原件在outputs/two-methods/SW-config.yaml；CPU2线程、float32/AMP关、chunk588800、overlap2、batch1；记录与榜单服务配置未必相同。
- 额外依赖固定requirements-roformer-experiment.txt，仅work/sep-env，不修改全局。原有torch2.5.1/numpy1.26.4环境沿用。

## Locked piano B and drum research update (2026-10-16)

The piano entrypoint pins the existing SW model/config/wrapper and Transkun pretrained 2.0 (package 2.0.1) by hashes in `config/piano-b.lock.json`; upstream source is checked at its recorded Git revision. Pinning is reproducibility, not a new commercial-license clearance for the rehosted SW weights. Existing Transkun and GeneralUser GS license notes remain applicable.

Drum research reuses installed `adtof-pytorch==0.1.0` and its bundled `adtof_frame_rnn_pytorch_weights.pth` (3,617,805 bytes, SHA256 `1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320`). Per-file package code hashes, strict model load, input and activation hashes are in `outputs/drums/*activation-receipt.json`. Model forward is run once per registered input; threshold variants reuse the same activations. No checkpoint or input media is distributed in Git.

The original [ADTOF project](https://github.com/MZehren/ADTOF) declares CC BY-NC-SA 4.0; the existing noncommercial research restriction remains unresolved for product deployment regardless of the PyTorch port's code license. The hybrid and generated comparisons are explicitly research artifacts, not automatic commercial-production approval. No remote service was invoked or newly purchased in this update.

## Drum optimization v2 (2026-10-16)

- OaF third-party conversion: https://huggingface.co/thebluescreen/oaf-drums-onnx , revision771fd5529062b9f6f0b58f01cc4b9819db046f4a, ONNX5,966,247bytes SHA25623d4b05ce7e9715bdb4396823d68bc886e8a958fa9f6266c0f7132b78098b521 matches HF LFS. Model card/NOTICE declare Apache2.0. Numerical parity with original TensorFlow checkpoint was not independently reproduced. Decoder reference app https://github.com/Sillybit-io/silly-midi-tools revision16bf8de185f195d03f68fbf853da5acad2e26b92; no app resources redistributed.
- YODO official https://github.com/varsaav/yodo revision0cb980a11e9ba1a37cbafddec1e85c66d8ffa236, author Colab-linked tri2-80k.weights256,231,380bytes SHA2561cdc360b6c0b72e669d6736c1df0c9e171d157aadddbebe3b67130874264f588. CPU OpenCV4.11 adapter, not parity-validated against author Darknet; zero detections on both tested sources. No YODO event enters final MIDI. Weight redistribution/commercial status not audited; not distributed.
- IDM official https://github.com/bernardo-torres/inverse-drum-machine revision456656868538205ef756912c7cf5b0fd936de8af, repository Apache2.0; bundled idm-44-train-kits val-epoch518 checkpoint2,544,694bytes SHA2565856a9bee7c6d503842795756d238dc8470f6f3e010e9e4f33ede0362850cb4c. Official encoder-only strict state loading, no manual onset override. Full checkpoint and dataset rights have not received a separate commercial audit. No IDM prediction enters final selected result.
- Existing ADTOF noncommercial and rehosted SW license uncertainties remain. No user audio, checkpoint, downloaded upstream code, or bulk media is committed. New wrappers authored here are retained with hash receipts. Isolated overlay dependencies do not change global Python.

## Open-hat three-model experiment (2026-10-16)

DrumSep MDX23C six-stem architecture/inference is read from https://github.com/openmirlab/mdxnet-infer at cb4779eedeca4f55ba498df8e234e2b5f4b90aaf. The release-mirrored community checkpoint by aufr33/jarredou is437652699bytes, SHA256 d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0; config2417bytes SHA25617d1649a227f841165bdb4c11a42082898192a1ea3ceab7e7e0b9293d6589dd6. Original weight rights are not established by mirror availability; local research here is not commercial clearance. No checkpoint or upstream source is redistributed in Git. Existing source dependencies are used locally, no global environment changes.

YODO original published single-channel cfg is incompatible with the downloaded tri2-80k.weights layout in the tested OpenCV loader. The research adapter copies the cfg and changes channels to3, replicates the grayscale spectrogram across RGB, and rejects nonfinite raw outputs. Full Darknet parity remains unproved. Prior zero detections were numerically invalid, not evidence of upstream model quality. All original output GM labels are retained. Synthetic controls use existing GeneralUser GS2.0.3 sample bank and contain no user-song reference events; no weights were trained. All previous license limitations remain.

## 2026-10-17 贝斯音高/分离对照

- torchcrepe0.0.24 full：官方 https://github.com/maxrmorrison/torchcrepe ，代码MIT；随PyPI包full.pth SHA256 133225604dedd2e4005f8bbd1bd0a2ec073ba8b7a6cd31ff6d5edbbfa3539986。代码许可不替代完整上游权重商用授权审查。
- PENN官方 https://github.com/interactiveaudiolab/penn ，代码MIT。因1.0.0/torbi与当前torch2.5.1不兼容，实际采用0.0.14、官方viterbi-normal解码；不声称与新版数值等价。FCNF0++权重来自 https://huggingface.co/maxrmorrison/fcnf0-plus-plus/tree/74911e26f43ad38790a42592e77f9d8be0a5dd1c ，SHA256 28d89add04722461f831249a338b74516a96dedd3301ed794c18953d51d1b960。未完成独立权重商用审查。
- Demucs4.0.1 htdemucs_ft官方bag的bass专用d12395a8-e57c48e6.th，官方dl.fbaipublicfiles.com/demucs/hybrid_transformer/来源；SHA256 e57c48e6b0e38af4f7118d7bd08c49f0a0c0edf7d09143bdd902ea0d237303e6。仅执行bass专用checkpoint，非完整4模型bag推理；保留官方归一化与恢复，随机shift不保证与完整bag同字节。
- 原Demucs6s与已有SW来源沿用既有记录。新增依赖只在ignored work/bass-models目录，版本与源码/权重/输出哈希见outputs/bass-models；没有训练或向服务商上传音频。
