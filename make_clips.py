"""Cut one clip per question: max(0, t - 239 s) through t, at 1 FPS, without audio."""
import json
import re
import subprocess
from pathlib import Path

DATA_DIR = Path("The_Prestige")
VIDEO_DIR = Path("videos")      # videos/<video_id>.mp4, obtained yourself
CLIP_DIR = Path("clips")
MANIFEST = Path("manifest.jsonl")
MAX_WINDOW = 240                # at most 240 inclusive one-second samples at 1 FPS
FPS = 1                         # None keeps the native frame rate

TIME_RE = re.compile(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b")


def to_seconds(ts):
    seconds = 0
    for part in ts.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def to_timestamp(seconds):
    h, rest = divmod(max(0, seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def shift_timestamps(text, offset):
    """Rewrite times in the question so they refer to the clip, not the full video."""
    if offset <= 0:
        return text
    return TIME_RE.sub(lambda m: to_timestamp(to_seconds(m.group()) - offset), text)


def cut_clip(src, dst, start, end):
    tmp = dst.with_name(dst.stem + ".part.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-ss", str(start), "-t", str(end - start + 1), "-i", str(src)]
    if FPS:
        cmd += ["-vf", f"fps={FPS}", "-frames:v", str(round((end - start + 1) * FPS))]
    cmd += ["-an", "-c:v", "libx264", "-preset", "ultrafast", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(dst)


def main():
    CLIP_DIR.mkdir(exist_ok=True)
    rows, missing = [], set()
    for path in sorted(DATA_DIR.glob("*.json")):
        for video_id, entry in json.loads(path.read_text(encoding="utf-8")).items():
            src = VIDEO_DIR / f"{video_id}.mp4"
            if not src.exists():
                missing.add(video_id)
                continue
            for q in entry["Questions"]:
                end = to_seconds(q["Timestamp"])
                start = max(0, end - MAX_WINDOW + 1)
                clip = CLIP_DIR / f"clip_uid{q['UID']}.mp4"
                if not clip.exists():
                    cut_clip(src, clip, start, end)
                rows.append({
                    "uid": q["UID"],
                    "video_id": video_id,
                    "clip": str(clip),
                    "question": shift_timestamps(q["Question"], start),
                    "question_type": q["Question type"],
                    "answer": q["Answer"],
                })
    with MANIFEST.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} questions to {MANIFEST}; {len(missing)} videos not found in {VIDEO_DIR}/")


if __name__ == "__main__":
    main()
