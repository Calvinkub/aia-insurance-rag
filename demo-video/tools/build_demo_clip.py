"""Cut a real screen recording of the demo page into the narrated clips used by DemoScene.

The recording is a full-screen Chrome capture, so this script also crops away the browser tabs and bookmarks bar:
only the web page (below the toolbar) is kept, scaled to 1680x944 (x264 needs an even height). Nothing from the raw recording is committed.

Usage: python3 tools/build_demo_clip.py "/path/to/Screen Recording.mov"
Writes public/demo.mp4, public/demo_timeline.json and src/demo_timeline.json (start/end seconds of each narrated clip).
Each clip's window is at least as long as its voice-over (src/audio.json) plus a margin; the last frame is held if the
recording segment is shorter than that.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = ["npx", "remotion", "ffmpeg", "-y", "-loglevel", "error"]
CROP = "crop=2848:1602:46:164"  # page area of a 2940x1766 retina screen: skips the 164 px of browser UI at the top
MARGIN = 1.0  # seconds of picture after the voice ends

# (clip key, source start s, source end s) in the raw recording
SEGMENTS = [
    ("demo1", 0.4, 11.6),   # Thai question: RAG answer with verified citation, then the same question in Agent mode
    ("demo2", 16.6, 21.9),  # vague question: the agent asks what is meant
    ("demo3", 30.4, 37.4),  # clear question: agent calls list_products
    ("demo4", 37.7, 44.2),  # same question in RAG mode: abstains
    ("demo5", 44.2, 56.0),  # English question: RAG with verified citation, then Agent
]


def main(src: str) -> None:
    audio = json.loads((ROOT / "src" / "audio.json").read_text())
    tmp = Path(tempfile.mkdtemp(prefix="demo_clip_"))
    parts, timeline, t = [], {}, 0.0
    for key, a, b in SEGMENTS:
        want = audio[key] + MARGIN
        hold = max(0.0, want - (b - a))
        vf = f"{CROP},scale=1680:944:flags=lanczos"
        out = tmp / f"{key}.mp4"
        subprocess.run([*FFMPEG, "-ss", str(a), "-to", str(b), "-i", src, "-an", "-vf", vf,
                        "-r", "30", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(out)], check=True, cwd=ROOT)
        parts.append(out)
        if hold:  # this ffmpeg build has no tpad filter: hold the last frame with a looped still image
            still = tmp / f"{key}.png"
            subprocess.run([*FFMPEG, "-ss", str(b - 0.05), "-i", src, "-frames:v", "1", "-vf", vf, str(still)], check=True, cwd=ROOT)
            held = tmp / f"{key}_hold.mp4"
            subprocess.run([*FFMPEG, "-loop", "1", "-framerate", "30", "-t", f"{hold:.2f}", "-i", str(still), "-r", "30",
                            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(held)], check=True, cwd=ROOT)
            parts.append(held)
        length = (b - a) + hold
        timeline[key] = {"start": round(t, 2), "end": round(t + length, 2)}
        t += length
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run([*FFMPEG, "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
                    str(ROOT / "public" / "demo.mp4")], check=True, cwd=ROOT)
    timeline["duration"] = round(t, 2)
    for p in (ROOT / "public" / "demo_timeline.json", ROOT / "src" / "demo_timeline.json"):
        p.write_text(json.dumps(timeline, indent=2))
    print(timeline)


if __name__ == "__main__":
    main(sys.argv[1])
