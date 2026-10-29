import mimetypes
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from . import media
from .formatters import regroup_segments, to_json, to_srt, to_txt
from .transcriber import transcribe_openai, transcribe_whisper_local

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
FRONTEND_DIR = BASE_DIR / "frontend"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

jobs = {}
jobs_lock = threading.Lock()

app = FastAPI(title="Transkripsi Audio/Video ID")


@app.on_event("startup")
async def _cleanup_old_files():
    cutoff = time.time() - 24 * 3600
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        for f in d.glob("*"):
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            except OSError:
                pass


def _set_job(job_id: str, **kwargs):
    with jobs_lock:
        jobs[job_id].update(kwargs)


def _process(job_id: str, input_path: Path, ext: str, engine: str,
             model_size: str, language: str, api_key: str):
    tmp_dir = None
    try:
        _set_job(job_id, status="processing", progress=0.05, message="Menyiapkan audio...")
        audio_path = input_path
        if media.is_video(input_path.name):
            if not media.ffmpeg_available():
                raise RuntimeError("ffmpeg tidak ditemukan — diperlukan untuk file video.")
            tmp_dir = tempfile.mkdtemp(prefix="transcribe_")
            audio_path = Path(tmp_dir) / "audio.wav"
            media.extract_audio(str(input_path), str(audio_path))
            _set_job(job_id, progress=0.15, message="Audio diekstrak, mulai transkripsi...")

        def progress_cb(p, msg):
            _set_job(job_id, progress=round(0.15 + p * 0.8, 3), message=msg)

        if engine == "openai":
            segments, detected = transcribe_openai(
                str(audio_path), api_key=api_key, language=language, progress_cb=progress_cb
            )
        else:
            segments, detected = transcribe_whisper_local(
                str(audio_path), model_size=model_size, language=language, progress_cb=progress_cb
            )

        _set_job(job_id, message="Menyimpan hasil...")
        stem = input_path.stem
        out_txt = OUTPUT_DIR / f"{job_id}_{stem}.txt"
        out_srt = OUTPUT_DIR / f"{job_id}_{stem}.srt"
        out_json = OUTPUT_DIR / f"{job_id}_{stem}.json"
        meta = {
            "source": input_path.name,
            "engine": engine,
            "model": model_size if engine == "whisper-local" else "whisper-1",
            "language": detected,
            "duration_segments": len(segments),
        }
        out_txt.write_text(to_txt(segments), encoding="utf-8")
        out_srt.write_text(to_srt(segments), encoding="utf-8")
        out_json.write_text(to_json(segments, meta), encoding="utf-8")

        _set_job(
            job_id,
            status="done",
            progress=1.0,
            message="Selesai",
            detected_language=detected,
            segment_count=len(segments),
            preview=to_txt(segments)[:2000],
            segments=segments,
            files={"txt": out_txt.name, "srt": out_srt.name, "json": out_json.name},
        )
    except Exception as e:
        _set_job(job_id, status="error", message=str(e))
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/")
async def index():
    index_path = FRONTEND_DIR / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health():
    return {"ok": True, "ffmpeg": media.ffmpeg_available()}


@app.post("/api/transcribe")
async def transcribe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    engine: str = Form("whisper-local"),
    model_size: str = Form("small"),
    language: str = Form("id"),
    openai_api_key: str = Form(""),
):
    if not file.filename:
        raise HTTPException(400, "File tidak ditemukan.")
    if not media.is_supported(file.filename):
        raise HTTPException(400, f"Format file tidak didukung: {file.filename}")
    if engine not in ("whisper-local", "openai"):
        raise HTTPException(400, "Engine tidak valid.")
    if engine == "openai" and not openai_api_key.strip():
        raise HTTPException(400, "API key OpenAI wajib diisi untuk engine cloud.")

    job_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{job_id}_{Path(file.filename).name}"
    with input_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Antre...",
            "filename": file.filename,
            "engine": engine,
            "input_path": str(input_path),
            "media_kind": "video" if media.is_video(file.filename) else "audio",
        }
    background_tasks.add_task(
        _process, job_id, input_path, ext, engine, model_size, language, openai_api_key.strip()
    )
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job tidak ditemukan.")
        data = {k: v for k, v in job.items() if k not in ("preview", "input_path")}
        if job.get("status") == "done":
            data["preview"] = job.get("preview", "")
        return data


@app.get("/api/jobs/{job_id}/media")
async def job_media(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job tidak ditemukan.")
        path = job.get("input_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "File media tidak ditemukan.")
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@app.get("/api/jobs/{job_id}/download/{fmt}")
async def download(job_id: str, fmt: str, max_words: int = 0, merge: int = 1):
    if fmt not in ("txt", "srt", "json"):
        raise HTTPException(400, "Format tidak valid.")
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.get("status") != "done":
            raise HTTPException(404, "Hasil belum tersedia.")
        segments = job.get("segments") or []
        filename = job.get("filename", job_id)
        meta = {
            "source": filename,
            "engine": job.get("engine"),
            "language": job.get("detected_language"),
            "max_words": max_words if fmt in ("srt", "json") else 0,
        }

    stem = Path(filename).stem
    if fmt == "txt":
        content = to_txt(segments)
        media_type = "text/plain"
    elif fmt == "srt":
        out_segs = regroup_segments(segments, max_words, bool(merge)) if max_words else segments
        content = to_srt(out_segs)
        media_type = "application/x-subrip"
    else:
        out_segs = regroup_segments(segments, max_words, bool(merge)) if max_words else segments
        content = to_json(out_segs, meta)
        media_type = "application/json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{stem}.{fmt}"'},
    )
