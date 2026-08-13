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

    @staticmethod
    def _install_safe_sampling(model) -> None:
        """Make Magpie's topk=1 sampling paths truly greedy and fp16-safe.

        NeMo's EOS-detection probe calls ``sample_codes_from_logits`` with
        ``topk=1``, but that method still runs ``softmax(logits / temperature)``
        followed by ``torch.multinomial``. In fp16, large codec logits (or their
        division by a tiny temperature) overflow to +inf / NaN, which
        ``torch.multinomial`` rejects with a CUDA device-side assert, and a
        garbage argmax can trigger premature EOS (truncated audio). With
        ``topk=1`` there is exactly one surviving token, so a real ``argmax`` is
        mathematically equivalent and removes ``softmax``/``multinomial`` from
        the path entirely.

        We also force ``sanitize_logits=True`` on the AR local-transformer
        sampler (nan_to_num + clamp before sampling) to neutralise fp16
        instability in the main generation logits.
        """
        from types import MethodType

        import torch
        from nemo.collections.tts.modules.magpietts_modules import clear_forbidden_logits

        if getattr(model, "_magpie_safe_sampling_installed", False):
            return

        original = model.sample_codes_from_logits

        def _safe_sample_codes_from_logits(
            self,
            all_code_logits_t,
            temperature=0.7,
            topk=80,
            unfinished_items=None,
            finished_items=None,
            forbid_audio_eos=False,
        ):
            unfinished_items = unfinished_items or {}
            finished_items = finished_items or {}

            # Non-greedy paths keep NeMo's original behaviour.
            if int(topk) != 1:
                return original(
                    all_code_logits_t,
                    temperature=temperature,
                    topk=topk,
                    unfinished_items=unfinished_items,
                    finished_items=finished_items,
                    forbid_audio_eos=forbid_audio_eos,
                )

            all_preds = [[] for _ in range(self.frame_stacking_factor)]
            for fs_index in range(self.frame_stacking_factor):
                for idx in range(self.num_audio_codebooks):
                    si = (idx + self.num_audio_codebooks * fs_index) * self.num_all_tokens_per_codebook
                    ei = si + self.num_all_tokens_per_codebook
                    logits = all_code_logits_t[:, si:ei].clone()

                    # Sanitize in fp32 before applying any intentional -inf masks.
                    logits = torch.nan_to_num(logits.float(), nan=0.0, posinf=100.0, neginf=-100.0)
                    logits = logits.clamp(min=-100.0, max=100.0)

                    for item_idx in unfinished_items:
                        logits[item_idx, self.audio_eos_id] = float("-inf")
                    for item_idx in finished_items:
                        logits[item_idx, :] = float("-inf")
                        logits[item_idx, self.audio_eos_id] = 0.0

                    logits = clear_forbidden_logits(
                        logits.unsqueeze(1), self.codebook_size, forbid_audio_eos=forbid_audio_eos
                    ).squeeze(1)

                    # True greedy: no softmax, no division, no multinomial.
                    codebook_preds = torch.argmax(logits, dim=-1, keepdim=True).long()
                    all_preds[fs_index].append(codebook_preds)

            all_preds = [torch.cat(preds, dim=1) for preds in all_preds]
            return torch.stack(all_preds, dim=2)

        model.sample_codes_from_logits = MethodType(_safe_sample_codes_from_logits, model)

        # Force sanitize_logits=True on the AR local-transformer sampler when the
        # signature supports it.
        lt = getattr(model, "_lt_helper", None)
        if lt is not None and hasattr(lt, "sample_autoregressive"):
            import inspect

            original_ar = lt.sample_autoregressive
            if "sanitize_logits" in inspect.signature(original_ar).parameters:

                def _safe_ar(*args, **kwargs):
                    kwargs["sanitize_logits"] = True
                    return original_ar(*args, **kwargs)

                lt.sample_autoregressive = _safe_ar

        model._magpie_safe_sampling_installed = True
        logger.info("installed safe greedy sampling (true-argmax EOS probe + sanitize_logits)")

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
            # temperature stays <= 0.0: the AR local-transformer sampler maps
            # temperature <= 0 to argmax directly, so a small positive value would
            # route through softmax(logits / t) -> multinomial and overflow in fp16.
            #
            # The EOS probe (sample_codes_from_logits, topk=1) is replaced by a
            # true-argmax + fp32-sanitized implementation in
            # _install_safe_sampling, which removes torch.multinomial from the
            # topk=1 path entirely (the source of the device-side assert).
            try:
                ip = model.inference_parameters
                ip.temperature = 0.0
                ip.topk = 1
                ip.eos_detection_method = "argmax_any"
                ip.ignore_finished_sentence_tracking = True
                logger.info("inference: greedy decoding (temperature=0.0, topk=1, eos=argmax_any, sentence_tracking=NeMo default)")
            except Exception as e:
                logger.warning("could not set greedy inference params: %s", e)
            dtype = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}.get(precision)
            if dtype is not None and dtype != torch.float32:
                self._install_dtype_shims(torch)
                model = model.to(dtype=dtype)
            model = model.to(device)
            self._install_safe_sampling(model)
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

    @staticmethod
    def _is_fatal_cuda_error(exc: BaseException) -> bool:
        msg = str(exc).lower()
        return "device-side assert" in msg or "cudaerrorassert" in msg

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
                if self._is_fatal_cuda_error(e):
                    logger.critical("fatal CUDA context error; terminating worker so systemd can reload it: %s", e)
                    import os
                    os._exit(70)
                raise
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu()
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            audio = np.clip(audio, -1.0, 1.0)
            return audio
