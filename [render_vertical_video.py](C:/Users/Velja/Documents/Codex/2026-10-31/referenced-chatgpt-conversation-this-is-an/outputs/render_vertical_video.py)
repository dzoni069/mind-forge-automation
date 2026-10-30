#!/usr/bin/env python3
"""Build a captioned 9:16 MIND FORGE video from script.txt and voice.wav."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole_seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{millis:03}"


def caption_groups(text: str, max_words: int = 5, max_chars: int = 32) -> list[str]:
    words = text.split()
    groups: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join([*current, word])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            groups.append(" ".join(current))
            current = []
        current.append(word)
        if re.search(r"[.!?][\"')\]]?$", word):
            groups.append(" ".join(current))
            current = []

    if current:
        groups.append(" ".join(current))
    return groups


def write_srt(text: str, duration: float, destination: Path) -> None:
    groups = caption_groups(text)
    if not groups:
        raise ValueError("script.txt does not contain any captions")

    # Timing is estimated from phrase length and punctuation. It is suitable
    # for a first draft, but it is not word-level speech recognition.
    weights = [max(1, len(group)) for group in groups]
    pauses = []
    for group in groups:
        final_word = group.split()[-1]
        if re.search(r"[.!?][\"')\]]?$", final_word):
            pauses.append(0.22)
        elif re.search(r"[,;:][\"')\]]?$", final_word):
            pauses.append(0.10)
        else:
            pauses.append(0.0)

    total_pause = min(sum(pauses), duration * 0.15)
    speech_time = max(0.1, duration - total_pause)
    total_weight = sum(weights)
    cursor = 0.0
    entries: list[str] = []

    for index, (group, weight, pause) in enumerate(zip(groups, weights, pauses), start=1):
        start = cursor
        cursor += speech_time * weight / total_weight + pause
        end = duration if index == len(groups) else min(cursor, duration)
        entries.append(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{group}\n")

    destination.write_text("\n".join(entries), encoding="utf-8")


def make_title(text: str, destination: Path) -> None:
    words = text.split()[:8]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > 23:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, default=Path("source-assets"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()

    script_path = args.assets / "script.txt"
    voice_path = args.assets / "voice.wav"
    for required in (script_path, voice_path):
        if not required.is_file():
            raise FileNotFoundError(f"Required file is missing: {required}")

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is not installed")

    text = script_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("script.txt is empty")

    duration = float(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(voice_path),
            ]
        )
    )
    if duration < 5 or duration > 180:
        raise ValueError(f"Unexpected voice duration: {duration:.1f} seconds")

    args.output.mkdir(parents=True, exist_ok=True)
    video_path = args.output / "mind-forge-video.mp4"
    srt_path = args.output / "captions.srt"
    title_path = args.output / "opening-title.txt"
    write_srt(text, duration, srt_path)
    make_title(text, title_path)
    shutil.copy2(script_path, args.output / "script.txt")
    shutil.copy2(voice_path, args.output / "voice.wav")

    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    fonts_dir = "/usr/share/fonts/truetype/dejavu"
    if not Path(font).is_file():
        raise FileNotFoundError(f"Expected font is missing: {font}")

    background = (
        "gradients=s=1080x1920:r=30:"
        f"d={duration:.3f}:c0=0x080B1F:c1=0x182451:c2=0x422879:"
        "n=3:type=radial:speed=0.18:seed=19"
    )
    video_filters = ",".join(
        [
            "drawgrid=w=150:h=150:t=1:c=white@0.07",
            "drawbox=x=50:y=110:w=980:h=1700:color=white@0.13:t=4",
            "drawbox=x='75+abs(sin(t*0.6))*760':y=430:w=180:h=10:color=0x22D3EE@0.85:t=fill",
            f"drawtext=fontfile={font}:text='MIND FORGE':fontcolor=white:fontsize=56:"
            "x=(w-text_w)/2:y=155:shadowcolor=black@0.7:shadowx=2:shadowy=2",
            f"drawtext=fontfile={font}:textfile='{title_path.resolve()}':fontcolor=white:fontsize=72:"
            "line_spacing=14:x=(w-text_w)/2:y=510:box=1:boxcolor=0x080B1F@0.45:"
            "boxborderw=28:enable='between(t,0,4)'",
            f"subtitles=filename='{srt_path.resolve()}':fontsdir='{fonts_dir}':"
            "force_style='FontName=DejaVu Sans,FontSize=48,Bold=1,Outline=2,Shadow=0,"
            "Alignment=2,MarginL=100,MarginR=100,MarginV=350,BorderStyle=3,"
            "BackColour=&H99080B1F'",
        ]
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-f",
        "lavfi",
        "-i",
        background,
        "-i",
        str(voice_path),
        "-vf",
        video_filters,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        f"{duration:.3f}",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(video_path),
    ]
    print(f"Rendering a 1080x1920 video ({duration:.1f} seconds)...")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("FFmpeg could not render the video") from error

    print(f"Video ready: {video_path}")
    print(f"Captions ready: {srt_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # keep GitHub Actions logs understandable
        print(f"VIDEO BUILD ERROR: {error}", file=sys.stderr)
        raise
