# Transkripsi Audio/Video — Bahasa Indonesia

Aplikasi web untuk mengubah audio/video menjadi teks (subtitle) dalam bahasa Indonesia. Mendukung dua engine:

- **Whisper Lokal** — offline via [faster-whisper], gratis, tanpa API key
- **OpenAI Cloud** — via API `whisper-1`, butuh API key

## Fitur

- Upload audio (`mp3`, `wav`, `m4a`, `flac`, `ogg`, dll) atau video (`mp4`, `mkv`, `mov`, `avi`, `webm`)
- Ekstrak audio otomatis dari video (ffmpeg)
- Progress bar real-time
- **Player audio/video** di browser — putar sambil cek hasil transkrip
- **Klik segmen transkrip** → player lompat & play ke waktu segmen tersebut (segmen aktif tersorot otomatis)
- Download hasil: `.txt`, `.srt`, `.json` (timestamp per segmen)
- Saat download SRT/JSON: atur **maksimal kata per timestamp** (mis. 8 kata), opsi gabung segmen kecil / tanpa batas
- Deteksi bahasa otomatis / pilih manual (`id`, `en`, auto)

## Prasyarat

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) di PATH (wajib untuk file video)
- RAM ≥ 8 GB untuk model Whisper `medium`/`large-v3`

## Instalasi

```bash
pip install -r requirements.txt
```

## Menjalankan

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Buka browser: **http://127.0.0.1:8000**

## Penggunaan

1. Tarik/klik area upload, pilih file audio atau video
2. Pilih engine:
   - **Whisper Lokal** — pilih model (`tiny` s/d `large-v3`; makin besar makin akurat tapi makin lambat)
   - **OpenAI Cloud** — masukkan API key OpenAI (`sk-...`)
3. Pilih bahasa (`id` = Indonesia, atau `auto`)
4. Klik **Transkrip Sekarang** — player muncul, bisa diputar sambil menunggu
5. Setelah selesai: klik segmen transkrip untuk lompat ke waktunya
6. Download hasil:
   - **TXT** — teks polos utuh (tanpa prompt)
   - **SRT / JSON** — muncul pertanyaan *maksimal kata per timestamp* (default 8, atau pilih "Tanpa batas")

## Struktur Proyek

```
subtitle/
├── backend/
│   ├── main.py          # Server FastAPI + endpoint
│   ├── transcriber.py   # Whisper lokal + OpenAI API
│   ├── media.py         # Ekstrak audio video (ffmpeg)
│   └── formatters.py    # Konversi ke txt / srt / json
├── frontend/
│   └── index.html       # UI web
├── uploads/             # File sementara saat diproses
├── outputs/             # Hasil transkrip
└── requirements.txt
```

## API

| Method | Endpoint | Deskripsi |
|---|---|---|
| POST | `/api/transcribe` | Upload file + opsi → `job_id` |
| GET | `/api/jobs/{id}` | Status job + preview + segmen |
| GET | `/api/jobs/{id}/media` | Putar file asli (audio/video) |
| GET | `/api/jobs/{id}/download/{txt\|srt\|json}` | Ambil hasil (`?max_words=8&merge=1` untuk SRT/JSON) |
| GET | `/api/health` | Cek status + ketersediaan ffmpeg |

## Catatan

- Model Whisper diunduh otomatis dari Hugging Face saat pertama kali dipakai (butuh internet sekali saja)
- File video dikonversi ke WAV 16 kHz mono sebelum transkripsi
- API key OpenAI tidak disimpan di server
