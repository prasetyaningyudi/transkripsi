import shutil
import subprocess

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".webm"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}


def is_video(filename: str) -> bool:
    from pathlib import Path
    return Path(filename).suffix.lower() in VIDEO_EXTS


def is_supported(filename: str) -> bool:
    from pathlib import Path
    return Path(filename).suffix.lower() in AUDIO_EXTS | VIDEO_EXTS


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def extract_audio(video_path: str, audio_path: str) -> None:
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg tidak ditemukan. Install ffmpeg lalu tambahkan ke PATH. "
            "https://ffmpeg.org/download.html"
        )
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Gagal ekstrak audio: {result.stderr[-500:]}")
