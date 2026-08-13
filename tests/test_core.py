"""Unit tests for core logic (no GPU / no model required).

Run:  source .venv/bin/activate && pytest tests/ -v
"""

import time

import numpy as np
import pytest

from app.audio.pcm import pcm_bytes, wav_from_pcm, pcm_from_wav
from app.schemas.errors import ApiException, ErrorCodes
from app.runtime.scheduler import Scheduler
from app.text.normalizer import normalize_text, split_for_long_mode
from app.text.phrase_buffer import PhraseBuffer


# ---------------------------------------------------------------- text

def test_normalize_empty_raises():
    with pytest.raises(ApiException) as ei:
        normalize_text("   ")
    assert ei.value.code == ErrorCodes.EMPTY_TEXT


def test_normalize_too_long():
    with pytest.raises(ApiException) as ei:
        normalize_text("x" * 6000)
    assert ei.value.code == ErrorCodes.TEXT_TOO_LONG


def test_normalize_collapses_whitespace():
    assert normalize_text("  Hello   world\n") == "Hello world"


def test_split_long_mode():
    text = " ".join(["word"] * 500)
    parts = split_for_long_mode(text, max_chars=100)
    assert len(parts) > 1
    assert all(len(p) <= 100 for p in parts)
    assert "".join(parts).replace(" ", "") == text.replace(" ", "")


# ------------------------------------------------------------- phrase buffer

def test_phrase_no_flush_before_min_words():
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    b.append("one two, ")
    assert b.pop_ready() == []


def test_phrase_flush_on_period():
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    b.append("Hello there.")
    assert b.pop_ready() == ["Hello there."]


def test_phrase_flush_on_hindi_danda():
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    b.append("\u091c\u0940 \u0938\u0930\u0964")
    assert b.pop_ready() == ["\u091c\u0940 \u0938\u0930\u0964"]


def test_phrase_hard_timeout():
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=40)
    b.append("a b c ")
    time.sleep(0.08)
    assert b.pop_ready() == ["a b c"]


def test_phrase_max_words():
    # max_words is the flush threshold: buffer flushes as soon as the cap is hit.
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=10,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    b.append(" ".join(str(i) for i in range(20)))
    phrase = b.pop_ready()[0]
    assert len(phrase.split()) == 20


def test_phrase_commit_flush():
    b = PhraseBuffer()
    b.append("xyz")
    assert b.flush_all() == ["xyz"]
    assert b.flush_all() == []


def test_phrase_streaming_simulation():
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=30, hard_timeout_ms=80)
    b.append("\u091c\u0940 ")
    time.sleep(0.05)
    b.append("\u0938\u0930, ")
    time.sleep(0.05)
    # 2 words + comma is below min_words=3: not flushed yet
    assert b.pop_ready() == []
    b.append("\u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964")
    time.sleep(0.05)
    # sentence-final punctuation flushes the whole pending buffer
    assert b.pop_ready() == [
        "\u091c\u0940 \u0938\u0930, \u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964"]


def test_phrase_splits_at_first_sentence_final():
    # Multiple sentences arriving together flush one sentence at a time.
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    b.append("One. Two. Three.")
    assert b.pop_ready() == ["One.", "Two.", "Three."]
    assert b.pop_ready() == []


def test_phrase_commit_splits_sentences():
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    b.append("Aapka order. Dhanyavaad.")
    assert b.flush_all() == ["Aapka order.", "Dhanyavaad."]
    assert b.flush_all() == []


def test_phrase_comma_does_not_split_mid_sentence():
    # A comma must not flush a short sentence; only sentence-final punctuation does.
    demo = "\u091c\u0940 \u0938\u0930, \u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964"
    b = PhraseBuffer(min_words=3, preferred_words=8, max_words=18,
                     soft_timeout_ms=0, hard_timeout_ms=0)
    i = 0
    while i < len(demo):
        b.append(demo[i:i + 6])
        i += 6
    assert b.pop_ready() == [demo]



# -------------------------------------------------------------- audio pcm

def test_wav_roundtrip():
    audio = np.sin(2 * np.pi * 440 * np.arange(2205) / 22050).astype(np.float32)
    wav = wav_from_pcm(pcm_bytes(audio), 22050)
    back, sr, ch = pcm_from_wav(wav)
    assert sr == 22050 and ch == 1
    assert len(back) == 2205
    assert np.allclose(back, audio, atol=1 / 32768)


# ---------------------------------------------------------------- scheduler

def test_scheduler_priority_order():
    s = Scheduler(max_queue=8)
    s.start()
    order = []

    def fake_synth(cancel_event):
        time.sleep(0.05)
        if cancel_event.is_set():
            raise RuntimeError("cancelled")
        return np.ones(10, dtype=np.float32)

    def mk(tag):
        def fn(ce):
            order.append(tag)
            return fake_synth(ce)
        return fn

    s.submit(mk("bench"), priority=30)
    s.submit(mk("realtime"), priority=0)
    s.submit(mk("normal"), priority=10)
    time.sleep(0.5)
    assert order == ["realtime", "normal", "bench"]
    s.stop()


def test_scheduler_queue_full():
    s = Scheduler(max_queue=1)
    s.start()
    s.submit(lambda ce: np.zeros(1, dtype=np.float32), priority=10)
    with pytest.raises(ApiException) as ei:
        s.submit(lambda ce: np.zeros(1, dtype=np.float32), priority=10)
    assert ei.value.code == ErrorCodes.QUEUE_FULL
    s.stop()


def test_scheduler_cancel_active():
    s = Scheduler(max_queue=8)
    s.start()

    def slow(ce):
        time.sleep(0.4)
        if ce.is_set():
            raise RuntimeError("cancelled")
        return np.ones(5, dtype=np.float32)

    job = s.submit(slow, priority=10)
    time.sleep(0.1)
    s.cancel(job_id=job.job_id)
    with pytest.raises(ApiException) as ei:
        s.wait(job, 5)
    assert ei.value.code == ErrorCodes.SYNTHESIS_CANCELLED
    s.stop()


def test_scheduler_cancel_all():
    s = Scheduler(max_queue=8)
    s.start()

    def slow(ce):
        time.sleep(0.4)
        if ce.is_set():
            raise RuntimeError("cancelled")
        return np.ones(5, dtype=np.float32)

    s.submit(slow, priority=0)
    s.submit(slow, priority=10)
    time.sleep(0.05)
    n = s.cancel()
    assert n == 2
    time.sleep(0.5)
    assert s.stats["queue_depth"] == 0
    s.stop()


def test_scheduler_timeout():
    s = Scheduler(max_queue=8)
    s.start()

    def stuck(ce):
        time.sleep(5)
        return np.ones(5, dtype=np.float32)

    job = s.submit(stuck, priority=10)
    with pytest.raises(ApiException) as ei:
        s.wait(job, 0.3)
    assert ei.value.code == ErrorCodes.SYNTHESIS_TIMEOUT
    s.cancel()
    s.stop()
