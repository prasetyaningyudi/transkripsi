from pathlib import Path
from typing import Callable, Optional

_model_cache = {}


def _get_whisper_model(model_size: str):
    if model_size not in _model_cache:
        from faster_whisper import WhisperModel

        try:
            model = WhisperModel(model_size, device="auto", compute_type="auto")
        except Exception:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _model_cache[model_size] = model
    return _model_cache[model_size]


def transcribe_whisper_local(
    audio_path: str,
    model_size: str = "small",
    language: Optional[str] = "id",
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> list:
    model = _get_whisper_model(model_size)
    lang = language if language and language != "auto" else None
    segments_iter, info = model.transcribe(
        audio_path,
        language=lang,
        vad_filter=True,
        beam_size=5,
    )
    duration = getattr(info, "duration", None) or 0.0
    detected = getattr(info, "language", lang or "unknown")
    results = []
    for seg in segments_iter:
        results.append(
            {"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()}
        )
        if progress_cb and duration > 0:
            progress_cb(min(seg.end / duration, 1.0), f"Segmen {len(results)}")
    if progress_cb:
        progress_cb(1.0, "Selesai")
    return results, detected


def transcribe_openai(
    audio_path: str,
    api_key: str,
    language: Optional[str] = "id",
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> list:
    from openai import OpenAI

    if not api_key:
        raise ValueError("API key OpenAI diperlukan untuk engine cloud.")
    client = OpenAI(api_key=api_key)
    if progress_cb:
        progress_cb(0.1, "Mengirim ke OpenAI...")
    lang = language if language and language != "auto" else None
    kwargs = {"model": "whisper-1", "response_format": "verbose_json"}
    if lang:
        kwargs["language"] = lang
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(file=f, **kwargs)
    if progress_cb:
        progress_cb(0.9, "Memproses hasil...")
    results = []
    for seg in getattr(result, "segments", []) or []:
        results.append(
            {
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
            }
        )
    if not results and getattr(result, "text", None):
        results.append({"start": 0.0, "end": 0.0, "text": result.text.strip()})
    if progress_cb:
        progress_cb(1.0, "Selesai")
    detected = getattr(result, "language", lang or "unknown")
    return results, detected
