import json


def format_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_txt(segments: list) -> str:
    return "\n".join(seg["text"].strip() for seg in segments)


def to_srt(segments: list) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_time(seg["start"])
        end = format_srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n")
    return "\n".join(lines)


def to_json(segments: list, meta: dict = None) -> str:
    payload = {"segments": segments}
    if meta:
        payload["meta"] = meta
    return json.dumps(payload, ensure_ascii=False, indent=2)


def regroup_segments(segments: list, max_words: int = 0, merge: bool = True) -> list:
    if not max_words or max_words <= 0 or not segments:
        return list(segments)

    groups = []
    for seg in segments:
        words = seg["text"].split()
        if not words:
            continue
        if merge and groups and len(groups[-1]["words"]) + len(words) <= max_words:
            groups[-1]["words"].extend(words)
            groups[-1]["end"] = seg["end"]
        else:
            groups.append({"start": seg["start"], "end": seg["end"], "words": list(words)})

    result = []
    for g in groups:
        words = g["words"]
        total = len(words)
        if total <= max_words:
            result.append({"start": g["start"], "end": g["end"], "text": " ".join(words)})
        else:
            n_chunks = -(-total // max_words)
            duration = g["end"] - g["start"]
            for i in range(n_chunks):
                chunk = words[i * max_words:(i + 1) * max_words]
                t0 = g["start"] + duration * (i * max_words) / total
                t1 = g["start"] + duration * min((i + 1) * max_words, total) / total
                result.append({
                    "start": round(t0, 3),
                    "end": round(t1, 3),
                    "text": " ".join(chunk),
                })
    return result
