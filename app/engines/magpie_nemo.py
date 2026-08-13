"""MagpieTTS engine backed by NVIDIA NeMo Speech.

Uses MagpieTTSModel.do_tts(transcript, language, apply_TN, use_cfg, speaker_index)
which returns (audio float32 [-1,1], length) at 22.05 kHz mono.
"""

import logging
import threading

import numpy as np

from app.engines.base import TTSEngine

logger = logging.getLogger("magpie.engine")


class MagpieNemoEngine(TTSEngine):
    SAMPLE_RATE = 22050

    def __init__(self, model_id: str = "magpie-tts-multilingual-357m",
                 codec_id: str = "nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps"):
        self.model_id = model_id
        self.codec_id = codec_id
        self._model = None
        self._precision = None
        self._device = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def precision(self) -> str | None:
        return self._precision

    def _install_dtype_shims(self, torch) -> None:
        """NeMo eager inference mixes fp32 masks with reduced-precision weights.

        transformer_2501 multiplies hidden states by fp32 attention masks
        (``x * x_mask``), which promotes the activations to fp32 and then
        crashes inside bf16/fp16 LayerNorm and Linear ops. Align tensors to
        the weight dtype at the op boundary so reduced-precision inference
        works end to end. No-op for pure fp32 models.
        """
        import torch.nn.functional as F

        if getattr(F, "_magpie_dtype_shims_installed", False):
            return

        _orig_ln = F.layer_norm
        def _ln(input, normalized_shape, weight=None, bias=None, eps=1e-5):
            if weight is not None and input.dtype != weight.dtype:
                input = input.to(weight.dtype)
            return _orig_ln(input, normalized_shape, weight, bias, eps)

        _orig_lin = F.linear
        def _lin(input, weight, bias=None):
            if input.dtype != weight.dtype:
                input = input.to(weight.dtype)
            return _orig_lin(input, weight, bias)

        F.layer_norm = _ln
        F.linear = _lin
        F._magpie_dtype_shims_installed = True
        logger.info("installed dtype-alignment shims for reduced-precision inference")

    def load(self, model_path: str, precision: str, device: str = "cuda:0") -> None:
        """model_path may be a HF repo id or a local .nemo file."""
        with self._lock:
            try:
                import torch
                from nemo.collections.tts.models import MagpieTTSModel
            except ImportError as e:
                raise RuntimeError(
                    "NeMo Speech toolkit is not installed. Run scripts/install.sh first.") from e

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available on this host.")

            logger.info("loading %s (precision=%s) onto %s ...", model_path, precision, device)
            if model_path.endswith(".nemo"):
                model = MagpieTTSModel.restore_from(model_path, map_location=device)
            else:
                model = MagpieTTSModel.from_pretrained(model_path)

            codec = getattr(model, "codec_model", None)
            if codec is None:
                logger.info("checkpoint has no embedded codec; attempting %s", self.codec_id)
                try:
                    from nemo.collections.tts.models import AudioCodecModel
                    codec = AudioCodecModel.from_pretrained(self.codec_id)
                    model.codec_model = codec
                except Exception as e:
                    logger.warning("codec attach failed: %s", e)

            model.eval()
            # Deterministic inference: greedy/argmax decoding instead of the
            # checkpoint default (temperature=0.7, topk=80 multinomial sampling).
            # Sampling on code-mixed (Hinglish) text often loops past the EOS and
            # hallucinates long repeated audio; greedy keeps output bounded and
            # reproducible. See sample_autoregressive (temperature <= 0 -> argmax).
            #
            # ignore_finished_sentence_tracking=False enables NeMo's attention
            # based sentence-completion tracking: once cross-attention reaches the
            # end of the text it forces the audio EOS token. This is the reliable
            # backstop against the occasional missed sampled-EOS token (fp16 CUDA
            # kernels are nondeterministic), which otherwise runs to the
            # max_decoder_steps ceiling and produces ~21s of looped audio.
            try:
                ip = model.inference_parameters
                ip.temperature = 0.01
                ip.topk = 1
                ip.eos_detection_method = "argmax_any"
                ip.ignore_finished_sentence_tracking = False
                logger.info("inference: greedy decoding (temperature=0.01, topk=1, eos=argmax_any, sentence_tracking=enabled)")
            except Exception as e:
                logger.warning("could not set greedy inference params: %s", e)
            dtype = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}.get(precision)
            if dtype is not None and dtype != torch.float32:
                self._install_dtype_shims(torch)
                model = model.to(dtype=dtype)
            model = model.to(device)
            self._model = model
            self._precision = precision
            self._device = device
            logger.info("model loaded: %s", type(model).__name__)

    def unload(self) -> None:
        with self._lock:
            if self._model is not None:
                import torch
                self._model = None
                torch.cuda.empty_cache()
                logger.info("model unloaded, CUDA cache cleared")

    def synthesize(self, text: str, language: str, speaker_index: int,
                   apply_tn: bool = True, use_cfg: bool = True, cfg_scale: float = 2.5,
                   cancel_event=None) -> np.ndarray:
        with self._lock:
            if self._model is None:
                raise RuntimeError("model not loaded")
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("cancelled")
            try:
                audio, _ = self._model.do_tts(
                    transcript=text,
                    language=language,
                    apply_TN=apply_tn,
                    use_cfg=use_cfg,
                    speaker_index=int(speaker_index),
                )
            except Exception as e:
                if cancel_event is not None and cancel_event.is_set():
                    raise RuntimeError("cancelled") from e
                raise
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu()
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            audio = np.clip(audio, -1.0, 1.0)
            return audio
